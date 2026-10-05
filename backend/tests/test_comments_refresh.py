from datetime import UTC, datetime, timedelta

from app.api.routes import _comments_stale
from app.models import Article

NOW = datetime(2026, 10, 5, 12, tzinfo=UTC)


def story(published_hours_ago, fetched_minutes_ago=None):
    return Article(
        source="hn", published_at=NOW - timedelta(hours=published_hours_ago),
        comments_fetched_at=None if fetched_minutes_ago is None else NOW - timedelta(minutes=fetched_minutes_ago),
    )


def test_never_fetched_is_always_stale():
    assert _comments_stale(story(1), NOW)
    assert _comments_stale(story(100), NOW)


def test_live_thread_refreshes_after_five_minutes():
    assert not _comments_stale(story(3, fetched_minutes_ago=4), NOW)
    assert _comments_stale(story(3, fetched_minutes_ago=6), NOW)


def test_frozen_thread_is_not_refetched():
    assert not _comments_stale(story(60, fetched_minutes_ago=600), NOW)
