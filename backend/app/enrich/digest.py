"""Daily overview: four or five sentences on the most relevant stories, in English and Spanish.

Refreshed by the worker only when the top stories have changed (and the last overview is at
least 30 minutes old) or when it is more than three hours old, so it costs a few requests a day."""

from datetime import UTC, datetime, timedelta

import structlog
from pydantic import BaseModel, Field
from sqlalchemy import and_, or_, select

from app.ai.base import AIClient, AIError, Priority, QuotaExhausted
from app.config import get_settings
from app.db import SessionLocal
from app.models import Article, Digest

log = structlog.get_logger()

TOP_STORIES = 12
PER_SOURCE_CAP = 5
MIN_AGE = timedelta(minutes=30)
MAX_AGE = timedelta(hours=3)

SYSTEM = """You write the short overview at the top of a news front page.
You get the day's most relevant stories (headline and, when available, a description).
Write 4 or 5 sentences, at most 110 words, that tell a busy reader what matters today:
- Group related stories; lead with the most important development.
- Use only facts present in the input. Never add names, figures, causes or outcomes.
- Neutral, plain news language; no opinions, no hype, no bullet points, no headings.
Return summary_en (English) and summary_es (natural Spanish, Spain) with the same content."""


class DigestOut(BaseModel):
    summary_en: str = Field(min_length=40, max_length=1200)
    summary_es: str = Field(min_length=40, max_length=1400)


async def top_stories(session, now: datetime) -> list[Article]:
    """Highest global relevance of the last day (HN /front covers the previous day: 48 h),
    with at most PER_SOURCE_CAP from one source so the overview spans the whole page."""
    recent = or_(
        Article.published_at > now - timedelta(hours=24),
        and_(Article.source == "hn", Article.published_at > now - timedelta(hours=48)),
    )
    rows = (await session.scalars(
        select(Article).where(Article.duplicate_of.is_(None), Article.global_score.is_not(None), recent)
        .order_by(Article.global_score.desc(), Article.published_at.desc()).limit(TOP_STORIES * 4)
    )).all()
    picked, counts = [], {}
    for a in rows:
        if counts.get(a.source, 0) < PER_SOURCE_CAP:
            picked.append(a)
            counts[a.source] = counts.get(a.source, 0) + 1
        if len(picked) == TOP_STORIES:
            break
    return picked


def build_prompt(stories: list[Article]) -> str:
    lines = []
    for i, a in enumerate(stories, start=1):
        lines.append(f"{i}. [{a.source}] {a.title}")
        if a.ai_summary_en or a.summary:
            lines.append(f"   {(a.ai_summary_en or a.summary or '')[:400]}")
    return "Today's most relevant stories:\n\n" + "\n".join(lines)


def is_due(last: Digest | None, top_ids: list[int], now: datetime) -> bool:
    if last is None:
        return True
    age = now - last.created_at
    if age >= MAX_AGE:
        return True
    return age >= MIN_AGE and set(top_ids[:5]) != set(last.article_ids[:5])


async def refresh_digest(ai: AIClient | None = None, now: datetime | None = None) -> bool:
    """Writes a new overview if one is due. Returns whether it did."""
    cfg = get_settings()
    now = now or datetime.now(UTC)
    if ai is None:
        if not cfg.gemini_api_key:
            return False
        from app.ai.factory import get_ai_client
        ai = get_ai_client()
    async with SessionLocal() as session:
        stories = await top_stories(session, now)
        if len(stories) < 3:
            return False
        last = await session.scalar(select(Digest).order_by(Digest.created_at.desc()).limit(1))
        ids = [a.id for a in stories]
        if not is_due(last, ids, now):
            return False
        # Flash writes better prose; if it is overloaded or out of quota, Flash-Lite still delivers.
        out, used = None, None
        for model in (cfg.gemini_model_flash, cfg.gemini_model_lite):
            try:
                out = await ai.generate_json(
                    build_prompt(stories), DigestOut, model=model, task="digest",
                    priority=Priority.BRIEFING, system=SYSTEM,
                )
                used = model
                break
            except (AIError, QuotaExhausted) as exc:
                log.warning("digest_model_failed", model=model, error=str(exc))
        if out is None or used is None:
            return False
        session.add(Digest(text_en=out.summary_en.strip(), text_es=out.summary_es.strip(), article_ids=ids,
                           model=used))
        await session.commit()
        log.info("digest_done", stories=len(ids))
        return True
