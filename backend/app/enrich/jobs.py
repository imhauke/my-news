"""Enrichment jobs: excerpt from the original page and stage 0 with Gemini."""

import asyncio
from datetime import UTC, datetime, timedelta

import structlog
from sqlalchemy import or_, select

from app.ai.base import AIClient, AIError, Priority, QuotaExhausted
from app.config import get_settings
from app.db import SessionLocal
from app.enrich.article_text import extract_article_text
from app.enrich.meta import extract_description, extract_image
from app.enrich.stage0 import SCORE_VERSION, EnrichmentBatch, ScoreBatch, build_prompt, rescore_prompt, system_prompt
from app.ingest.fetch import make_client
from app.models import Article

log = structlog.get_logger()
BATCH_SIZE = 10  # each item may carry up to 2,500 characters of article text
MAX_PER_RUN = 100
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; MyNews/0.1; +https://github.com/imhauke/my-news)"}


def _readable(article: Article) -> bool:
    """Reuters article pages reject automated requests (HTTP 401), and Ask HN posts link to the
    thread itself: neither has an article page to read."""
    return article.source != "reuters" and not article.url.startswith("https://news.ycombinator.com/")


async def fetch_article_texts(articles: list[Article]) -> dict[int, str]:
    """Reads the opening paragraphs of each original page concurrently. Nothing is stored."""
    cfg = get_settings()
    sem = asyncio.Semaphore(cfg.http_concurrency)
    texts: dict[int, str] = {}

    async def one(article: Article, client) -> None:
        try:
            async with sem:
                resp = await client.get(article.url, headers=HEADERS)
            if resp.status_code == 200 and "html" in resp.headers.get("content-type", ""):
                if text := extract_article_text(resp.text):
                    texts[article.id] = text
        except Exception as exc:  # noqa: BLE001 — an unreachable page just means no article text
            log.debug("article_text_failed", url=article.url, error=str(exc))

    async with make_client(cfg.http_timeout_seconds) as client:
        await asyncio.gather(*(one(a, client) for a in articles if _readable(a)))
    return texts


async def fetch_page_meta(limit: int = 60) -> None:
    """Reads the linked page once per article to fill what the feed lacks: the excerpt
    (og:description) and the lead image (og:image). Mostly Hacker News links.
    Reuters article pages reject automated requests (HTTP 401), so they are skipped."""
    cfg = get_settings()
    async with SessionLocal() as session:
        articles = (await session.execute(
            select(Article).where(
                or_(Article.summary.is_(None), Article.image_url.is_(None)),
                Article.meta_fetched_at.is_(None), Article.source != "reuters", Article.duplicate_of.is_(None),
                ~Article.url.startswith("https://news.ycombinator.com/"),
            ).order_by(Article.published_at.desc()).limit(limit)
        )).scalars().all()
        if not articles:
            return
        sem = asyncio.Semaphore(cfg.http_concurrency)

        async def one(article: Article, client) -> None:
            try:
                async with sem:
                    resp = await client.get(article.url, headers=HEADERS)
                if resp.status_code == 200 and "html" in resp.headers.get("content-type", ""):
                    article.summary = article.summary or extract_description(resp.text)
                    article.image_url = article.image_url or extract_image(resp.text, str(resp.url))
            except Exception as exc:  # noqa: BLE001 — one dead page does not stop the rest
                log.debug("meta_failed", url=article.url, error=str(exc))
            article.meta_fetched_at = datetime.now(UTC)

        async with make_client(cfg.http_timeout_seconds) as client:
            await asyncio.gather(*(one(a, client) for a in articles))
        await session.commit()
        log.info("meta_done", checked=len(articles), images=sum(1 for a in articles if a.image_url))


