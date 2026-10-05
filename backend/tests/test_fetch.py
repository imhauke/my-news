import asyncio

import httpx
import pytest
import respx

from app.ingest.fetch import get_with_retry

URL = "https://x.test/feed"


@respx.mock
async def test_retries_5xx_then_returns():
    respx.get(URL).mock(side_effect=[httpx.Response(503), httpx.Response(200, text="ok")])
    async with httpx.AsyncClient() as c:
        resp = await get_with_retry(c, URL, sem=asyncio.Semaphore(1), backoff=0.001)
    assert resp.text == "ok"


@respx.mock
async def test_4xx_fails_without_retry():
    route = respx.get(URL).mock(return_value=httpx.Response(404))
    async with httpx.AsyncClient() as c:
        with pytest.raises(httpx.HTTPStatusError):
            await get_with_retry(c, URL, sem=asyncio.Semaphore(1), backoff=0.001)
    assert route.call_count == 1
