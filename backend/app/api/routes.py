import asyncio
from datetime import UTC, datetime, timedelta
from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from fastapi.responses import StreamingResponse
from sqlalchemy import and_, func, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app import chat as story_chat
from app.ai.base import AIClient
from app.api.comments_tree import build_tree
from app.api.session import ensure_session, forget, optional_user, required_user
from app.config import get_settings
from app.db import get_session
from app.enrich.digest import KINDS as DIGEST_KINDS
from app.enrich.translate import translate_comments
from app.ingest.fetch import make_client
from app.ingest.jobs import fetch_story_comments
from app.models import AIUsage, Article, ArticleFeedback, Digest, Event, User
from app.schemas import ArticleOut, ChatIn, CommentNode, DigestOut, EventBatch, FeedbackIn

log = structlog.get_logger()
router = APIRouter()
Session = Annotated[AsyncSession, Depends(get_session)]
MaybeUser = Annotated[User | None, Depends(optional_user)]
Lang = Annotated[str, Query(pattern="^(es|en)$")]
TRANSLATE_BUDGET = 120  # max comments translated per request

COMMENTS_SQL = text("""
    WITH RECURSIVE tree AS (
        SELECT id, author, text, text_es, created_at, depth, ARRAY[sibling_rank] AS path
        FROM hn_comments WHERE story_id = :story AND parent_id = :story AND NOT deleted
        UNION ALL
        SELECT c.id, c.author, c.text, c.text_es, c.created_at, c.depth, t.path || c.sibling_rank
        FROM hn_comments c JOIN tree t ON c.parent_id = t.id WHERE NOT c.deleted
    )
    SELECT id, author, text, text_es, created_at, depth FROM tree ORDER BY path
""")


COMMENTS_REFRESH = timedelta(minutes=5)
THREAD_LIVE = timedelta(hours=48)


def _comments_stale(a: Article, now: datetime | None = None) -> bool:
    now = now or datetime.now(UTC)
    if a.comments_fetched_at is None:
        return True
    return now - a.published_at < THREAD_LIVE and now - a.comments_fetched_at > COMMENTS_REFRESH


async def _out(session: AsyncSession, user: User | None, articles: list[Article]) -> list[ArticleOut]:
    """Serialises articles, adding the session user's current rating."""
    votes: dict[int, int] = {}
    if user and articles:
        votes = dict((await session.execute(
            select(ArticleFeedback.article_id, ArticleFeedback.value).where(
                ArticleFeedback.user_id == user.id, ArticleFeedback.article_id.in_([a.id for a in articles])
            )
        )).all())
    outs = []
    for a in articles:
        out = ArticleOut.model_validate(a)
        out.hn_story_id = int(a.external_id) if a.source == "hn" else None
        out.feedback = votes.get(a.id, 0)
        outs.append(out)
    return outs


@router.get("/health")
async def health(session: Session) -> dict:
    await session.execute(select(1))
    return {"status": "ok"}


@router.post("/session")
async def create_session(user: Annotated[User, Depends(ensure_session)]) -> dict:
    return {"user_id": user.id}


@router.delete("/session", status_code=204)
async def delete_session(response: Response, session: Session, user: MaybeUser) -> None:
    """Withdraws consent: this browser's anonymous user and all its data are deleted."""
    await forget(response, session, user)


