import httpx
import pytest
import respx
from pydantic import BaseModel

from app.ai.base import AIError, Usage
from app.ai.gemini import GeminiClient
from app.ai.limiter import RateLimiter

BASE = "https://gemini.test/v1beta"


class Out(BaseModel):
    topics: list[str]


def make(usage=None, retries=2) -> GeminiClient:
    async def sink(task, model, u: Usage, status):
        if usage is not None:
            usage.append((task, model, u.input_tokens, status))

    limiter = RateLimiter(6000, 1000)
    return GeminiClient(
        api_key="k", base_url=BASE, embedding_model="emb", embedding_dimensions=768,
        limiter_for=lambda _model: limiter, usage_sink=sink, max_retries=retries, backoff_base=0.001,
    )


def ok(text: str) -> httpx.Response:
    return httpx.Response(200, json={
        "candidates": [{"content": {"parts": [{"text": text}]}}],
        "usageMetadata": {"promptTokenCount": 7, "candidatesTokenCount": 3},
    })


@respx.mock
async def test_generate_json_validates_and_records_usage():
    route = respx.post(f"{BASE}/models/m:generateContent").mock(return_value=ok('{"topics": ["chips"]}'))
    seen: list = []
    out = await make(seen).generate_json("p", Out, model="m", task="enrich")
    assert out.topics == ["chips"]
    assert seen == [("enrich", "m", 7, "ok")]
    assert route.calls[0].request.headers["x-goog-api-key"] == "k"


@respx.mock
async def test_retries_on_429_then_succeeds():
    respx.post(f"{BASE}/models/m:generateContent").mock(side_effect=[httpx.Response(429), ok("hola")])
    seen: list = []
    assert await make(seen).generate("p", model="m", task="t") == "hola"
    assert [s[3] for s in seen] == ["rate_limited", "ok"]


@respx.mock
async def test_gives_up_after_max_retries():
    respx.post(f"{BASE}/models/m:generateContent").mock(return_value=httpx.Response(429))
    with pytest.raises(AIError):
        await make(retries=1).generate("p", model="m", task="t")


@respx.mock
async def test_invalid_structured_output_raises():
    respx.post(f"{BASE}/models/m:generateContent").mock(return_value=ok('{"wrong": 1}'))
    with pytest.raises(AIError):
        await make().generate_json("p", Out, model="m", task="t")


@respx.mock
async def test_embed_requests_configured_dimensions():
    route = respx.post(f"{BASE}/models/emb:batchEmbedContents").mock(
        return_value=httpx.Response(200, json={"embeddings": [{"values": [0.1, 0.2]}, {"values": [0.3, 0.4]}]})
    )
    vecs = await make().embed(["a", "b"], task="embed")
    assert vecs == [[0.1, 0.2], [0.3, 0.4]]
    assert b'"outputDimensionality":768' in route.calls[0].request.content.replace(b" ", b"")


def sse(*events: dict) -> httpx.Response:
    import json

    body = "".join(f"data: {json.dumps(e)}\r\n\r\n" for e in events)
    return httpx.Response(200, text=body, headers={"content-type": "text/event-stream"})


@respx.mock
async def test_stream_chat_yields_text_skips_thoughts_and_records_usage():
    route = respx.post(f"{BASE}/models/m:streamGenerateContent", params={"alt": "sse"}).mock(side_effect=[
        httpx.Response(429),
        sse(
            {"candidates": [{"content": {"parts": [{"text": "planning", "thought": True}]}}]},
            {"candidates": [{"content": {"parts": [{"text": "The Nobel "}]}}]},
            {"candidates": [{"content": {"parts": [{"text": "is a prize."}]}}],
             "usageMetadata": {"promptTokenCount": 120, "candidatesTokenCount": 9}},
        ),
    ])
    seen: list = []
    chunks = [c async for c in make(seen).stream_chat([("user", "What is it?")], model="m", task="chat", system="s")]
    assert chunks == ["The Nobel ", "is a prize."]
    assert route.call_count == 2  # one retry before the first chunk
    assert seen == [("chat", "m", 0, "rate_limited"), ("chat", "m", 120, "ok")]
    import json

    sent = json.loads(route.calls[-1].request.content)
    assert sent["contents"] == [{"role": "user", "parts": [{"text": "What is it?"}]}]
    assert sent["systemInstruction"] == {"parts": [{"text": "s"}]}


@respx.mock
async def test_stream_chat_gives_up_on_client_errors():
    respx.post(f"{BASE}/models/m:streamGenerateContent").mock(return_value=httpx.Response(400, text="bad"))
    with pytest.raises(AIError, match="400"):
        _ = [c async for c in make().stream_chat([("user", "q")], model="m", task="chat", system="s")]


@respx.mock
async def test_stream_chat_turns_a_silent_model_into_an_ai_error():
    respx.post(f"{BASE}/models/m:streamGenerateContent").mock(side_effect=httpx.ReadTimeout("slow"))
    with pytest.raises(AIError, match="ReadTimeout"):
        _ = [c async for c in make().stream_chat([("user", "q")], model="m", task="chat", system="s")]


@respx.mock
async def test_stream_chat_retries_a_silent_model_once_before_any_text():
    route = respx.post(f"{BASE}/models/m:streamGenerateContent").mock(side_effect=[
        httpx.ReadTimeout("slow"),
        sse({"candidates": [{"content": {"parts": [{"text": "Hola"}]}}]}),
    ])
    seen: list = []
    chunks = [c async for c in make(seen).stream_chat([("user", "q")], model="m", task="chat", system="s")]
    assert chunks == ["Hola"] and route.call_count == 2
    assert [s[3] for s in seen] == ["error", "ok"]


@respx.mock
async def test_stream_chat_does_not_restart_once_text_is_flowing():
    class Dropped(httpx.AsyncByteStream):
        async def __aiter__(self):
            yield b'data: {"candidates": [{"content": {"parts": [{"text": "Parcial"}]}}]}\n\n'
            raise httpx.ReadError("connection lost")

    route = respx.post(f"{BASE}/models/m:streamGenerateContent").mock(
        return_value=httpx.Response(200, stream=Dropped(), headers={"content-type": "text/event-stream"}))
    got: list[str] = []
    with pytest.raises(AIError, match="ReadError"):
        async for chunk in make().stream_chat([("user", "q")], model="m", task="chat", system="s"):
            got.append(chunk)
    assert got == ["Parcial"] and route.call_count == 1  # what the reader saw is not repeated
