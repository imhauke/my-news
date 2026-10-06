"""The brief of the day: a few sentences at the top of the front page on the most important
stories, world affairs and technology together, in English and Spanish.

It is refreshed by the worker only when the top stories have changed (and it is at least 30
minutes old) or when it is more than three hours old, so it costs a few requests a day."""

from datetime import UTC, datetime, timedelta

import structlog
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.ai.base import AIClient, AIError, Priority, QuotaExhausted
from app.config import get_settings
from app.db import SessionLocal
from app.models import Article, Digest
from app.ranking import rank_recent

log = structlog.get_logger()

KIND = "general"  # the digests table keeps a kind column; there is a single brief now
PER_SIDE = 7  # stories from each side: world affairs and technology
MIN_AGE = timedelta(minutes=30)
FLASH_COOLDOWN = timedelta(hours=1)
_flash_paused_until = datetime.min.replace(tzinfo=UTC)
MAX_AGE = timedelta(hours=3)

SYSTEM = """You write the brief at the top of a news front page, for a busy reader who follows both
world affairs and technology. You get the day's most important stories (headline and, when
available, a description).
Write 5 or 6 sentences, at most 140 words:
- Open with the single most important development, whatever its area.
- Cover both sides of the day: world affairs (geopolitics, economy) and technology (AI, chips,
  security, the tech industry). Group related stories.
- Use only facts present in the input. Never add names, figures, causes or outcomes.
- Neutral, plain news language; no opinions, no hype, no bullet points, no headings.
Return summary_en (English) and summary_es (natural Spanish, Spain) with the same content.
Also return the same brief as 4 to 6 bullet points, bullets_en and bullets_es: one fact per
point, at most 18 words each, starting with the subject (who or what), no trailing period."""


class DigestOut(BaseModel):
    summary_en: str = Field(min_length=40, max_length=1400)
    summary_es: str = Field(min_length=40, max_length=1600)
    bullets_en: list[str] = Field(default_factory=list, max_length=7)
    bullets_es: list[str] = Field(default_factory=list, max_length=7)


def _is_tech(article: Article) -> bool:
    return article.source in ("ars", "hn") or article.section == "technology"


async def top_stories(session, now: datetime) -> list[Article]:
    """The most important stories of the last day (see app.ranking): the best PER_SIDE from world
    affairs and from technology, alternating, so the brief always speaks about both."""
    ranked = await rank_recent(session, now)
    tech = [a for a in ranked if _is_tech(a)]
    world = [a for a in ranked if not _is_tech(a)]
    picked: list[Article] = []
    for i in range(PER_SIDE):
        picked += [side[i] for side in (world, tech) if i < len(side)]
    return sorted(picked, key=ranked.index)


def build_prompt(stories: list[Article]) -> str:
    lines = []
    for i, a in enumerate(stories, start=1):
        lines.append(f"{i}. [{a.source}{'/' + a.section if a.section else ''}] {a.title}")
        if a.ai_summary_en or a.summary:
            lines.append(f"   {(a.ai_summary_en or a.summary or '')[:400]}")
    return "Today's most important stories, most important first:\n\n" + "\n".join(lines)


def _clean(bullets: list[str]) -> list[str]:
    return [b.strip().lstrip("•-–— ").rstrip(".").strip() for b in bullets if b.strip()][:6]


def is_due(last: Digest | None, top_ids: list[int], now: datetime) -> bool:
    if last is None:
        return True
    age = now - last.created_at
    if age >= MAX_AGE:
        return True
    return age >= MIN_AGE and set(top_ids[:5]) != set(last.article_ids[:5])


async def refresh_digest(ai: AIClient | None = None, now: datetime | None = None) -> int:
    """Writes the brief if it is due. Returns 1 when it was written, else 0."""
    cfg = get_settings()
    now = now or datetime.now(UTC)
    if ai is None:
        if not cfg.gemini_api_key:
            return 0
        from app.ai.factory import get_ai_client
        ai = get_ai_client()
    async with SessionLocal() as session:
        stories = await top_stories(session, now)
        if len(stories) < 3:
            return 0
        last = await session.scalar(
            select(Digest).where(Digest.kind == KIND).order_by(Digest.created_at.desc()).limit(1)
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
                    build_prompt(stories), DigestOut, model=model, task="digest",
                    priority=Priority.BRIEFING, system=SYSTEM,
                )
                used = model
                break
            except (AIError, QuotaExhausted) as exc:
                log.warning("digest_model_failed", model=model, error=str(exc))
                if model == cfg.gemini_model_flash and ("429" in str(exc) or isinstance(exc, QuotaExhausted)):
                    _flash_paused_until = now + FLASH_COOLDOWN
        if out is None or used is None:
            return 0
        session.add(Digest(
            kind=KIND, text_en=out.summary_en.strip(), text_es=out.summary_es.strip(),
            bullets_en=_clean(out.bullets_en), bullets_es=_clean(out.bullets_es), article_ids=ids, model=used,
        ))
        await session.commit()
        log.info("digest_done", stories=len(ids), model=used)
        return 1
