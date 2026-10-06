"""Embeddings: a vector of what each story is about, so stories can be found by meaning.

One vector per story (headline, description and topics, in English), computed once with the
Gemini embedding model after enrichment. The model is multilingual, so a Spanish query finds
English stories."""

import structlog
from sqlalchemy import and_, select

from app.ai.base import AIClient, AIError, Priority, QuotaExhausted
from app.config import get_settings
from app.db import SessionLocal
from app.models import Article, Embedding

log = structlog.get_logger()

# The free tier counts every text against a per-minute limit: small runs every few minutes keep
# well within it (a day brings about 300 stories).
BATCH = 50  # texts per request
MAX_PER_RUN = 100


def article_text(article: Article) -> str:
    parts = [article.title]
    if description := article.ai_summary_en or article.summary:
        parts.append(description[:600])
    if article.topics:
        parts.append("Topics: " + ", ".join(article.topics))
    return "\n".join(parts)


async def embed_articles(ai: AIClient | None = None) -> int:
    """Embeds the enriched stories that have no vector yet, newest first. Returns how many."""
    cfg = get_settings()
    if ai is None:
        if not cfg.gemini_api_key:
            return 0
        from app.ai.factory import get_ai_client
        ai = get_ai_client()
    done = 0
    async with SessionLocal() as session:
        missing = (await session.scalars(
            select(Article)
            .outerjoin(Embedding, and_(Embedding.owner_type == "article", Embedding.owner_id == Article.id))
            .where(Embedding.owner_id.is_(None), Article.enriched_at.is_not(None), Article.duplicate_of.is_(None))
            .order_by(Article.published_at.desc()).limit(MAX_PER_RUN)
        )).all()
        for start in range(0, len(missing), BATCH):
            batch = missing[start:start + BATCH]
            try:
                vectors = await ai.embed([article_text(a) for a in batch], task="embed_articles",
                                         priority=Priority.ENRICHMENT)
            except QuotaExhausted:
                break
            except AIError as exc:
                log.warning("embed_batch_failed", error=str(exc))
                continue
            session.add_all(
                Embedding(owner_type="article", owner_id=a.id, model=cfg.gemini_model_embedding, vector=v)
                for a, v in zip(batch, vectors, strict=True)
            )
            await session.commit()
            done += len(batch)
    if done:
        log.info("embed_done", embedded=done)
    return done
