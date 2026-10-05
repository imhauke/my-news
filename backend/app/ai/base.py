"""Interfaz común del cliente de IA: cambiar de proveedor no toca el resto del código."""

from dataclasses import dataclass
from enum import IntEnum
from typing import Protocol, TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class Priority(IntEnum):
    """Menor valor = más prioridad (sección 3.1: Para ti > análisis HN > briefing)."""

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
    """Se agotó la cuota diaria: el llamador debe degradar (p. ej. puntuar solo con embeddings)."""


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
