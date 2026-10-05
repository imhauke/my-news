"""Worker process: ingestion and enrichment scheduler. Run with `python -m app.worker`."""

import asyncio

import structlog
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.config import get_settings
from app.enrich import jobs as enrich
from app.ingest import jobs
from app.logging import configure_logging

log = structlog.get_logger()


async def enrich_pipeline() -> None:
    """First the excerpt from the original page; then Gemini uses it as context."""
    await enrich.fetch_meta_descriptions()
    await enrich.enrich_articles()


async def main() -> None:
    cfg = get_settings()
    configure_logging(cfg.log_level)
    if not cfg.scheduler_enabled:
        log.info("scheduler_disabled")
        await asyncio.Event().wait()

    scheduler = AsyncIOScheduler()
    opts = {"max_instances": 1, "coalesce": True}
    scheduler.add_job(jobs.ingest_hn, "interval", hours=3, id="hn", **opts)  # /front changes little
    scheduler.add_job(jobs.ingest_ars, "interval", minutes=90, id="ars", **opts)
    scheduler.add_job(jobs.ingest_reuters, "interval", minutes=90, id="reuters", **opts)
    scheduler.add_job(jobs.refresh_hn_comments, "interval", minutes=30, id="hn_comments", **opts)
    scheduler.add_job(enrich_pipeline, "interval", minutes=15, id="enrich", **opts)
    scheduler.start()

    # First run at startup, without waiting for the first interval.
    await asyncio.gather(jobs.ingest_hn(), jobs.ingest_ars(), jobs.ingest_reuters(), return_exceptions=True)
    await enrich_pipeline()
    log.info("worker_started")
    await asyncio.Event().wait()


if __name__ == "__main__":
    asyncio.run(main())
