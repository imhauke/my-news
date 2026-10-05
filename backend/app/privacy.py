"""Retention: reading history linked to a reader is kept for a year at most."""

from datetime import UTC, datetime, timedelta

import structlog
from sqlalchemy import delete, exists, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import SessionLocal
from app.models import ArticleFeedback, Event, User

log = structlog.get_logger()

RETENTION = timedelta(days=365)


async def purge_expired(session: AsyncSession, now: datetime | None = None) -> tuple[int, int]:
    """Deletes linked events older than RETENTION and the anonymous users left with nothing recent
    (their cookie has expired by then). Events with no user are anonymous counts and are kept."""
    cutoff = (now or datetime.now(UTC)) - RETENTION
    events = await session.execute(delete(Event).where(Event.user_id.is_not(None), Event.created_at < cutoff))
    recent_event = exists(select(Event.id).where(Event.user_id == User.id))
    recent_rating = exists(
        select(ArticleFeedback.user_id).where(ArticleFeedback.user_id == User.id, ArticleFeedback.updated_at >= cutoff)
    )
    users = await session.execute(
        delete(User).where(User.email.is_(None), User.created_at < cutoff, ~recent_event, ~recent_rating)
    )
    await session.commit()
    return events.rowcount, users.rowcount


async def purge_job() -> None:
    async with SessionLocal() as session:
        events, users = await purge_expired(session)
    log.info("privacy_purge", events=events, users=users)
