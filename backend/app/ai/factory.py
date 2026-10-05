"""Construye el cliente de IA de la app: un limitador por modelo y registro de uso en ai_usage."""

from functools import lru_cache

from app.ai.base import Usage
from app.ai.gemini import GeminiClient
from app.ai.limiter import RateLimiter
from app.config import get_settings
from app.db import SessionLocal
from app.models import AIUsage

_limiters: dict[str, RateLimiter] = {}


def _limiter_for(model: str) -> RateLimiter:
    cfg = get_settings()
    return _limiters.setdefault(model, RateLimiter(cfg.gemini_rpm, cfg.gemini_rpd))


async def record_usage(task: str, model: str, usage: Usage, status: str) -> None:
    async with SessionLocal() as session:
        session.add(AIUsage(task=task, model=model, input_tokens=usage.input_tokens,
                            output_tokens=usage.output_tokens, status=status))
        await session.commit()


@lru_cache
def get_ai_client() -> GeminiClient:
    cfg = get_settings()
    return GeminiClient(
        api_key=cfg.gemini_api_key, base_url=cfg.gemini_base_url,
        embedding_model=cfg.gemini_model_embedding, embedding_dimensions=cfg.embedding_dimensions,
        limiter_for=_limiter_for, usage_sink=record_usage,
    )
