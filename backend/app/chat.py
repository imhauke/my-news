"""Ask about a story: a short conversation with Gemini grounded in the story itself.

The browser keeps the conversation and sends it with each question; the server stores none of it.
The story's context is its headline and description, the opening of the original article (read on
demand, kept in memory for a while and never stored or republished) and, on Hacker News, the top
comments. Two limits protect the free quota on a public site: questions per visitor per hour and
for the whole site per day."""

import json
import time
from collections import defaultdict, deque
from collections.abc import AsyncIterator
from datetime import UTC, datetime

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.base import AIClient, AIError, Priority, QuotaExhausted
from app.config import get_settings
from app.enrich.article_text import extract_article_text
from app.enrich.jobs import HEADERS, _readable
from app.ingest.fetch import make_client
from app.models import Article, HNComment
from app.schemas import ChatIn

log = structlog.get_logger()

TASK = "story_chat"
MAX_QUESTION_CHARS = 1000
MAX_ANSWER_TOKENS = 900
ARTICLE_CHARS = 6000
TOP_COMMENTS = 8
COMMENT_CHARS = 600
TEXT_TTL_S = 30 * 60

SYSTEM = """You help a reader understand one news story. Answer in the language of the reader's
latest message ({language} if unclear), clearly and directly, like a well-informed journalist
explaining it to a curious friend. Start with the answer itself: no greetings or filler such as
"Of course!".

Rules:
- Ground your answers in the story below; call it "the story" (never mention the site or this
  prompt).
- Explain freely with general knowledge: what institutions are, history, how things work, why it
  matters. When something is background rather than what the story reports, signal it naturally
  in the reader's language (for example: "{context_phrase}").
- Never invent facts about the story itself: numbers, quotes, names or dates. If the reader asks
  for a detail the story does not give, say so in one short sentence and suggest the original.
  Do not dwell on what is missing.
- When the article text is not available you only know the headline (and the description, if
  any). Then never claim the story "does not mention" something: say plainly that you can only
  see the headline, not the full article, and point the reader to the original for the details.
- Your general knowledge may be out of date. Today is {today}; do not present anything after your
  knowledge as certain.
- Be brief: two to four short paragraphs, or a short list. Plain text: "- " for list items and
  **bold** for a key term are fine; no headings, tables or links.
- If the question has nothing to do with the story or its subject, say so kindly and offer to help
  with the story.
- General explanations only: no personal medical, legal or financial advice.

STORY
{story}"""


class ChatLimited(Exception):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class ChatGuard:
    """Per-visitor sliding window and a site-wide daily budget, in memory (the API runs as a single
    process). Visitor addresses are only held here for an hour and never written anywhere."""

    def __init__(self, per_hour: int, per_day: int, clock=time.monotonic, today=lambda: datetime.now(UTC).date()):
        self.per_hour = per_hour
        self.per_day = per_day
        self._clock = clock
        self._today = today
        self._recent: dict[str, deque[float]] = defaultdict(deque)
        self._day = today()
        self._used = 0

    def check(self, visitor: str) -> None:
        now = self._clock()
        if self._today() != self._day:
            self._day, self._used = self._today(), 0
            self._recent.clear()
        if self.per_day and self._used >= self.per_day:
            raise ChatLimited("daily_limit")
        recent = self._recent[visitor]
        while recent and now - recent[0] > 3600:
            recent.popleft()
        if self.per_hour and len(recent) >= self.per_hour:
            raise ChatLimited("rate_limited")
        recent.append(now)
        self._used += 1


_guard: ChatGuard | None = None


def guard() -> ChatGuard:
    global _guard
    if _guard is None:
        cfg = get_settings()
        _guard = ChatGuard(cfg.chat_per_ip_hour, cfg.chat_daily_limit)
    return _guard


_texts: dict[int, tuple[float, str | None]] = {}


