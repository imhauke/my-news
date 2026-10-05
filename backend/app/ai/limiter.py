"""Per-model rate limiter: token bucket (per minute) + daily counter + priority queue.

A limit of 0 disables it; then only the exponential backoff on 429 protects the quota."""

import asyncio
import heapq
import itertools
import time
from collections.abc import Callable
from datetime import datetime
from zoneinfo import ZoneInfo

from app.ai.base import Priority, QuotaExhausted

PACIFIC = ZoneInfo("America/Los_Angeles")  # Google resets the daily counter at midnight Pacific time


def _pacific_day() -> str:
    return datetime.now(PACIFIC).strftime("%Y-%m-%d")


class RateLimiter:
    def __init__(
        self,
        requests_per_minute: int,
        requests_per_day: int,
        *,
        clock: Callable[[], float] = time.monotonic,
        day: Callable[[], str] = _pacific_day,
    ) -> None:
        self.rpm = requests_per_minute
        self.rpd = requests_per_day
        self._clock = clock
        self._day = day
        self._tokens = float(requests_per_minute)
        self._last_refill = clock()
        self._current_day = day()
        self._used_today = 0
        self._waiters: list[tuple[int, int, asyncio.Future[None]]] = []
        self._seq = itertools.count()
        self._pump: asyncio.Task[None] | None = None

    @property
    def used_today(self) -> int:
        self._roll_day()
        return self._used_today

    @property
    def remaining_today(self) -> int | None:
        return None if self.rpd <= 0 else max(self.rpd - self.used_today, 0)

    def _roll_day(self) -> None:
        today = self._day()
        if today != self._current_day:
            self._current_day, self._used_today = today, 0

    def _refill(self) -> None:
        now = self._clock()
        self._tokens = min(self.rpm, self._tokens + (now - self._last_refill) * self.rpm / 60)
        self._last_refill = now

    async def acquire(self, priority: Priority = Priority.ENRICHMENT) -> None:
        """Waits for a slot in priority order. Raises QuotaExhausted when the day's quota is used up."""
        self._roll_day()
        if 0 < self.rpd <= self._used_today:
            raise QuotaExhausted("daily quota exhausted")
        if self.rpm <= 0:  # no per-minute limit: no queue
            self._used_today += 1
            return
        fut: asyncio.Future[None] = asyncio.get_running_loop().create_future()
        heapq.heappush(self._waiters, (int(priority), next(self._seq), fut))
        if self._pump is None or self._pump.done():
            self._pump = asyncio.create_task(self._run())
        await fut

    async def _run(self) -> None:
        while self._waiters:
            self._roll_day()
            if 0 < self.rpd <= self._used_today:
                while self._waiters:
                    _, _, fut = heapq.heappop(self._waiters)
                    if not fut.done():
                        fut.set_exception(QuotaExhausted("daily quota exhausted"))
                return
            self._refill()
            if self._tokens >= 1:
                _, _, fut = heapq.heappop(self._waiters)
                if fut.done():  # cancelled by the caller
                    continue
                self._tokens -= 1
                self._used_today += 1
                fut.set_result(None)
            else:
                await asyncio.sleep((1 - self._tokens) * 60 / self.rpm)