@router.get("/feed/latest", response_model=list[ArticleOut])
async def latest(
    session: Session,
    user: MaybeUser,
    source: Annotated[str | None, Query(pattern="^(reuters|ars|hn)$")] = None,
    section: Annotated[str | None, Query(max_length=32)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 30,
    before: datetime | None = None,
    offset: Annotated[int, Query(ge=0, le=10_000)] = 0,
) -> list[ArticleOut]:
    """Chronological feed, filterable by source and section. Duplicates are excluded.
    Hacker News alone follows /front instead: newest day first, then HN's own ranking
    (page with offset, since the order is not chronological)."""
    q = select(Article).where(Article.duplicate_of.is_(None)).limit(limit).offset(offset)
    if source == "hn":
        q = q.where(Article.hn_front_day.is_not(None)).order_by(
            Article.hn_front_day.desc(), Article.hn_front_rank.asc()
        )
    else:
        q = q.order_by(Article.published_at.desc())
    if source:
        q = q.where(Article.source == source)
    if section:
        q = q.where(Article.section == section)
    if before:
        q = q.where(Article.published_at < before)
    return await _out(session, user, list((await session.execute(q)).scalars()))


@router.get("/feed/important", response_model=list[ArticleOut])
async def important(
    session: Session, user: MaybeUser, limit: Annotated[int, Query(ge=1, le=10)] = 5
) -> list[ArticleOut]:
    """Today's essentials: non-personalised lane with the highest global relevance (stage 0).
    HN comes from /front, which covers the previous day, so its window is 48 h."""
    now = datetime.now(UTC)
    recent = or_(
        Article.published_at > now - timedelta(hours=24),
        and_(Article.source == "hn", Article.published_at > now - timedelta(hours=48)),
    )
    q = (
        select(Article)
        .where(Article.duplicate_of.is_(None), Article.global_score.is_not(None), recent)
        .order_by(Article.global_score.desc(), Article.published_at.desc())
        .limit(limit * 6)
    )
    # Source balance: at most half (rounded up) from any single source.
    per_source_cap, picked, counts = -(-limit // 2), [], {}
    for a in (await session.execute(q)).scalars():
        if counts.get(a.source, 0) < per_source_cap:
            picked.append(a)
            counts[a.source] = counts.get(a.source, 0) + 1
        if len(picked) == limit:
            break
    return await _out(session, user, picked)


@router.get("/digest", response_model=dict[str, DigestOut | None])
async def digest(session: Session) -> dict[str, Digest | None]:
    """Latest overview of each kind (general, world, tech); null where none exists yet."""
    return {
        kind: await session.scalar(
            select(Digest).where(Digest.kind == kind).order_by(Digest.created_at.desc()).limit(1)
        )
        for kind in DIGEST_KINDS
    }


@router.get("/articles/{article_id}", response_model=ArticleOut)
async def article(article_id: int, session: Session, user: MaybeUser) -> ArticleOut:
    a = await session.get(Article, article_id)
    if not a:
        raise HTTPException(404, "article not found")
    return (await _out(session, user, [a]))[0]


@router.put("/articles/{article_id}/feedback")
async def put_feedback(
    article_id: int, body: FeedbackIn, session: Session, user: Annotated[User, Depends(required_user)]
) -> dict:
    """Thumbs up (1), down (-1) or clear the rating (0). This is the explicit signal the For You
    feed will learn from; every change is also logged in events."""
    if not await session.get(Article, article_id):
        raise HTTPException(404, "article not found")
    current = await session.get(ArticleFeedback, (user.id, article_id))
    previous = current.value if current else 0
    if body.value == 0:
        if current:
            await session.delete(current)
    elif current:
        current.value, current.updated_at = body.value, datetime.now(UTC)
    else:
        session.add(ArticleFeedback(user_id=user.id, article_id=article_id, value=body.value))
    if body.value != previous:
        kind = body.value or previous
        session.add(Event(user_id=user.id, article_id=article_id, type="like" if kind > 0 else "dislike",
                          value=1 if body.value else 0))
    await session.commit()
    return {"article_id": article_id, "feedback": body.value}


@router.get("/articles/{article_id}/comments", response_model=list[CommentNode])
async def comments(article_id: int, session: Session, lang: Lang = "en") -> list[CommentNode]:
    a = await session.get(Article, article_id)
    if not a or a.source != "hn":
        raise HTTPException(404, "article has no Hacker News thread")
    if _comments_stale(a):
        # On demand: the worker only fetches big threads at 2/8/24/48 h; the rest are fetched
        # here the first time someone opens them (and refreshed while the thread is live).
        try:
            async with make_client(get_settings().http_timeout_seconds) as client:
                await fetch_story_comments(session, a, client, asyncio.Semaphore(1))
        except Exception as exc:  # noqa: BLE001 — if Algolia fails, serve what is stored
            log.warning("comments_on_demand_failed", story=a.external_id, error=str(exc))
    rows = (await session.execute(COMMENTS_SQL, {"story": int(a.external_id)})).mappings().all()
    if lang == "es" and get_settings().gemini_api_key:
        # Translate untranslated comments in reading order, capped per request.
        pending = [(r["id"], r["text"]) for r in rows if r["text"] and not r["text_es"]][:TRANSLATE_BUDGET]
        if pending:
            from app.ai.factory import get_ai_client

            await translate_comments(session, pending, get_ai_client())
            rows = (await session.execute(COMMENTS_SQL, {"story": int(a.external_id)})).mappings().all()
    return build_tree([dict(r) for r in rows])


def chat_ai() -> AIClient | None:
    if not get_settings().gemini_api_key:
        return None
    from app.ai.factory import get_ai_client
    return get_ai_client()


def client_ip(request: Request) -> str:
    """The visitor's address: set by the site's Caddy from the trusted edge proxy (X-Real-IP), or
    the direct peer when running without proxies."""
    return request.headers.get("x-real-ip") or (request.client.host if request.client else "unknown")


@router.post("/articles/{article_id}/chat")
async def ask_about_story(
    article_id: int, body: ChatIn, request: Request, session: Session,
    ai: Annotated[AIClient | None, Depends(chat_ai)],
) -> StreamingResponse:
    """Answers a question about one story, streamed as server-sent events (see app.chat)."""
    try:
        story_chat.validate(body)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    a = await session.get(Article, article_id)
    if not a:
        raise HTTPException(404, "article not found")
    if ai is None:
        raise HTTPException(503, "unavailable")
    try:
        story_chat.guard().check(client_ip(request))
    except story_chat.ChatLimited as exc:
        raise HTTPException(429, exc.code) from exc
    system = await story_chat.build_system(session, a, body.lang)
    return StreamingResponse(
        story_chat.answer(ai, system, body), media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/events", status_code=202)
async def post_events(batch: EventBatch, session: Session, user: MaybeUser) -> dict:
    user_id = user.id if user else None
    session.add_all(Event(user_id=user_id, type=e.type, article_id=e.article_id, value=e.value, position=e.position)
                    for e in batch.events)
    await session.commit()
    return {"accepted": len(batch.events)}


@router.get("/metrics")
async def metrics(session: Session) -> dict:
    day_ago = datetime.now(UTC) - timedelta(hours=24)
    per_source = (await session.execute(
        select(Article.source, func.count()).where(Article.created_at > day_ago).group_by(Article.source)
    )).all()
    usage = (await session.execute(
        select(AIUsage.model, func.sum(AIUsage.requests), func.sum(AIUsage.input_tokens + AIUsage.output_tokens))
        .where(AIUsage.created_at > day_ago).group_by(AIUsage.model)
    )).all()
    originals = select(func.count()).select_from(Article).where(Article.duplicate_of.is_(None))
    total = await session.scalar(originals)
    enriched = await session.scalar(originals.where(Article.enriched_at.is_not(None)))
    last_ingest = await session.scalar(select(func.max(Article.created_at)))
    return {
        "articles_total": total,
        "articles_enriched": enriched,
        "last_ingest_at": last_ingest,
        "ingested_last_24h": {s: n for s, n in per_source},
        "ai_usage_last_24h": [{"model": m, "requests": int(r), "tokens": int(t or 0)} for m, r, t in usage],
    }
