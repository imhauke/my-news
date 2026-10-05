"""Spanish translation of Hacker News comments, on demand and cached in hn_comments.

A big thread has hundreds of comments: it is translated in chunks in reading order (top first),
with a budget per request, and nothing is translated twice."""

import asyncio

import structlog
from pydantic import BaseModel, Field
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.base import AIClient, AIError, Priority, QuotaExhausted
from app.config import get_settings
from app.models import HNComment

log = structlog.get_logger()
BATCH_SIZE = 40
MAX_CHARS = 3000

SYSTEM = """You translate Hacker News comments from English into natural Spanish (Spain).
Rules:
- Translate faithfully; keep the tone, including informal or sarcastic comments.
- Keep code, commands, URLs, usernames, product names and quoted identifiers unchanged.
- Keep paragraph breaks and code fences exactly where they are.
- If a comment is already in Spanish, return it unchanged.
- Return every input id exactly once, with its translation in text_es."""


class TranslatedComment(BaseModel):
    id: int
    text_es: str = Field(max_length=12000)


class TranslationBatch(BaseModel):
    items: list[TranslatedComment]


def build_prompt(comments: list[tuple[int, str]]) -> str:
    return "Comments:\n\n" + "\n\n".join(f"[id={cid}]\n{text[:MAX_CHARS]}" for cid, text in comments)


async def translate_comments(session: AsyncSession, comments: list[tuple[int, str]], ai: AIClient) -> int:
    """Translates (id, text) pairs in concurrent batches and stores text_es. Returns how many were
    translated. If the quota runs out, keeps what it got and leaves the rest in English."""
    batches = [comments[i:i + BATCH_SIZE] for i in range(0, len(comments), BATCH_SIZE)]
    wanted = {cid for cid, _ in comments}

    async def run(batch: list[tuple[int, str]]) -> list[TranslatedComment]:
        try:
            result = await ai.generate_json(
                build_prompt(batch), TranslationBatch, model=get_settings().gemini_model_lite,
                task="translate_comments", priority=Priority.HN_ANALYSIS, system=SYSTEM,
            )
            return result.items
        except (AIError, QuotaExhausted) as exc:
            log.warning("translate_batch_failed", error=str(exc), size=len(batch))
            return []

    done = 0
    for items in await asyncio.gather(*(run(b) for b in batches)):
        for item in items:
            if item.id in wanted and item.text_es.strip():
                await session.execute(update(HNComment).where(HNComment.id == item.id).values(text_es=item.text_es))
                wanted.discard(item.id)
                done += 1
    await session.commit()
    return done
