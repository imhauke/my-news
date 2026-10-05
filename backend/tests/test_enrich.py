from datetime import UTC, datetime

import pytest
from sqlalchemy import select

from app.ai.base import AIError, QuotaExhausted
from app.enrich import jobs
from app.enrich.meta import extract_description
from app.enrich.stage0 import EnrichedItem, EnrichmentBatch, build_prompt
from app.models import Article

NOW = datetime(2026, 10, 5, 8, tzinfo=UTC)


def test_extract_description_prefers_og_and_truncates():
    html = """<html><head>
      <meta name="description" content="Plain description that is long enough to be kept around.">
      <meta property="og:description" content="Open Graph   description,  with collapsed whitespace and enough length.">
    </head></html>"""
    assert extract_description(html) == "Open Graph description, with collapsed whitespace and enough length."
    long = f'<meta name="description" content="{"word " * 200}">'
    out = extract_description(long, max_length=50)
    assert out and len(out) <= 50 and out.endswith("…")
    assert extract_description('<meta name="description" content="too short">') is None


def test_build_prompt_includes_excerpt_only_when_present():
    prompt = build_prompt([
        {"id": 1, "source": "reuters", "section": None, "title": "Headline only", "summary": None},
        {"id": 2, "source": "ars", "section": "ai", "title": "With excerpt", "summary": "Some context."},
    ])
    assert "[id=1] source=reuters\ntitle: Headline only\n\n" in prompt
    assert "section=ai" in prompt and "excerpt: Some context." in prompt


class FakeAI:
    def __init__(self, responses):
        self.responses = list(responses)
        self.prompts: list[str] = []

    async def generate_json(self, prompt, schema, **kw):
        self.prompts.append(prompt)
        r = self.responses.pop(0)
        if isinstance(r, Exception):
            raise r
        return r


def item(id_, score=0.5):
    return EnrichedItem(id=id_, title_es=f"titular {id_}", summary_en=f"en {id_}", summary_es=f"es {id_}",
                        topics=[" Chips ", ""], topics_es=["Chips "], global_score=score)


@pytest.fixture
async def articles(session, monkeypatch):
    rows = [Article(source="hn", external_id=str(i), url=f"https://a.test/{i}", url_normalized=f"a.test/{i}",
                    title=f"Story {i}", summary=f"Excerpt {i}", published_at=NOW) for i in range(3)]
    session.add_all(rows)
    await session.commit()
    monkeypatch.setattr(jobs, "SessionLocal", lambda: _Reuse(session))
    return rows


class _Reuse:
    """Reuses the test session as if it were a new one (async context manager)."""

    def __init__(self, session):
        self.session = session

    async def __aenter__(self):
        return self.session

    async def __aexit__(self, *exc):
        return False


async def test_enrich_writes_fields_and_ignores_unknown_ids(session, articles):
    ids = [a.id for a in articles]
    ai = FakeAI([EnrichmentBatch(items=[item(ids[0], 0.9), item(ids[1]), item(9999)])])
    assert await jobs.enrich_articles(ai, read_articles=False) == 2
    first = await session.get(Article, ids[0])
    assert (first.ai_summary_en, first.ai_summary_es) == (f"en {ids[0]}", f"es {ids[0]}")
    assert (first.topics, first.topics_es, first.global_score) == (["chips"], ["chips"], 0.9)
    assert first.title_es == f"titular {ids[0]}"
    # The one the model skipped stays pending and is retried on the next run.
    pending = (await session.scalars(select(Article.id).where(Article.enriched_at.is_(None)))).all()
    assert pending == [ids[2]]


async def test_enrich_stops_on_quota_and_skips_failed_batches(session, articles, monkeypatch):
    monkeypatch.setattr(jobs, "BATCH_SIZE", 1)
    ai = FakeAI([AIError("bad json"), QuotaExhausted("day")])
    assert await jobs.enrich_articles(ai, read_articles=False) == 0
    assert len(ai.prompts) == 2  # a failed batch does not stop the run; exhausted quota does


async def test_articles_enriched_before_title_translation_are_redone(session, articles):
    done = articles[0]
    done.enriched_at, done.title_es = NOW, None
    await session.commit()
    ai = FakeAI([EnrichmentBatch(items=[item(a.id) for a in articles])])
    assert await jobs.enrich_articles(ai, read_articles=False) == 3


async def test_headline_only_articles_get_no_description(session, articles):
    articles[0].summary = None  # like Reuters: headline only
    await session.commit()
    ai = FakeAI([EnrichmentBatch(items=[item(a.id) for a in articles])])
    await jobs.enrich_articles(ai, read_articles=False)
    bare, rich = await session.get(Article, articles[0].id), await session.get(Article, articles[1].id)
    assert (bare.ai_summary_en, bare.ai_summary_es) == (None, None)
    assert bare.title_es == f"titular {articles[0].id}" and bare.topics == ["chips"]
    assert rich.ai_summary_es == f"es {articles[1].id}"


def test_extract_article_text_needs_real_body():
    from app.enrich.article_text import extract_article_text

    para = "This paragraph is long enough to count as article body text for the extractor to keep it. " * 3
    page = f"<nav><p>{para}</p></nav><article><p>{para}</p><p>{para}</p><p>{para}</p></article><p>short</p>"
    text = extract_article_text(page)
    assert text and text.count(para.strip()) == 3  # nav paragraph skipped, short one dropped
    bio = f"<p>{para}</p><p>{para}</p>"  # an author bio or a paywall teaser is not enough
    assert extract_article_text(bio) is None
    assert len(extract_article_text(page, max_chars=50) or "") == 50


async def test_article_text_is_passed_to_the_model(session, articles, monkeypatch):
    async def fake_texts(batch):
        return {batch[0].id: "Body text with details."}

    monkeypatch.setattr(jobs, "fetch_article_texts", fake_texts)
    ai = FakeAI([EnrichmentBatch(items=[item(a.id) for a in articles])])
    await jobs.enrich_articles(ai)
    assert "article text: Body text with details." in ai.prompts[0]
