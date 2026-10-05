from datetime import UTC, datetime, timedelta

import httpx
import pytest

from app.db import get_session
from app.main import app
from app.models import Article

NOW = datetime.now(UTC)


@pytest.fixture
async def client(session):
    async def override():
        yield session

    app.dependency_overrides[get_session] = override
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as c:
        yield c
    app.dependency_overrides.clear()


def article(i, *, score=None, hours_ago=1, dup=None, source="ars"):
    return Article(
        source=source, external_id=str(i), url=f"https://a.test/{i}", url_normalized=f"a.test/{i}", title=f"T{i}",
        published_at=NOW - timedelta(hours=hours_ago), global_score=score, duplicate_of=dup,
        ai_summary_en=f"en {i}", ai_summary_es=f"es {i}",
    )


async def test_important_orders_by_score_and_filters(session, client):
    session.add_all([article(1, score=0.4), article(2, score=0.9), article(3), article(4, score=1.0, hours_ago=30)])
    await session.commit()
    session.add(article(5, score=0.95, dup=1))
    await session.commit()
    body = (await client.get("/feed/important")).json()
    assert [a["title"] for a in body] == ["T2", "T1"]  # unscored, old and duplicate are left out
    assert body[0]["ai_summary_es"] == "es 2"


async def test_latest_filters_by_source_and_paginates(session, client):
    session.add_all([article(1, hours_ago=1), article(2, hours_ago=2, source="hn"), article(3, hours_ago=3)])
    await session.commit()
    page1 = (await client.get("/feed/latest", params={"source": "ars", "limit": 1})).json()
    page2 = (await client.get("/feed/latest", params={"source": "ars", "before": page1[0]["published_at"]})).json()
    assert [a["title"] for a in page1 + page2] == ["T1", "T3"]
    assert (await client.get("/feed/latest", params={"source": "nope"})).status_code == 422


async def test_comments_404_for_non_hn(session, client):
    session.add(article(1))
    await session.commit()
    assert (await client.get("/articles/1/comments")).status_code == 404
    assert (await client.get("/articles/999")).status_code == 404


async def test_events_and_metrics(session, client):
    session.add(article(1, score=0.5))
    await session.commit()
    resp = await client.post("/events", json={"events": [{"type": "click", "article_id": 1, "position": 0}]})
    assert resp.json() == {"accepted": 1}
    assert (await client.post("/events", json={"events": [{"type": "nope"}]})).status_code == 422
    metrics = (await client.get("/metrics")).json()
    assert metrics["articles_total"] == 1 and metrics["articles_enriched"] == 0


async def test_important_balances_sources(session, client):
    session.add_all([article(i, score=0.9 - i / 100, source="reuters") for i in range(1, 6)] + [article(9, score=0.1)])
    await session.commit()
    body = (await client.get("/feed/important", params={"limit": 4})).json()
    assert [a["source"] for a in body] == ["reuters", "reuters", "ars"]  # at most 2 per source with limit=4


async def test_session_cookie_and_feedback_roundtrip(session, client):
    session.add(article(1, score=0.5))
    await session.commit()
    assert (await client.put("/articles/1/feedback", json={"value": 1})).status_code == 401
    first = await client.post("/session")
    assert "mn_session" in first.cookies
    again = await client.post("/session")  # the cookie identifies the same user
    assert again.json() == first.json()

    assert (await client.put("/articles/1/feedback", json={"value": 1})).json()["feedback"] == 1
    assert (await client.get("/feed/latest")).json()[0]["feedback"] == 1
    await client.put("/articles/1/feedback", json={"value": -1})
    await client.put("/articles/1/feedback", json={"value": 0})
    assert (await client.get("/articles/1")).json()["feedback"] == 0
    assert (await client.put("/articles/1/feedback", json={"value": 5})).status_code == 422
    assert (await client.put("/articles/99/feedback", json={"value": 1})).status_code == 404

    from sqlalchemy import select

    from app.models import Event
    events = (await session.execute(select(Event.type, Event.value).order_by(Event.id))).all()
    assert events == [("like", 1), ("dislike", 1), ("dislike", 0)]


async def test_latest_filters_by_section(session, client):
    a, b = article(1), article(2)
    a.section, b.section = "ai", "security"
    session.add_all([a, b])
    await session.commit()
    body = (await client.get("/feed/latest", params={"source": "ars", "section": "security"})).json()
    assert [x["title"] for x in body] == ["T2"]


async def test_comments_are_translated_to_spanish_on_demand(session, client, monkeypatch):
    from app.api import routes
    from app.enrich.translate import TranslatedComment, TranslationBatch
    from app.models import HNComment

    story = article(1, source="hn")
    story.external_id, story.comments_fetched_at = "500", NOW
    session.add(story)
    session.add_all([
        HNComment(id=501, story_id=500, parent_id=500, author="a", text="Hello", created_at=NOW, depth=0),
        HNComment(id=502, story_id=500, parent_id=501, author="b", text="Thanks", created_at=NOW, depth=1),
    ])
    await session.commit()

    calls = []

    class FakeAI:
        async def generate_json(self, prompt, schema, **kw):
            calls.append(prompt)
            return TranslationBatch(items=[TranslatedComment(id=501, text_es="Hola"),
                                           TranslatedComment(id=502, text_es="Gracias")])

    monkeypatch.setattr("app.ai.factory.get_ai_client", lambda: FakeAI())
    monkeypatch.setattr(routes, "get_settings", lambda: type("S", (), {"gemini_api_key": "k"})())

    english = (await client.get("/articles/1/comments")).json()
    assert english[0]["text_es"] is None and not calls  # nothing is translated in English
    spanish = (await client.get("/articles/1/comments", params={"lang": "es"})).json()
    assert spanish[0]["text_es"] == "Hola" and spanish[0]["children"][0]["text_es"] == "Gracias"
    await client.get("/articles/1/comments", params={"lang": "es"})
    assert len(calls) == 1  # cached: not translated again


async def test_hacker_news_follows_front_page_order(session, client):
    from datetime import date

    stories = []
    for i, (day, rank, hours_ago) in enumerate([(4, 2, 1), (4, 1, 30), (3, 1, 2), (4, 3, 5)], start=1):
        s = article(i, source="hn", hours_ago=hours_ago)
        s.hn_front_day, s.hn_front_rank = date(2026, 10, day), rank
        stories.append(s)
    stray = article(9, source="hn")  # an HN story that never made /front is not listed
    session.add_all([*stories, stray])
    await session.commit()

    titles = [a["title"] for a in (await client.get("/feed/latest", params={"source": "hn"})).json()]
    assert titles == ["T2", "T1", "T4", "T3"]  # newest day first, then HN's own ranking
    page2 = (await client.get("/feed/latest", params={"source": "hn", "limit": 2, "offset": 2})).json()
    assert [a["title"] for a in page2] == ["T4", "T3"]


async def test_digest_endpoint_returns_latest_or_null(session, client):
    from app.models import Digest

    assert (await client.get("/digest")).json() is None
    session.add_all([
        Digest(text_en="old", text_es="viejo", article_ids=[1], model="m", created_at=NOW - timedelta(hours=2)),
        Digest(text_en="new", text_es="nuevo", article_ids=[2], model="m", created_at=NOW),
    ])
    await session.commit()
    body = (await client.get("/digest")).json()
    assert (body["text_en"], body["text_es"], body["article_ids"]) == ("new", "nuevo", [2])
