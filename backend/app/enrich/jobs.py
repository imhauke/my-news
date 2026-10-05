"""Trabajos de enriquecimiento: extracto de la página original y etapa 0 con Gemini."""

import asyncio
from datetime import UTC, datetime

import structlog
from sqlalchemy import or_, select

from app.ai.base import AIClient, AIError, Priority, QuotaExhausted
from app.config import get_settings
from app.db import SessionLocal
from app.enrich.meta import extract_description
from app.enrich.stage0 import SYSTEM, EnrichmentBatch, build_prompt
from app.ingest.fetch import make_client
from app.models import Article

log = structlog.get_logger()
BATCH_SIZE = 25
MAX_PER_RUN = 100


async def fetch_meta_descriptions(limit: int = 60) -> None:
    """Para HN (y cualquier fuente sin extracto) lee og:description de la página enlazada.
    Reuters llega vía enlaces de Google News que no se pueden resolver sin JS: se omite."""
    cfg = get_settings()
    async with SessionLocal() as session:
        articles = (await session.execute(
            select(Article).where(
                Article.summary.is_(None), Article.meta_fetched_at.is_(None),
                Article.source != "reuters", Article.duplicate_of.is_(None),
                ~Article.url.startswith("https://news.ycombinator.com/"),
            ).order_by(Article.published_at.desc()).limit(limit)
        )).scalars().all()
        if not articles:
            return
        sem = asyncio.Semaphore(cfg.http_concurrency)
        headers = {"User-Agent": "Mozilla/5.0 (compatible; MyNews/0.1; +https://github.com/imhauke/my-news)"}

        async def one(article: Article, client) -> None:
            try:
                async with sem:
                    resp = await client.get(article.url, headers=headers)
                if resp.status_code == 200 and "html" in resp.headers.get("content-type", ""):
                    article.summary = extract_description(resp.text)
            except Exception as exc:  # noqa: BLE001 — una página caída no frena al resto
                log.debug("meta_failed", url=article.url, error=str(exc))
            article.meta_fetched_at = datetime.now(UTC)

        async with make_client(cfg.http_timeout_seconds) as client:
            await asyncio.gather(*(one(a, client) for a in articles))
        await session.commit()
        log.info("meta_done", checked=len(articles), found=sum(1 for a in articles if a.summary))


async def enrich_articles(ai: AIClient | None = None) -> int:
    """Enriquece en lotes los artículos pendientes, los más recientes primero.
    Si se agota la cuota, para: lo pendiente se procesa en la siguiente ejecución."""
    cfg = get_settings()
    if ai is None:
        if not cfg.gemini_api_key:
            log.info("enrich_skipped", reason="sin GEMINI_API_KEY")
            return 0
        from app.ai.factory import get_ai_client
        ai = get_ai_client()

    done = 0
    seen: set[int] = set()
    async with SessionLocal() as session:
        pending = (await session.execute(
            # Pendientes: sin enriquecer, o enriquecidos antes de que existiera la traducción del titular.
            select(Article).where(
                or_(Article.enriched_at.is_(None), Article.title_es.is_(None)), Article.duplicate_of.is_(None)
            )
            .order_by(Article.published_at.desc()).limit(MAX_PER_RUN)
        )).scalars().all()
        by_id = {a.id: a for a in pending}
        for start in range(0, len(pending), BATCH_SIZE):
            batch = pending[start:start + BATCH_SIZE]
            prompt = build_prompt([
                {"id": a.id, "source": a.source, "section": a.section, "title": a.title, "summary": a.summary}
                for a in batch
            ])
            try:
                result = await ai.generate_json(
                    prompt, EnrichmentBatch, model=cfg.gemini_model_lite, task="enrich",
                    priority=Priority.ENRICHMENT, system=SYSTEM,
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
                    continue  # id inventado o repetido por el modelo
                seen.add(article.id)
                article.title_es = item.title_es.strip()
                # Sin extracto de la fuente (Reuters vía Google News) no hay descripción posible:
                # el modelo solo repetiría el titular, así que no se guarda nada.
                has_excerpt = bool(article.summary)
                article.ai_summary_en = (item.summary_en.strip() or None) if has_excerpt else None
                article.ai_summary_es = (item.summary_es.strip() or None) if has_excerpt else None
                article.topics = [t.strip().lower() for t in item.topics if t.strip()]
                article.topics_es = [t.strip().lower() for t in item.topics_es if t.strip()]
                article.global_score = item.global_score
                article.enriched_at = now
                done += 1
            await session.commit()
    log.info("enrich_done", enriched=done)
    return done
