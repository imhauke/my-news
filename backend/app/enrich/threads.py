"""Hacker News thread analysis: what the community says about a story, in a few lines.

For threads with a real discussion, Gemini Flash-Lite reads the opening of the conversation (top
comments and their first replies, in reading order) and returns the overall tone, the main points
of debate with what each side argues, notable contributions (first-hand experience, corrections)
and resources the commenters linked, in English and Spanish. The worker writes it once the thread
has been fetched and rewrites it when the thread has grown by half."""

from datetime import UTC, datetime, timedelta
from typing import Literal

import structlog
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.base import AIClient, AIError, Priority, QuotaExhausted
from app.api.comments_tree import COMMENTS_SQL
from app.config import get_settings
from app.db import SessionLocal
from app.models import Article, HNComment, ThreadInsight

log = structlog.get_logger()

MIN_COMMENTS = 30
GROWTH = 1.5  # rewrite once the thread has this many times the comments covered
MIN_REWRITE_AGE = timedelta(hours=2)
WINDOW = timedelta(hours=72)
MAX_PER_RUN = 4
MAX_DEPTH = 2  # top comments, replies and replies to replies
COMMENT_CHARS = 700
CHAR_BUDGET = 24_000

SYSTEM = """You analyse a Hacker News discussion for a reader who has not read it. You get the
story's headline and the opening of the conversation in reading order; indentation marks replies.
Return:
- tone: the overall mood towards the story: "positive", "skeptical", "divided" or "mixed".
- summary_en / summary_es: what the community thinks overall, in at most 45 words.
- points: the 2 to 4 main points of debate. For each, a short title and at most 35 words saying
  what is argued and, when there is disagreement, what each side says.
- contributions: up to 3 comments that add something the article does not: first-hand
  experience, expert corrections, key data. Give the commenter's username and the gist in at
  most 30 words.
- resources: up to 3 links that commenters shared and that are worth opening, with a short title.
  Copy each URL exactly as it appears in a comment; never invent one. Return none if no comment
  links anything useful.
Rules: report what commenters say, attributing it ("some argue", "a commenter who works on X
says"); never present their claims as facts. Plain, neutral language; no quotes longer than a few
words. Spanish texts in natural Spanish (Spain). Titles at most 8 words."""


class Point(BaseModel):
    title_en: str = Field(max_length=120)
    title_es: str = Field(max_length=140)
    text_en: str = Field(max_length=500)
    text_es: str = Field(max_length=600)


class Contribution(BaseModel):
    author: str = Field(max_length=64)
    text_en: str = Field(max_length=400)
    text_es: str = Field(max_length=480)


class Resource(BaseModel):
    title: str = Field(max_length=120)
    url: str = Field(max_length=500)


class InsightOut(BaseModel):
    tone: Literal["positive", "skeptical", "divided", "mixed"]
    summary_en: str = Field(min_length=10, max_length=600)
    summary_es: str = Field(min_length=10, max_length=700)
    points: list[Point] = Field(default_factory=list, max_length=4)
    contributions: list[Contribution] = Field(default_factory=list, max_length=3)
    resources: list[Resource] = Field(default_factory=list, max_length=3)


async def conversation(session: AsyncSession, story_id: int) -> tuple[str, str]:
    """The opening of the thread as indented text within CHAR_BUDGET, plus every comment's text
    joined (to check that linked URLs are real)."""
    rows = (await session.execute(COMMENTS_SQL, {"story": story_id})).mappings().all()
    lines, used = [], 0
    for r in rows:
        if r["depth"] > MAX_DEPTH or not r["text"]:
            continue
        line = f"{'  ' * r['depth']}{r['author'] or 'anonymous'}: {r['text'][:COMMENT_CHARS]}"
        if used + len(line) > CHAR_BUDGET:
            break
        lines.append(line)
        used += len(line)
    return "\n".join(lines), "\n".join(r["text"] or "" for r in rows)


def build_prompt(article: Article, thread: str) -> str:
    return f"Headline: {article.title}\nLink: {article.url}\n\nDiscussion:\n{thread}"


async def due_threads(session: AsyncSession, now: datetime) -> list[tuple[Article, int]]:
    """Threads worth analysing now, with their stored comment count."""
    articles = (await session.scalars(
        select(Article).where(
            Article.source == "hn", Article.duplicate_of.is_(None), Article.comments_fetched_at.is_not(None),
            Article.hn_comment_count >= MIN_COMMENTS, Article.published_at > now - WINDOW,
        ).order_by(Article.hn_points.desc().nulls_last()).limit(60)
    )).all()
    if not articles:
        return []
    ids = [int(a.external_id) for a in articles]
    counts = dict((await session.execute(
        select(HNComment.story_id, func.count())
        .where(HNComment.story_id.in_(ids), HNComment.deleted.is_(False), HNComment.text.is_not(None))
        .group_by(HNComment.story_id)
    )).all())
    insights = {i.story_id: i for i in (await session.scalars(
        select(ThreadInsight).where(ThreadInsight.story_id.in_(ids))
    )).all()}
    due = []
    for a in articles:
        stored, insight = counts.get(int(a.external_id), 0), insights.get(int(a.external_id))
        if stored < MIN_COMMENTS:
            continue
        if insight is None or (
            stored >= insight.comments_covered * GROWTH and now - insight.created_at >= MIN_REWRITE_AGE
        ):
            due.append((a, stored))
    return due


async def analyse_threads(ai: AIClient | None = None, now: datetime | None = None) -> int:
    """Writes the insights that are due. Returns how many were written."""
    cfg = get_settings()
    now = now or datetime.now(UTC)
    if ai is None:
        if not cfg.gemini_api_key:
            return 0
        from app.ai.factory import get_ai_client
        ai = get_ai_client()
    done = 0
    async with SessionLocal() as session:
        for article, stored in (await due_threads(session, now))[:MAX_PER_RUN]:
            story_id = int(article.external_id)
            thread, everything = await conversation(session, story_id)
            try:
                out = await ai.generate_json(
                    build_prompt(article, thread), InsightOut, model=cfg.gemini_model_lite,
                    task="thread_insight", priority=Priority.HN_ANALYSIS, system=SYSTEM,
                )
            except QuotaExhausted:
                break
            except AIError as exc:
                log.warning("thread_insight_failed", story=story_id, error=str(exc))
                continue
            resources = [r.model_dump() for r in out.resources if r.url.startswith("http") and r.url in everything]
            await session.merge(ThreadInsight(
                story_id=story_id, tone=out.tone, summary=out.summary_en.strip(), summary_es=out.summary_es.strip(),
                key_points=[p.model_dump() for p in out.points],
                notable_comments=[c.model_dump() for c in out.contributions],
                resources=resources, comments_covered=stored, model=cfg.gemini_model_lite, created_at=now,
            ))
            await session.commit()
            done += 1
            log.info("thread_insight_done", story=story_id, comments=stored)
    return done
