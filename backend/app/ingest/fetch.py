"""Descarga concurrente con semáforo, timeouts y reintentos con espera exponencial."""

import asyncio
import random

import httpx
import structlog

log = structlog.get_logger()
USER_AGENT = "MyNews/0.1 (+https://github.com/imhauke/my-news)"


def make_client(timeout: float) -> httpx.AsyncClient:
    return httpx.AsyncClient(timeout=timeout, headers={"User-Agent": USER_AGENT}, follow_redirects=True)


def _retryable(status: int) -> bool:
    return status == 429 or status >= 500


async def get_with_retry(
    client: httpx.AsyncClient, url: str, *, sem: asyncio.Semaphore, retries: int = 3, backoff: float = 1.0
) -> httpx.Response:
    """GET con semáforo; reintenta errores de red, 429 y 5xx. Los 4xx restantes fallan de inmediato."""
    for attempt in range(retries + 1):
        try:
            async with sem:
                resp = await client.get(url)
            if not _retryable(resp.status_code):
                return resp.raise_for_status()
            err: Exception = httpx.HTTPStatusError(str(resp.status_code), request=resp.request, response=resp)
        except httpx.TransportError as exc:
            err = exc
        if attempt == retries:
            raise err
        delay = backoff * 2**attempt + random.uniform(0, 0.25)
        log.warning("fetch_retry", url=url, attempt=attempt, delay=round(delay, 2), error=str(err))
        await asyncio.sleep(delay)
    raise RuntimeError("unreachable")
