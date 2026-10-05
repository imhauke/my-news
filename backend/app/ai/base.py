"""Common AI client interface: switching provider does not touch the rest of the code."""

from dataclasses import dataclass
from enum import IntEnum
from typing import Protocol, TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class Priority(IntEnum):
    """Lower value = higher priority (For You > HN analysis > enrichment > briefing)."""

    FOR_YOU = 0
    HN_ANALYSIS = 1
    ENRICHMENT = 2
    BRIEFING = 3


@dataclass(frozen=True)
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0


class AIError(Exception):
    pass


class QuotaExhausted(AIError):
    """Daily quota exhausted: the caller should degrade (e.g. rank with embeddings only)."""


class AIClient(Protocol):
    async def generate(
        self, prompt: str, *, model: str, task: str, priority: Priority = Priority.ENRICHMENT,
        system: str | None = None,
    ) -> str: ...

    async def generate_json(
        self, prompt: str, schema: type[T], *, model: str, task: str,
        priority: Priority = Priority.ENRICHMENT, system: str | None = None,
    ) -> T: ...

    async def embed(
        self, texts: list[str], *, task: str, priority: Priority = Priority.ENRICHMENT
    ) -> list[list[float]]: ...
