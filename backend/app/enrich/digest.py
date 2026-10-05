"""Overviews of the day: four or five sentences on the most relevant stories, in English and
Spanish, in three flavours — general (everything), world (geopolitics) and tech.

Each is refreshed by the worker only when its top stories have changed (and it is at least 30
minutes old) or when it is more than three hours old, so they cost a few requests a day."""

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
FLASH_COOLDOWN = timedelta(hours=1)
_flash_paused_until = datetime.min.replace(tzinfo=UTC)
MAX_AGE = timedelta(hours=3)

KINDS = ("general", "world", "tech")

# Which stories each overview draws from.
SCOPES = {
    "general": None,
    "world": and_(Article.source == "reuters", Article.section == "world"),
    "tech": or_(Article.source.in_(("ars", "hn")), and_(Article.source == "reuters", Article.section == "technology")),
}

FOCUS = {
    "general": "Cover the whole day across topics.",
    "world": "Focus on geopolitics and world affairs.",
    "tech": "Focus on technology: AI, software, hardware, security and the tech industry.",
}

SYSTEM = """You write the short overview at the top of a news front page.
You get the day's most relevant stories (headline and, when available, a description).
Write 4 or 5 sentences, at most 110 words, that tell a busy reader what matters today:
- Group related stories; lead with the most important development.
- Use only facts present in the input. Never add names, figures, causes or outcomes.
- Neutral, plain news language; no opinions, no hype, no bullet points, no headings.
Return summary_en (English) and summary_es (natural Spanish, Spain) with the same content.
Also return the same overview as 3 to 5 bullet points, bullets_en and bullets_es: one fact per
point, at most 16 words each, starting with the subject (who or what), no trailing period."""


class DigestOut(BaseModel):
    summary_en: str = Field(min_length=40, max_length=1200)
    summary_es: str = Field(min_length=40, max_length=1400)
    bullets_en: list[str] = Field(default_factory=list, max_length=6)
    bullets_es: list[str] = Field(default_factory=list, max_length=6)


async def top_stories(session, now: datetime, kind: str = "general") -> list[Article]:
    """Highest global relevance of the last day (HN /front covers the previous day: 48 h) within
    the overview's scope, with at most PER_SOURCE_CAP from one source so it spans the page."""
    recent = or_(
        Article.published_at > now - timedelta(hours=24),
        and_(Article.source == "hn", Article.published_at > now - timedelta(hours=48)),
    )
    query = select(Article).where(Article.duplicate_of.is_(None), Article.global_score.is_not(None), recent)
    if SCOPES[kind] is not None:
        query = query.where(SCOPES[kind])
    rows = (await session.scalars(
        query.order_by(Article.global_score.desc(), Article.published_at.desc()).limit(TOP_STORIES * 4)
    )).all()
    cap = PER_SOURCE_CAP if kind == "general" else TOP_STORIES  # a single-source scope keeps them all
    picked, counts = [], {}
    for a in rows:
        if counts.get(a.source, 0) < cap:
            picked.append(a)
            counts[a.source] = counts.get(a.source, 0) + 1
        if len(picked) == TOP_STORIES:
            break
    return picked


def build_prompt(stories: list[Article], kind: str = "general") -> str:
    lines = [FOCUS[kind], ""]
    for i, a in enumerate(stories, start=1):
        lines.append(f"{i}. [{a.source}] {a.title}")
        if a.ai_summary_en or a.summary:
            lines.append(f"   {(a.ai_summary_en or a.summary or '')[:400]}")
    return "Today's most relevant stories:\n\n" + "\n".join(lines)


def _clean(bullets: list[str]) -> list[str]:
    return [b.strip().lstrip("•-–— ").rstrip(".").strip() for b in bullets if b.strip()][:5]


def is_due(last: Digest | None, top_ids: list[int], now: datetime) -> bool:
    if last is None:
        return True
    age = now - last.created_at
    if age >= MAX_AGE:
        return True
    return age >= MIN_AGE and set(top_ids[:5]) != set(last.article_ids[:5])


async def refresh_digest(ai: AIClient | None = None, now: datetime | None = None) -> int:
    """Writes every overview that is due. Returns how many were written."""
    cfg = get_settings()
    now = now or datetime.now(UTC)
    if ai is None:
        if not cfg.gemini_api_key:
            return 0
        from app.ai.factory import get_ai_client
        ai = get_ai_client()
    written = 0
    for kind in KINDS:
        written += await _refresh_kind(ai, kind, now)
    return written


async def _refresh_kind(ai: AIClient, kind: str, now: datetime) -> int:
    cfg = get_settings()
    async with SessionLocal() as session:
        stories = await top_stories(session, now, kind)
        if len(stories) < 3:
            return 0
        last = await session.scalar(
            select(Digest).where(Digest.kind == kind).order_by(Digest.created_at.desc()).limit(1)
        )
        ids = [a.id for a in stories]
        if not is_due(last, ids, now):
            return 0
        # Flash writes better prose; if it is overloaded or out of quota, Flash-Lite still delivers.
        # After Flash runs out of quota (429) it is skipped for a while instead of being retried.
        global _flash_paused_until
        models = [cfg.gemini_model_flash, cfg.gemini_model_lite]
        if now < _flash_paused_until:
            models = [cfg.gemini_model_lite]
        out, used = None, None
        for model in models:
            try:
                out = await ai.generate_json(
                    build_prompt(stories, kind), DigestOut, model=model, task=f"digest_{kind}",
                    priority=Priority.BRIEFING, system=SYSTEM,
                )
                used = model
                break
            except (AIError, QuotaExhausted) as exc:
                log.warning("digest_model_failed", kind=kind, model=model, error=str(exc))
                if model == cfg.gemini_model_flash and ("429" in str(exc) or isinstance(exc, QuotaExhausted)):
                    _flash_paused_until = now + FLASH_COOLDOWN
        if out is None or used is None:
            return 0
        session.add(Digest(
            kind=kind, text_en=out.summary_en.strip(), text_es=out.summary_es.strip(),
            bullets_en=_clean(out.bullets_en), bullets_es=_clean(out.bullets_es), article_ids=ids, model=used,
        ))
        await session.commit()
        log.info("digest_done", kind=kind, stories=len(ids), model=used)
        return 1
