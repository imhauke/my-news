import asyncio

import pytest

from app.ai.base import Priority, QuotaExhausted
from app.ai.limiter import RateLimiter


async def test_daily_quota_exhausted_raises():
    lim = RateLimiter(requests_per_minute=600, requests_per_day=2)
    await lim.acquire()
    await lim.acquire()
    with pytest.raises(QuotaExhausted):
        await lim.acquire()
    assert lim.remaining_today == 0


async def test_daily_counter_resets_on_new_pacific_day():
    day = ["2026-10-05"]
    lim = RateLimiter(600, 1, day=lambda: day[0])
    await lim.acquire()
    day[0] = "2026-10-06"
    await lim.acquire()  # no lanza: nuevo día


async def test_priority_order_when_bucket_is_empty():
    lim = RateLimiter(requests_per_minute=600, requests_per_day=100)
    lim._tokens = 0  # fuerza a encolar
    order: list[str] = []

    async def go(name: str, prio: Priority) -> None:
        await lim.acquire(prio)
        order.append(name)

    await asyncio.gather(
        go("briefing", Priority.BRIEFING), go("for_you", Priority.FOR_YOU), go("hn", Priority.HN_ANALYSIS)
    )
    assert order == ["for_you", "hn", "briefing"]


async def test_zero_limits_disable_the_limiter():
    lim = RateLimiter(requests_per_minute=0, requests_per_day=0)
    await asyncio.gather(*(lim.acquire() for _ in range(500)))
    assert lim.used_today == 500 and lim.remaining_today is None
