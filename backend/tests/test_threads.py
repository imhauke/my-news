from datetime import UTC, datetime, timedelta

import httpx
import pytest
from sqlalchemy import select

from app.db import get_session
from app.enrich import threads
from app.enrich.threads import Contribution, InsightOut, Point, Resource
from app.main import app
from app.models import Article, HNComment, ThreadInsight

NOW = datetime.now(UTC)


class _Reuse:
    def __init__(self, session):
        self.session = session

    async def __aenter__(self):
        return self.session

    async def __aexit__(self, *exc):
        return False


class FakeAI:
    def __init__(self):
        self.prompts: list[str] = []

    async def generate_json(self, prompt, schema, **kw):
        self.prompts.append(prompt)
        return InsightOut(
            tone="divided", summary_en="Commenters are split on the licence.",
            summary_es="Los comentaristas se dividen.",
            points=[Point(title_en="Licence", title_es="Licencia", text_en="Some like it.",
                          text_es="A algunos les gusta.")],
            contributions=[Contribution(author="ada", text_en="Ran it in prod.", text_es="Lo usó en producción.")],
            resources=[Resource(title="Benchmarks", url="https://bench.example/run"),
                       Resource(title="Made up", url="https://invented.example")],
        )


@pytest.fixture
async def thread(session, monkeypatch):
    story = Article(source="hn", external_id="500", url="https://a.test/x", url_normalized="a.test/x", title="Rust 2.0",
                    published_at=NOW - timedelta(hours=3), hn_comment_count=40, comments_fetched_at=NOW)
    session.add(story)
    comments = [HNComment(id=1000 + i, story_id=500, parent_id=500, author=f"user{i}", text=f"Comment {i}",
                          created_at=NOW, depth=0, sibling_rank=i) for i in range(35)]
    comments[3].text = "See https://bench.example/run for numbers"
    comments.append(HNComment(id=2000, story_id=500, parent_id=1000, author="deep", text="A reply", created_at=NOW,
                              depth=1, sibling_rank=0))
    session.add_all(comments)
    await session.commit()
    monkeypatch.setattr(threads, "SessionLocal", lambda: _Reuse(session))
    return story


async def test_analyses_a_discussed_thread_and_keeps_only_real_links(session, thread):
    ai = FakeAI()
    assert await threads.analyse_threads(ai, now=NOW) == 1
    insight = await session.get(ThreadInsight, 500)
    assert (insight.tone, insight.comments_covered) == ("divided", 36)
    assert insight.summary_es == "Los comentaristas se dividen."
    assert [r["url"] for r in insight.resources] == ["https://bench.example/run"]  # the invented link is dropped
    assert insight.key_points[0]["title_es"] == "Licencia" and insight.notable_comments[0]["author"] == "ada"
    assert "Headline: Rust 2.0" in ai.prompts[0] and "\n  deep: A reply" in ai.prompts[0]  # replies are indented

    # not rewritten until the thread grows by half
    assert await threads.analyse_threads(ai, now=NOW + timedelta(hours=3)) == 0
    session.add_all(HNComment(id=3000 + i, story_id=500, parent_id=500, author="x", text="more", created_at=NOW,
                              depth=0, sibling_rank=100 + i) for i in range(20))
    await session.commit()
    assert await threads.analyse_threads(ai, now=NOW + timedelta(hours=3)) == 1


async def test_small_threads_are_left_alone(session, thread):
    thread.hn_comment_count = 12
    await session.commit()
    assert await threads.analyse_threads(FakeAI(), now=NOW) == 0
    assert (await session.scalars(select(ThreadInsight))).all() == []


async def test_insight_endpoint(session, thread):
    async def override():
        yield session

    app.dependency_overrides[get_session] = override
    try:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as c:
            assert (await c.get(f"/articles/{thread.id}/insight")).json() is None
            await threads.analyse_threads(FakeAI(), now=NOW)
            body = (await c.get(f"/articles/{thread.id}/insight")).json()
            assert body["tone"] == "divided" and body["points"][0]["title_en"] == "Licence"
            other = Article(source="ars", external_id="9", url="https://a.test/9", url_normalized="a.test/9", title="T",
                            published_at=NOW)
            session.add(other)
            await session.commit()
            assert (await c.get(f"/articles/{other.id}/insight")).status_code == 404
    finally:
        app.dependency_overrides.clear()
