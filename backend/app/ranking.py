"""Ranking for "Today's essentials" and the daily overviews.

Gemini rates each story's importance once (stage 0). On top of that the server adds what it can
measure itself, how many outlets report the story and how far it went on Hacker News, and halves
the result every HALF_LIFE_HOURS, so a big story from yesterday gives way to comparable news from
today."""

import math
from datetime import datetime, timedelta

from sqlalchemy import ColumnElement, and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Article

HALF_LIFE_HOURS = 18
COVERAGE_BONUS = 0.05  # per other outlet reporting the same story, up to MAX_COVERAGE
MAX_COVERAGE = 3
HN_BONUS = 0.05  # reached at HN_FULL_POINTS
HN_FULL_POINTS = 500
CANDIDATES = 300


def recent(now: datetime) -> ColumnElement[bool]:
    """The last day; HN /front covers the previous day, so its stories get 48 h."""
    return or_(
        Article.published_at > now - timedelta(hours=24),
        and_(Article.source == "hn", Article.published_at > now - timedelta(hours=48)),
    )


def score(article: Article, now: datetime, coverage: int = 0) -> float:
    base = article.global_score or 0.0
    base += COVERAGE_BONUS * min(coverage, MAX_COVERAGE)
    if article.hn_points:
        base += HN_BONUS * min(article.hn_points / HN_FULL_POINTS, 1)
    age_hours = max((now - article.published_at).total_seconds() / 3600, 0)
    return base * math.pow(0.5, age_hours / HALF_LIFE_HOURS)


async def rank_recent(session: AsyncSession, now: datetime, where: ColumnElement[bool] | None = None) -> list[Article]:
    """Scored stories of the last day, best first."""
    query = select(Article).where(Article.duplicate_of.is_(None), Article.global_score.is_not(None), recent(now))
    if where is not None:
        query = query.where(where)
    articles = (await session.scalars(query.order_by(Article.global_score.desc()).limit(CANDIDATES))).all()
    if not articles:
        return []
    coverage = dict((await session.execute(
        select(Article.duplicate_of, func.count())
        .where(Article.duplicate_of.in_([a.id for a in articles]))
        .group_by(Article.duplicate_of)
    )).all())
    return sorted(articles, key=lambda a: score(a, now, coverage.get(a.id, 0)), reverse=True)
