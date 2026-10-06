"""Semantic search: the query is embedded with the same model as the stories, and pgvector returns
the stories whose vectors are closest (cosine). Close matches are kept; a small bonus favours
recent stories among similar ones."""

import math
from collections import OrderedDict
from datetime import UTC, datetime

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.base import AIClient, Priority
from app.chat import ChatGuard
from app.config import get_settings
from app.models import Article, Embedding

# Calibrated on real queries with gemini-embedding-2: related stories score about 0.60-0.80, while
# gibberish or a topic the site never covers tops out around 0.60-0.63 against everything.
MIN_BEST = 0.645  # if even the best match is below this, nothing is really about the query
MIN_SIMILARITY = 0.6
SPREAD = 0.08  # and each result must be close to the best match
RECENCY_BONUS = 0.03  # for a story published now, halving every RECENCY_HALF_LIFE_DAYS
RECENCY_HALF_LIFE_DAYS = 3
CANDIDATES = 60
QUERY_CACHE = 256

_vectors: OrderedDict[str, list[float]] = OrderedDict()
_guard: ChatGuard | None = None


def guard() -> ChatGuard:
    """Searches per visitor per hour and per day for the site: each new query costs one request."""
    global _guard
    if _guard is None:
        _guard = ChatGuard(per_hour=120, per_day=3000)
    return _guard


async def query_vector(ai: AIClient, query: str) -> list[float]:
    key = " ".join(query.lower().split())
    if key in _vectors:
        _vectors.move_to_end(key)
        return _vectors[key]
    (vector,) = await ai.embed([key], task="search", priority=Priority.FOR_YOU)
    _vectors[key] = vector
    if len(_vectors) > QUERY_CACHE:
        _vectors.popitem(last=False)
    return vector


async def search(session: AsyncSession, ai: AIClient, query: str, limit: int = 20,
                 now: datetime | None = None) -> list[Article]:
    now = now or datetime.now(UTC)
    vector = await query_vector(ai, query)
    distance = Embedding.vector.cosine_distance(vector)
    rows = (await session.execute(
        select(Article, distance.label("distance"))
        .join(Embedding, and_(Embedding.owner_type == "article", Embedding.owner_id == Article.id,
                              Embedding.model == get_settings().gemini_model_embedding))
        .where(Article.duplicate_of.is_(None))
        .order_by(distance).limit(CANDIDATES)
    )).all()
    if not rows:
        return []
    best = 1 - rows[0].distance
    if best < MIN_BEST:
        return []
    scored = []
    for article, d in rows:
        similarity = 1 - d
        if similarity < MIN_SIMILARITY or similarity < best - SPREAD:
            continue
        age_days = max((now - article.published_at).total_seconds() / 86400, 0)
        scored.append((similarity + RECENCY_BONUS * math.pow(0.5, age_days / RECENCY_HALF_LIFE_DAYS), article))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [a for _, a in scored[:limit]]
