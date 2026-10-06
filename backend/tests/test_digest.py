from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from app.enrich import digest
from app.enrich.digest import DigestOut, is_due
from app.models import Article, Digest

NOW = datetime(2026, 10, 5, 12, tzinfo=UTC)


def test_is_due_rules():
    assert is_due(None, [1, 2, 3], NOW)
    fresh = Digest(article_ids=[1, 2, 3, 4, 5], created_at=NOW - timedelta(minutes=10))
    assert not is_due(fresh, [9, 8, 7, 6, 5], NOW)  # changed, but too recent to rewrite
    settled = Digest(article_ids=[1, 2, 3, 4, 5], created_at=NOW - timedelta(minutes=45))
    assert not is_due(settled, [5, 4, 3, 2, 1, 99], NOW)  # same top five
    assert is_due(settled, [1, 2, 3, 4, 6], NOW)  # top stories changed
    assert is_due(Digest(article_ids=[1], created_at=NOW - timedelta(hours=4)), [1], NOW)


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
        return DigestOut(summary_en="Today the main stories are " + "x" * 40, summary_es="Hoy destaca " + "y" * 40,
                         bullets_en=["• Brazil heads to a runoff.", " "], bullets_es=["- Brasil irá a segunda vuelta."])


SECTION = {"reuters": "world", "ars": "ai", "hn": "front"}


@pytest.fixture
async def stories(session, monkeypatch):
    rows = [
        Article(source=src, external_id=f"{src}{i}", url=f"https://a.test/{src}{i}", url_normalized=f"a.test/{src}{i}",
                title=f"{src} story {i}", section=SECTION[src], published_at=NOW - timedelta(hours=1),
                global_score=0.9 - i / 100, ai_summary_en=f"Description {i}")
        for src in ("reuters", "ars", "hn") for i in range(7)
    ]
    session.add_all(rows)
    await session.commit()
    monkeypatch.setattr(digest, "SessionLocal", lambda: _Reuse(session))
    return rows


async def test_refresh_writes_one_brief_mixing_world_and_tech(session, stories):
    ai = FakeAI()
    assert await digest.refresh_digest(ai, now=NOW) == 1
    saved = (await session.scalars(select(Digest))).all()
    assert [d.kind for d in saved] == ["general"]
    by_id = {a.id: a for a in stories}
    picked = [by_id[i] for i in saved[0].article_ids]
    world = [a for a in picked if a.source == "reuters"]
    assert len(world) == digest.PER_SIDE and len(picked) == 2 * digest.PER_SIDE  # both sides, evenly
    assert "[reuters/world]" in ai.prompts[0] and "[ars/ai]" in ai.prompts[0]
    assert saved[0].bullets_en == ["Brazil heads to a runoff"]  # cleaned: no marker, no period
    assert saved[0].bullets_es == ["Brasil irá a segunda vuelta"]

    assert await digest.refresh_digest(ai, now=NOW + timedelta(minutes=5)) == 0  # not due yet
    assert len(ai.prompts) == 1


async def test_falls_back_to_the_lite_model(session, stories, monkeypatch):
    from app.ai.base import AIError

    class Overloaded(FakeAI):
        async def generate_json(self, prompt, schema, model, **kw):
            self.prompts.append(model)
            if model == digest.get_settings().gemini_model_flash:
                raise AIError("Gemini 429 after 5 attempts")
            return await super().generate_json(prompt, schema, **kw)

    monkeypatch.setattr(digest, "_flash_paused_until", digest.datetime.min.replace(tzinfo=UTC))
    ai = Overloaded()
    assert await digest.refresh_digest(ai, now=NOW) == 1
    assert (await session.scalar(select(Digest))).model == digest.get_settings().gemini_model_lite
    # after a 429, Flash is left alone for a while
    await session.delete(await session.scalar(select(Digest)))
    await session.commit()
    assert await digest.refresh_digest(ai, now=NOW + timedelta(minutes=30)) == 1
    assert ai.prompts.count(digest.get_settings().gemini_model_flash) == 1
