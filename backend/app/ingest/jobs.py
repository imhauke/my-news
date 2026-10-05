"""Trabajos de ingesta que ejecuta el worker."""

import asyncio
from datetime import UTC, datetime, timedelta

import httpx
import structlog
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import SessionLocal
from app.ingest import sources
from app.ingest.fetch import get_with_retry, make_client
from app.ingest.service import upsert_articles, upsert_comments
from app.models import Article

log = structlog.get_logger()

# Pasadas de comentarios mientras el hilo está vivo; después se congela (sección 3.4).
COMMENT_PASS_HOURS = (2, 8, 24, 48)
COMMENT_MIN_POINTS = 100
COMMENT_MIN_COMMENTS = 30


async def ingest_hn() -> None:
    """Historias de /front (portada del día anterior) con sus datos de la API oficial."""
    cfg = get_settings()
    sem = asyncio.Semaphore(cfg.http_concurrency)
    async with make_client(cfg.http_timeout_seconds) as client:
        ids = sources.parse_hn_front((await get_with_retry(client, sources.HN_FRONT_URL, sem=sem)).text)
        responses = await asyncio.gather(
            *(get_with_retry(client, sources.HN_ITEM_URL.format(id=i), sem=sem) for i in ids),
            return_exceptions=True,
        )
    items = []
    for story_id, r in zip(ids, responses, strict=True):
        if isinstance(r, Exception):
            log.warning("hn_item_failed", story=story_id, error=str(r))
            continue
        if parsed := sources.parse_hn_item(r.json()):
            items.append(parsed)
    if not items:
        log.error("source_empty", source="hn")
        return
    async with SessionLocal() as session:
        log.info("ingest_done", source="hn", fetched=len(ids), **await upsert_articles(session, items))


async def _ingest_feeds(source: str, feeds: dict[str, list[str]], parse) -> None:
    cfg = get_settings()
    sem = asyncio.Semaphore(cfg.http_concurrency)
    pairs = [(section, url) for section, urls in feeds.items() for url in urls]
    async with make_client(cfg.http_timeout_seconds) as client:
        responses = await asyncio.gather(
            *(get_with_retry(client, url, sem=sem) for _, url in pairs), return_exceptions=True
        )
    items = []
    for (section, _), r in zip(pairs, responses, strict=True):
        if isinstance(r, Exception):
            log.warning("feed_failed", source=source, section=section, error=str(r))
            continue
        items.extend(parse(r.text, section))
    if not items:
        log.error("source_empty", source=source)  # alerta: la fuente dejó de devolver datos
        return
    async with SessionLocal() as session:
        log.info("ingest_done", source=source, fetched=len(items), **await upsert_articles(session, items))


async def ingest_ars() -> None:
    await _ingest_feeds("ars", sources.ARS_FEEDS, sources.parse_ars_feed)


async def ingest_reuters() -> None:
    feeds = {name: [sources.reuters_feed_url(q) for q in qs] for name, qs in sources.REUTERS_QUERIES.items()}
    await _ingest_feeds("reuters", feeds, sources.parse_reuters_feed)


async def refresh_hn_comments() -> None:
    """Descarga el árbol de los hilos relevantes cuando toca su siguiente pasada (2, 8, 24, 48 h)."""
    cfg = get_settings()
    now = datetime.now(UTC)
    async with SessionLocal() as session:
        candidates = (await session.execute(
            select(Article).where(
                Article.source == "hn",
                Article.comments_pass < len(COMMENT_PASS_HOURS),
                Article.published_at > now - timedelta(hours=COMMENT_PASS_HOURS[-1] + 6),
                or_(Article.hn_points >= COMMENT_MIN_POINTS, Article.hn_comment_count >= COMMENT_MIN_COMMENTS),
            )
        )).scalars().all()
        due = [
            a for a in candidates
            if now - a.published_at >= timedelta(hours=COMMENT_PASS_HOURS[a.comments_pass])
        ]
        sem = asyncio.Semaphore(2)  # Algolia: ser educados
        async with make_client(cfg.http_timeout_seconds) as client:
            for article in due:
                try:
                    count = await fetch_story_comments(session, article, client, sem)
                except Exception as exc:  # noqa: BLE001 — un hilo fallido no frena a los demás
                    log.warning("comments_failed", story=article.external_id, error=str(exc))
                    continue
                article.comments_pass += 1
                await session.commit()
                log.info("comments_done", story=article.external_id, comments=count,
                         pass_number=article.comments_pass)


async def fetch_story_comments(
    session: AsyncSession, article: Article, client: httpx.AsyncClient, sem: asyncio.Semaphore
) -> int:
    """Descarga el árbol completo del hilo desde Algolia y lo guarda (upsert + marca de borrados)."""
    resp = await get_with_retry(client, sources.ALGOLIA_ITEM_URL.format(id=article.external_id), sem=sem)
    comments = sources.flatten_algolia_tree(resp.json())
    await upsert_comments(session, int(article.external_id), comments)
    article.comments_fetched_at = datetime.now(UTC)
    await session.commit()
    return len(comments)
