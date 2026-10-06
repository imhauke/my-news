from datetime import UTC, datetime, timedelta

from app.models import Article
from app.ranking import HALF_LIFE_HOURS, rank_recent, score

NOW = datetime(2026, 10, 6, 12, tzinfo=UTC)


def story(i, importance, hours_ago, *, source="reuters", points=None, dup=None):
    return Article(source=source, external_id=str(i), url=f"https://a.test/{i}", url_normalized=f"a.test/{i}",
                   title=f"T{i}", published_at=NOW - timedelta(hours=hours_ago), global_score=importance,
                   hn_points=points, duplicate_of=dup)


def test_score_halves_with_age_and_rewards_coverage_and_points():
    fresh, old = story(1, 0.8, 0), story(2, 0.8, HALF_LIFE_HOURS)
    assert score(fresh, NOW) == 0.8 and round(score(old, NOW), 6) == 0.4
    assert round(score(fresh, NOW, coverage=5), 6) == 0.95  # +0.05 per outlet, three at most
    assert round(score(story(3, 0.8, 0, source="hn", points=1200), NOW), 6) == 0.85
    assert score(story(4, 0.5, -1), NOW) == 0.5  # a timestamp slightly in the future is not boosted


async def test_a_big_story_from_yesterday_gives_way_to_comparable_news_from_today(session):
    session.add_all([story(1, 0.92, 20), story(2, 0.75, 1), story(3, 0.6, 0.5), story(4, 0.99, 30)])
    await session.commit()
    session.add_all([story(5, 0.75, 1, dup=3), story(6, 0.7, 1, source="ars", dup=3)])
    await session.commit()
    ranked = await rank_recent(session, NOW)
    # T4 is out of the 24 h window; T3 is reported by three outlets.
    assert [a.title for a in ranked] == ["T2", "T3", "T1"]
