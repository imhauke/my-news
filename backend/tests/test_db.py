"""Tests contra PostgreSQL real: idempotencia, deduplicación y consulta recursiva del árbol."""

from datetime import UTC, datetime

from sqlalchemy import func, select

from app.api.comments_tree import build_tree
from app.api.routes import COMMENTS_SQL
from app.ingest.service import upsert_articles, upsert_comments
from app.ingest.sources import flatten_algolia_tree
from app.ingest.types import ParsedArticle
from app.models import Article, HNComment

NOW = datetime(2026, 10, 5, 8, tzinfo=UTC)


def art(source, ext, url, title, **kw):
    return ParsedArticle(source=source, external_id=ext, url=url, title=title, published_at=NOW, **kw)


async def test_upsert_is_idempotent_and_updates_points(session):
    await upsert_articles(session, [art("hn", "1", "https://a.test/x", "Hello world", hn_points=10)])
    stats = await upsert_articles(session, [art("hn", "1", "https://a.test/x", "Hello world", hn_points=99)])
    assert stats == {"new": 0, "updated": 1, "duplicates": 0}
    assert await session.scalar(select(func.count()).select_from(Article)) == 1
    assert await session.scalar(select(Article.hn_points)) == 99


async def test_dedup_by_normalized_url_and_by_title(session):
    first = [art("ars", "a", "https://www.site.test/p/?utm_source=x", "Chip export rules tightened")]
    await upsert_articles(session, first)
    stats = await upsert_articles(session, [
        art("hn", "9", "http://site.test/p", "Something else entirely"),               # misma URL
        art("reuters", "r", "https://news.test/1", "Chip export rules tightened!"),    # titular similar
        art("reuters", "s", "https://news.test/2", "Unrelated geopolitics story"),
    ])
    assert stats["duplicates"] == 2
    originals = (await session.scalars(select(Article.title).where(Article.duplicate_of.is_(None)))).all()
    assert sorted(originals) == ["Chip export rules tightened", "Unrelated geopolitics story"]


async def test_comment_tree_roundtrip_and_deleted_marking(session):
    import json
    from pathlib import Path

    story = json.loads((Path(__file__).parent / "fixtures/algolia_item.json").read_text())
    await upsert_comments(session, 100, flatten_algolia_tree(story))
    rows = (await session.execute(COMMENTS_SQL, {"story": 100})).mappings().all()
    tree = build_tree([dict(r) for r in rows])
    assert [n.id for n in tree] == [101]          # 102 está borrado → fuera
    assert [c.id for c in tree[0].children] == [103]

    # Segunda pasada: 103 desaparece del hilo → se marca como borrado, no se pierde la fila
    story["children"][0]["children"] = []
    await upsert_comments(session, 100, flatten_algolia_tree(story))
    assert await session.scalar(select(HNComment.deleted).where(HNComment.id == 103)) is True


async def test_same_article_in_two_feeds_counts_once(session):
    a = art("ars", "x", "https://a.test/1", "Same story in two sections", section="ai")
    b = art("ars", "x", "https://a.test/1", "Same story in two sections", section="tech")
    stats = await upsert_articles(session, [a, b])
    assert stats == {"new": 1, "updated": 0, "duplicates": 0}


async def test_reingest_updates_section(session):
    await upsert_articles(session, [art("hn", "7", "https://a.test/7", "Old top story")])
    await upsert_articles(session, [art("hn", "7", "https://a.test/7", "Old top story", section="front")])
    assert await session.scalar(select(Article.section)) == "front"
