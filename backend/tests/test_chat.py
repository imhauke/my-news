from datetime import UTC, date, datetime

import httpx
import pytest

from app import chat
from app.ai.base import AIError
from app.api import routes
from app.db import get_session
from app.main import app
from app.models import Article, HNComment

NOW = datetime(2026, 10, 6, 9, tzinfo=UTC)


class FakeAI:
    """Streams canned chunks; models listed in `failing` raise before the first one."""

    def __init__(self, failing=()):
        self.failing = set(failing)
        self.calls: list[tuple[str, str, list]] = []

    async def stream_chat(self, messages, *, model, task, system, priority, max_output_tokens, retries=1,
                          wait_seconds=25):
        self.calls.append((model, system, messages))
        if model in self.failing:
            raise AIError("busy")
        for chunk in ("El Nobel ", "es un premio."):
            yield chunk


@pytest.fixture
async def client(session, monkeypatch):
    async def override():
        yield session

    ai = FakeAI()
    app.dependency_overrides[get_session] = override
    app.dependency_overrides[routes.chat_ai] = lambda: ai
    monkeypatch.setattr(chat, "_guard", chat.ChatGuard(per_hour=3, per_day=100))

    async def no_page(article):
        return "Opening paragraphs of the original article. " * 3

    monkeypatch.setattr(chat, "article_text", no_page)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as c:
        c.ai = ai
        yield c
    app.dependency_overrides.clear()


async def story(session, **kw) -> Article:
    a = Article(source="hn", external_id="42", url="https://example.com/nobel", url_normalized="example.com/nobel",
                title="Nobel Prize in Chemistry awarded", published_at=NOW, ai_summary_en="Three chemists share it.",
                topics=["chemistry"], **kw)
    session.add(a)
    session.add(HNComment(id=1, story_id=42, author="ada", text="Great work on catalysts.", created_at=NOW, depth=0))
    await session.commit()
    return a


def events(text: str) -> list[tuple[str, str]]:
    out = []
    for block in text.strip().split("\n\n"):
        name, data = block.split("\n")
        out.append((name.removeprefix("event: "), data.removeprefix("data: ")))
    return out


async def test_streams_an_answer_grounded_in_the_story(session, client):
    a = await story(session)
    resp = await client.post(f"/articles/{a.id}/chat", json={"messages": [{"role": "user", "text": "¿Qué es?"}]})
    assert resp.status_code == 200 and resp.headers["content-type"].startswith("text/event-stream")
    assert events(resp.text) == [("delta", '{"text": "El Nobel "}'), ("delta", '{"text": "es un premio."}'),
                                 ("done", '{"model": "gemini-3.5-flash-lite"}')]
    model, system, messages = client.ai.calls[0]
    assert messages == [("user", "¿Qué es?")]
    for expected in ("Spanish", "Nobel Prize in Chemistry awarded", "Three chemists share it.",
                     "Opening paragraphs", "ada: Great work on catalysts."):
        assert expected in system


async def test_falls_back_to_flash_and_reports_when_nothing_answers(session, client):
    a = await story(session)
    client.ai.failing = {"gemini-3.5-flash-lite"}
    resp = await client.post(f"/articles/{a.id}/chat", json={"messages": [{"role": "user", "text": "q"}], "lang": "en"})
    assert events(resp.text)[-1] == ("done", '{"model": "gemini-3.8-flash"}')
    client.ai.failing = {"gemini-3.8-flash", "gemini-3.5-flash-lite"}
    resp = await client.post(f"/articles/{a.id}/chat", json={"messages": [{"role": "user", "text": "q"}]})
    assert events(resp.text) == [("error", '{"code": "unavailable"}')]


async def test_rejects_bad_requests_and_limits_each_visitor(session, client):
    a = await story(session)
    ask = {"messages": [{"role": "user", "text": "q"}]}
    assert (await client.post("/articles/999/chat", json=ask)).status_code == 404
    for bad in ({"role": "model", "text": "hi"}, {"role": "user", "text": "x" * 1001}):
        assert (await client.post(f"/articles/{a.id}/chat", json={"messages": [bad]})).status_code == 422
    for _ in range(3):
        assert (await client.post(f"/articles/{a.id}/chat", json=ask)).status_code == 200
    limited = await client.post(f"/articles/{a.id}/chat", json=ask)
    assert limited.status_code == 429 and limited.json()["detail"] == "rate_limited"
    other = await client.post(f"/articles/{a.id}/chat", json=ask, headers={"X-Real-IP": "203.0.113.9"})
    assert other.status_code == 200  # another visitor has their own allowance


def test_guard_resets_daily_budget_and_hourly_window():
    clock, day = [0.0], [date(2026, 10, 6)]
    g = chat.ChatGuard(per_hour=2, per_day=3, clock=lambda: clock[0], today=lambda: day[0])
    g.check("a"); g.check("a")  # noqa: E702
    with pytest.raises(chat.ChatLimited, match="rate_limited"):
        g.check("a")
    clock[0] = 3601
    g.check("a")
    with pytest.raises(chat.ChatLimited, match="daily_limit"):
        g.check("b")
    day[0] = date(2026, 10, 7)
    g.check("b")


def test_story_context_says_when_the_article_text_is_missing():
    a = Article(source="reuters", title="Talks resume", published_at=NOW, section="world", topics=[], summary=None)
    text = chat.story_context(a, None, [])
    assert "Talks resume" in text and "Reuters does not allow" in text and "comments" not in text