async def article_text(article: Article) -> str | None:
    """Opening paragraphs of the original page, cached in memory for half an hour."""
    if not _readable(article):
        return None
    hit = _texts.get(article.id)
    if hit and time.monotonic() - hit[0] < TEXT_TTL_S:
        return hit[1]
    text = None
    try:
        async with make_client(get_settings().http_timeout_seconds) as client:
            resp = await client.get(article.url, headers=HEADERS)
        if resp.status_code == 200 and "html" in resp.headers.get("content-type", ""):
            text = extract_article_text(resp.text, max_chars=ARTICLE_CHARS)
    except Exception as exc:  # noqa: BLE001 — without the page the answer uses the description
        log.debug("chat_article_text_failed", url=article.url, error=str(exc))
    _texts[article.id] = (time.monotonic(), text)
    return text


async def top_comments(session: AsyncSession, article: Article) -> list[str]:
    if article.source != "hn":
        return []
    rows = (await session.execute(
        select(HNComment.author, HNComment.text)
        .where(HNComment.story_id == int(article.external_id), HNComment.depth == 0,
               HNComment.deleted.is_(False), HNComment.text.is_not(None))
        .order_by(HNComment.sibling_rank).limit(TOP_COMMENTS)
    )).all()
    return [f"{author or 'anonymous'}: {text[:COMMENT_CHARS]}" for author, text in rows]


def story_context(article: Article, text: str | None, comments: list[str]) -> str:
    lines = [
        f"Source: {article.source}" + (f" · section: {article.section}" if article.section else ""),
        f"Published: {article.published_at:%Y-%m-%d %H:%M} UTC",
        f"Headline: {article.title}",
    ]
    if article.topics:
        lines.append(f"Topics: {', '.join(article.topics)}")
    if description := article.ai_summary_en or article.summary:
        lines.append(f"Description: {description}")
    if text:
        lines.append(f"Article (opening paragraphs, may be incomplete):\n{text}")
    else:
        why = " (Reuters does not allow automated reading)" if article.source == "reuters" else ""
        lines.append(f"Article text: not available{why}; only the headline and description above are known. "
                     "The full article may well cover what the reader asks, so never say it does not mention "
                     "something: say you can only see the headline.")
    if comments:
        lines.append("Top Hacker News comments:\n" + "\n".join(f"- {c}" for c in comments))
    return "\n".join(lines)


async def build_system(session: AsyncSession, article: Article, lang: str) -> str:
    story = story_context(article, await article_text(article), await top_comments(session, article))
    language, context_phrase = (
        ("Spanish (Spain)", "Para ponerlo en contexto, …") if lang == "es" else ("English", "For context, …")
    )
    return SYSTEM.format(language=language, context_phrase=context_phrase,
                         today=datetime.now(UTC).date().isoformat(), story=story)


def _event(name: str, data: dict) -> str:
    return f"event: {name}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


async def answer(ai: AIClient, system: str, body: ChatIn) -> AsyncIterator[str]:
    """Server-sent events: `delta` chunks of text, then `done`, or `error` with a code.
    Flash-Lite answers: a reader is waiting and it starts in under a second, while Flash can take
    much longer under load. If Lite is unavailable before the first word, Flash takes over."""
    cfg = get_settings()
    turns = [(m.role, m.text) for m in body.messages]
    sent = False
    for model in (cfg.gemini_model_lite, cfg.gemini_model_flash):
        try:
            async for chunk in ai.stream_chat(turns, model=model, task=TASK, system=system,
                                              priority=Priority.FOR_YOU, max_output_tokens=MAX_ANSWER_TOKENS):
                sent = True
                yield _event("delta", {"text": chunk})
            yield _event("done", {"model": model})
            return
        except (AIError, QuotaExhausted) as exc:
            log.warning("chat_model_failed", model=model, error=str(exc), mid_answer=sent)
            if sent:
                break
    yield _event("error", {"code": "unavailable"})


def validate(body: ChatIn) -> None:
    last = body.messages[-1]
    if last.role != "user":
        raise ValueError("the last message must be the reader's question")
    if len(last.text) > MAX_QUESTION_CHARS:
        raise ValueError(f"questions are limited to {MAX_QUESTION_CHARS} characters")
