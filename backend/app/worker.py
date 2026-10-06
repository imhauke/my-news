"""Worker process: ingestion and enrichment scheduler. Run with `python -m app.worker`."""

import asyncio
from datetime import datetime

import structlog
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.config import get_settings
from app.enrich import jobs as enrich
from app.enrich.digest import refresh_digest
from app.ingest import jobs
from app.logging import configure_logging
from app.privacy import purge_job

log = structlog.get_logger()


async def enrich_pipeline() -> None:
    """First the excerpt from the original page; then Gemini uses it as context."""
    await enrich.fetch_page_meta()
    await enrich.enrich_articles()
    await enrich.rescore_recent()


async def refresh() -> None:
    """One full refresh: all sources concurrently, then enrichment of whatever is new, so a story
    gets its translated headline and description in the same pass that fetched it."""
    results = await asyncio.gather(
        jobs.ingest_hn(), jobs.ingest_ars(), jobs.ingest_reuters(), return_exceptions=True
    )
    for name, result in zip(("hn", "ars", "reuters"), results, strict=True):
        if isinstance(result, Exception):
            log.error("ingest_failed", source=name, error=str(result))
    await enrich_pipeline()
    await refresh_digest()


async def main() -> None:
    cfg = get_settings()
    configure_logging(cfg.log_level)
    if not cfg.scheduler_enabled:
        log.info("scheduler_disabled")
        await asyncio.Event().wait()

    # Everything is kept at most `refresh_minutes` old. A run that overruns the interval is not
    # stacked: the next one starts when it finishes (max_instances=1, coalesce).
    scheduler = AsyncIOScheduler()
    every = {"trigger": "interval", "minutes": cfg.refresh_minutes, "max_instances": 1, "coalesce": True,
             "next_run_time": datetime.now()}  # first run right away
    scheduler.add_job(refresh, id="refresh", **every)
    scheduler.add_job(jobs.refresh_hn_comments, id="hn_comments", **every)
    scheduler.add_job(purge_job, "interval", id="privacy_purge", hours=24, next_run_time=datetime.now())
    scheduler.start()
    log.info("worker_started", refresh_minutes=cfg.refresh_minutes)
    await asyncio.Event().wait()


if __name__ == "__main__":
    asyncio.run(main())