async def enrich_articles(ai: AIClient | None = None, *, read_articles: bool = True) -> int:
    """Enriches pending articles in batches, newest first.
    If the quota runs out it stops; the rest is processed on the next run."""
    cfg = get_settings()
    if ai is None:
        if not cfg.gemini_api_key:
            log.info("enrich_skipped", reason="no GEMINI_API_KEY")
            return 0
        from app.ai.factory import get_ai_client
        ai = get_ai_client()

    done = 0
    seen: set[int] = set()
    async with SessionLocal() as session:
        pending = (await session.execute(
            # Pending: never enriched, or enriched before headline translation existed.
            select(Article).where(
                or_(Article.enriched_at.is_(None), Article.title_es.is_(None)), Article.duplicate_of.is_(None)
            )
            .order_by(Article.published_at.desc()).limit(MAX_PER_RUN)
        )).scalars().all()
        by_id = {a.id: a for a in pending}
        bodies = await fetch_article_texts(list(pending)) if read_articles else {}
        for start in range(0, len(pending), BATCH_SIZE):
            batch = pending[start:start + BATCH_SIZE]
            prompt = build_prompt([
                {"id": a.id, "source": a.source, "section": a.section, "title": a.title, "summary": a.summary,
                 "body": bodies.get(a.id)}
                for a in batch
            ])
            try:
                result = await ai.generate_json(
                    prompt, EnrichmentBatch, model=cfg.gemini_model_lite, task="enrich",
                    priority=Priority.ENRICHMENT, system=system_prompt(datetime.now(UTC).date()),
                )
            except QuotaExhausted:
                log.warning("enrich_quota_exhausted", remaining=len(pending) - start)
                break
            except AIError as exc:
                log.warning("enrich_batch_failed", error=str(exc))
                continue
            now = datetime.now(UTC)
            for item in result.items:
                article = by_id.get(item.id)
                if article is None or article.id in seen:
                    continue  # id invented or repeated by the model
                seen.add(article.id)
                article.title_es = item.title_es.strip()
                # Without an excerpt or article text (Reuters pages are not readable) the model could only
                # restate the headline, so no description is stored.
                has_context = bool(article.summary or bodies.get(article.id))
                article.ai_summary_en = (item.summary_en.strip() or None) if has_context else None
                article.ai_summary_es = (item.summary_es.strip() or None) if has_context else None
                article.topics = [t.strip().lower() for t in item.topics if t.strip()]
                article.topics_es = [t.strip().lower() for t in item.topics_es if t.strip()]
                article.global_score = item.importance / 100
                article.score_version = SCORE_VERSION
                article.enriched_at = now
                done += 1
            await session.commit()
    log.info("enrich_done", enriched=done)
    return done


RESCORE_BATCH = 25
RESCORE_WINDOW = timedelta(hours=48)


async def rescore_recent(ai: AIClient | None = None) -> int:
    """Re-rates the stories still eligible for the front lane that were scored with older
    criteria (score_version), so a change to stage0.IMPORTANCE shows at once. Older stories keep
    their score."""
    cfg = get_settings()
    if ai is None:
        if not cfg.gemini_api_key:
            return 0
        from app.ai.factory import get_ai_client
        ai = get_ai_client()
    now = datetime.now(UTC)
    done = 0
    async with SessionLocal() as session:
        stale = (await session.scalars(
            select(Article).where(
                Article.enriched_at.is_not(None), Article.duplicate_of.is_(None),
                Article.score_version < SCORE_VERSION, Article.published_at > now - RESCORE_WINDOW,
            ).order_by(Article.published_at.desc()).limit(MAX_PER_RUN)
        )).all()
        by_id = {a.id: a for a in stale}
        for start in range(0, len(stale), RESCORE_BATCH):
            batch = stale[start:start + RESCORE_BATCH]
            prompt = build_prompt([
                {"id": a.id, "source": a.source, "section": a.section, "title": a.title,
                 "summary": a.ai_summary_en or a.summary}
                for a in batch
            ])
            try:
                result = await ai.generate_json(
                    prompt, ScoreBatch, model=cfg.gemini_model_lite, task="rescore",
                    priority=Priority.ENRICHMENT, system=rescore_prompt(now.date()),
                )
            except QuotaExhausted:
                break
            except AIError as exc:
                log.warning("rescore_batch_failed", error=str(exc))
                continue
            for item in result.items:
                if (article := by_id.get(item.id)) and article.score_version < SCORE_VERSION:
                    article.global_score = item.importance / 100
                    article.score_version = SCORE_VERSION
                    done += 1
            await session.commit()
    if done:
        log.info("rescore_done", rescored=done)
    return done
