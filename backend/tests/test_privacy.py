from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.models import Event, User
from app.privacy import purge_expired

NOW = datetime(2026, 10, 5, tzinfo=UTC)


async def test_purge_drops_old_linked_history_and_keeps_anonymous_counts(session):
    stale, active = User(anon_token_hash="a", created_at=NOW - timedelta(days=500)), User(anon_token_hash="b")
    session.add_all([stale, active])
    await session.flush()
    old = NOW - timedelta(days=400)
    session.add_all([
        Event(user_id=stale.id, type="click", created_at=old),
        Event(user_id=active.id, type="click", created_at=old),
        Event(user_id=active.id, type="click", created_at=NOW - timedelta(days=3)),
        Event(user_id=None, type="click", created_at=old),
    ])
    await session.commit()

    assert await purge_expired(session, NOW) == (2, 1)
    assert [u.anon_token_hash for u in (await session.execute(select(User))).scalars()] == ["b"]
    left = (await session.execute(select(Event.user_id).order_by(Event.id))).scalars().all()
    assert left == [active.id, None]
