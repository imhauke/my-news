"""Gemini client (REST API, free tier) with rate limiting, retries and usage logging."""

import asyncio
import json
import random
from collections.abc import AsyncIterator, Awaitable, Callable

import httpx
import structlog

from app.ai.base import AIError, Priority, QuotaExhausted, T, Usage
from app.ai.limiter import RateLimiter

log = structlog.get_logger()

UsageSink = Callable[[str, str, Usage, str], Awaitable[None]]  # task, model, usage, status


class GeminiClient:
    def __init__(
        self,
        *,
        api_key: str,
        base_url: str,
        embedding_model: str,
        embedding_dimensions: int,
        limiter_for: Callable[[str], RateLimiter],
        http: httpx.AsyncClient | None = None,
        usage_sink: UsageSink | None = None,
        max_retries: int = 4,
        backoff_base: float = 1.0,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._headers = {"x-goog-api-key": api_key, "Content-Type": "application/json"}
        self._embedding_model = embedding_model
        self._dims = embedding_dimensions
        self._limiter_for = limiter_for
        self._http = http or httpx.AsyncClient(timeout=60)
        self._usage_sink = usage_sink
        self._max_retries = max_retries
        self._backoff_base = backoff_base

    async def _post(self, path: str, body: dict, *, task: str, model: str, priority: Priority) -> dict:
        """POST through the priority queue, with exponential backoff on 429 / 5xx."""
        for attempt in range(self._max_retries + 1):
            await self._limiter_for(model).acquire(priority)
            resp = await self._http.post(f"{self._base_url}/{path}", json=body, headers=self._headers)
            if resp.status_code == 429 or resp.status_code >= 500:
                await self._record(task, model, Usage(), "rate_limited" if resp.status_code == 429 else "error")
                if attempt == self._max_retries:
                    raise AIError(f"Gemini {resp.status_code} after {attempt + 1} attempts")
                delay = self._backoff_base * 2**attempt + random.uniform(0, 0.25)
                log.warning("gemini_retry", status=resp.status_code, attempt=attempt, delay=delay)
                await asyncio.sleep(delay)
                continue
            if resp.status_code >= 400:
                await self._record(task, model, Usage(), "error")
                raise AIError(f"Gemini {resp.status_code}: {resp.text[:200]}")
            data = resp.json()
            meta = data.get("usageMetadata", {})
            await self._record(
                task, model,
                Usage(meta.get("promptTokenCount", 0), meta.get("candidatesTokenCount", 0)), "ok",
            )
            return data
        raise AIError("unreachable")

    async def _record(self, task: str, model: str, usage: Usage, status: str) -> None:
        if self._usage_sink:
            await self._usage_sink(task, model, usage, status)

    @staticmethod
    def _text(data: dict) -> str:
        try:
            parts = data["candidates"][0]["content"]["parts"]
        except (KeyError, IndexError) as exc:
            raise AIError("Gemini response has no content") from exc
        return "".join(p.get("text", "") for p in parts)

    async def generate(
        self, prompt: str, *, model: str, task: str, priority: Priority = Priority.ENRICHMENT,
        system: str | None = None,
    ) -> str:
        body = self._body(prompt, system, {"temperature": 0})
        data = await self._post(f"models/{model}:generateContent", body, task=task, model=model, priority=priority)
        return self._text(data)

    async def generate_json(
        self, prompt: str, schema: type[T], *, model: str, task: str,
        priority: Priority = Priority.ENRICHMENT, system: str | None = None,
    ) -> T:
        config = {"temperature": 0, "responseMimeType": "application/json",
                  "responseJsonSchema": schema.model_json_schema()}
        data = await self._post(
            f"models/{model}:generateContent", self._body(prompt, system, config),
            task=task, model=model, priority=priority,
        )
        try:
            return schema.model_validate(json.loads(self._text(data)))
        except ValueError as exc:  # invalid JSON or outside the Pydantic schema
            raise AIError(f"invalid structured output: {exc}") from exc

    async def embed(
        self, texts: list[str], *, task: str, priority: Priority = Priority.ENRICHMENT
    ) -> list[list[float]]:
        if not texts:
            return []
        model = self._embedding_model
        body = {"requests": [
            {"model": f"models/{model}", "content": {"parts": [{"text": t}]},
             "outputDimensionality": self._dims}
            for t in texts
        ]}
        data = await self._post(f"models/{model}:batchEmbedContents", body, task=task, model=model, priority=priority)
        return [e["values"] for e in data["embeddings"]]

    async def stream_chat(
        self, messages: list[tuple[str, str]], *, model: str, task: str, system: str,
        priority: Priority = Priority.FOR_YOU, max_output_tokens: int = 1024, retries: int = 1,
        wait_seconds: float = 25,
    ) -> AsyncIterator[str]:
        """Streams the answer to a conversation of (role, text) turns, role "user" or "model".
        429 / 5xx are retried only before the first chunk: once text is flowing it cannot restart.
        A reader is waiting, so a model that stays silent for `wait_seconds` counts as failed."""
        body = {
            "contents": [{"role": role, "parts": [{"text": text}]} for role, text in messages],
            "systemInstruction": {"parts": [{"text": system}]},
            "generationConfig": {"temperature": 0.4, "maxOutputTokens": max_output_tokens},
        }
        url = f"{self._base_url}/models/{model}:streamGenerateContent?alt=sse"
        timeout = httpx.Timeout(10, read=wait_seconds)
        for attempt in range(retries + 1):
            await self._limiter_for(model).acquire(priority)
            try:
                async with self._http.stream("POST", url, json=body, headers=self._headers, timeout=timeout) as resp:
                    if resp.status_code < 400:
                        usage = Usage()
                        async for line in resp.aiter_lines():
                            if not line.startswith("data:"):
                                continue
                            data = json.loads(line[5:])
                            if meta := data.get("usageMetadata"):
                                usage = Usage(meta.get("promptTokenCount", 0), meta.get("candidatesTokenCount", 0))
                            parts = (data.get("candidates") or [{}])[0].get("content", {}).get("parts", [])
                            if text := "".join(p.get("text", "") for p in parts if not p.get("thought")):
                                yield text
                        await self._record(task, model, usage, "ok")
                        return
                    status = resp.status_code
                    detail = (await resp.aread()).decode(errors="replace")[:200]
            except httpx.HTTPError as exc:  # timeout or dropped connection
                await self._record(task, model, Usage(), "error")
                raise AIError(f"Gemini stream failed: {type(exc).__name__}") from exc
            retryable = status == 429 or status >= 500
            await self._record(task, model, Usage(), "rate_limited" if status == 429 else "error")
            if not retryable or attempt == retries:
                raise AIError(f"Gemini {status}: {detail}")
            await asyncio.sleep(self._backoff_base * 2**attempt + random.uniform(0, 0.25))

    @staticmethod
    def _body(prompt: str, system: str | None, config: dict) -> dict:
        body: dict = {"contents": [{"role": "user", "parts": [{"text": prompt}]}], "generationConfig": config}
        if system:
            body["systemInstruction"] = {"parts": [{"text": system}]}
        return body


__all__ = ["GeminiClient", "QuotaExhausted"]
