from datetime import UTC, datetime, timedelta

import httpx
import pytest

from app import search
from app.api import routes
from app.db import get_session
from app.enrich import embeddings
from app.main import app
from app.models import Article

NOW = datetime.now(UTC)
DIM = 768


def unit(*weights: float) -> list[float]:
    """A vector pointing along the first axes, normalised."""
    v = list(weights) + [0.0] * (DIM - len(weights))
    norm = sum(x * x for x in v) ** 0.5
    return [x / norm for x in v]


class FakeAI:
    """Embeds by keyword: election stories point along axis 0, chip stories along axis 1."""

    def __init__(self):
        self.calls: list[list[str]] = []

    async def embed(self, texts, *, task, priority=None):
        self.calls.append(texts)
        out = []
        for t in texts:
            t = t.lower()
            if "runoff" in t or "elecciones" in t:
                out.append(unit(1, 0.1))
            else:
                out.append(unit(0.1, 1) if "chip" in t else unit(0, 0, 1))
        return out


class _Reuse:
    def __init__(self, session):
        self.session = session

    async def __aenter__(self):
        return self.session

    async def __aexit__(self, *exc):
        return False


@pytest.fixture
async def stories(session, monkeypatch):
    rows = [
        Article(source="reuters", external_id="1", url="https://a.test/1", url_normalized="a.test/1",
                title="Brazil heads to a runoff", published_at=NOW - timedelta(hours=2), enriched_at=NOW),
        Article(source="ars", external_id="2", url="https://a.test/2", url_normalized="a.test/2",
                title="TSMC boosts AI chip output", published_at=NOW - timedelta(hours=1), enriched_at=NOW,
                ai_summary_en="More advanced chips.", topics=["semiconductors"]),
        Article(source="hn", external_id="3", url="https://a.test/3", url_normalized="a.test/3",
                title="Show HN: my garden planner", published_at=NOW, enriched_at=NOW),
        Article(source="hn", external_id="4", url="https://a.test/4", url_normalized="a.test/4",
                title="Not enriched yet", published_at=NOW),
    ]
    session.add_all(rows)
    await session.commit()
    monkeypatch.setattr(embeddings, "SessionLocal", lambda: _Reuse(session))
    return rows


async def test_embeds_enriched_stories_once(session, stories):
    ai = FakeAI()
    assert await embeddings.embed_articles(ai) == 3
    assert "TSMC boosts AI chip output\nMore advanced chips.\nTopics: semiconductors" in ai.calls[0]
    assert await embeddings.embed_articles(ai) == 0  # nothing left to embed
    assert len(ai.calls) == 1


async def test_search_finds_stories_by_meaning_in_another_language(session, stories, monkeypatch):
    ai = FakeAI()
    await embeddings.embed_articles(ai)
    monkeypatch.setattr(search, "_vectors", search.OrderedDict())
    found = await search.search(session, ai, "elecciones")
    assert [a.title for a in found] == ["Brazil heads to a runoff"]  # chips and gardens are too far
    await search.search(session, ai, "  Elecciones ")
    assert sum(t == ["elecciones"] for t in ai.calls) == 1  # the query vector is cached


async def test_search_endpoint_validates_and_limits(session, stories, monkeypatch):
    ai = FakeAI()
    await embeddings.embed_articles(ai)

    async def override():
        yield session

    app.dependency_overrides[get_session] = override
    app.dependency_overrides[routes.chat_ai] = lambda: ai
    monkeypatch.setattr(search, "_guard", search.ChatGuard(per_hour=2, per_day=100))
    try:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as c:
            assert (await c.get("/search", params={"q": "x"})).status_code == 422
            body = (await c.get("/search", params={"q": "chips"})).json()
            assert [a["title"] for a in body] == ["TSMC boosts AI chip output"]
            await c.get("/search", params={"q": "chips"})
            assert (await c.get("/search", params={"q": "chips"})).status_code == 429
    finally:
        app.dependency_overrides.clear()
