"""Persistencia idempotente: upsert por (fuente, id externo) y deduplicación."""

from datetime import UTC, datetime, timedelta

import structlog
from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.ingest.normalize import normalize_url, titles_similar
from app.ingest.types import ParsedArticle, ParsedComment
from app.models import Article, HNComment

log = structlog.get_logger()
DEDUP_WINDOW = timedelta(days=3)


async def upsert_articles(session: AsyncSession, items: list[ParsedArticle]) -> dict[str, int]:
    """Repetir una ingesta no duplica nada. Devuelve contadores {new, updated, duplicates}."""
    stats = {"new": 0, "updated": 0, "duplicates": 0}
    items = list({(a.source, a.external_id): a for a in items}.values())  # misma noticia en varios feeds
    if not items:
        return stats

    keys = {(a.source, a.external_id) for a in items}
    existing = {
        (r.source, r.external_id)
        for r in await session.execute(
            select(Article.source, Article.external_id).where(Article.external_id.in_([k[1] for k in keys]))
        )
    } & keys

    recent = (await session.execute(
        select(Article.id, Article.title, Article.url_normalized)
        .where(Article.published_at > datetime.now(UTC) - DEDUP_WINDOW, Article.duplicate_of.is_(None))
    )).all()
    by_url = {r.url_normalized: r.id for r in recent}
    titles = [(r.id, r.title) for r in recent]

    for a in items:
        norm = normalize_url(a.url)
        key = (a.source, a.external_id)
        values = dict(
            source=a.source, external_id=a.external_id, url=a.url, url_normalized=norm, title=a.title,
            summary=a.summary, section=a.section, author=a.author, published_at=a.published_at,
            hn_points=a.hn_points, hn_comment_count=a.hn_comment_count,
        )
        if key not in existing:
            dup = by_url.get(norm) or next((i for i, t in titles if titles_similar(a.title, t)), None)
            if dup:
                values["duplicate_of"] = dup
                stats["duplicates"] += 1
            stats["new"] += 1
        else:
            stats["updated"] += 1
        stmt = insert(Article).values(**values)
        update_cols = {c: stmt.excluded[c] for c in ("title", "summary", "section", "hn_points", "hn_comment_count")}
        article_id = (await session.execute(
            stmt.on_conflict_do_update(constraint="uq_articles_source_external_id", set_=update_cols)
            .returning(Article.id)
        )).scalar_one()
        if key not in existing and "duplicate_of" not in values:
            by_url[norm] = article_id
            titles.append((article_id, a.title))
    await session.commit()
    return stats


async def upsert_comments(session: AsyncSession, story_id: int, comments: list[ParsedComment]) -> int:
    """Upsert por id y marca de borrados: lo que ya no aparece en el árbol se marca como eliminado."""
    for c in comments:
        stmt = insert(HNComment).values(
            id=c.id, story_id=c.story_id, parent_id=c.parent_id, author=c.author, text=c.text,
            created_at=c.created_at, depth=c.depth, sibling_rank=c.sibling_rank, deleted=c.deleted,
        )
        await session.execute(stmt.on_conflict_do_update(
            index_elements=[HNComment.id],
            set_={k: stmt.excluded[k] for k in ("text", "author", "sibling_rank", "deleted")},
        ))
    seen = [c.id for c in comments]
    await session.execute(
        update(HNComment).where(HNComment.story_id == story_id, HNComment.id.not_in(seen)).values(deleted=True)
    )
    await session.commit()
    return len(comments)
