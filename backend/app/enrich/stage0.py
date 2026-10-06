"""Ranking stage 0: once per article and shared by all users, Gemini Flash-Lite assigns a
translated headline, a short description (EN/ES), topics and an importance score."""

from datetime import date

from pydantic import BaseModel, Field

# Bump when IMPORTANCE changes: the worker re-scores the last two days with the new criteria.
SCORE_VERSION = 2

IMPORTANCE = """importance: an integer from 1 to 100, how much the story matters to the reader this
  site is written for: a well-informed technology leader, think the CEOs of Google, Apple, OpenAI
  or Anthropic, reading their morning briefing on {today}. They follow:
  - technology and where it is going: AI models and research, chips, platforms, developer tools,
    major launches, big deals and funding, and the regulation of tech;
  - security: serious vulnerabilities, breaches, attacks and state cyber activity;
  - the state of the world as far as it moves markets, supply chains or policy: wars and
    escalations, elections and changes of government in major countries, sanctions, trade,
    energy and central banks.
  Judge impact (how many people, companies or countries it affects, and how much), novelty (a new
  fact, not an update, recap or commentary) and consequence (it changes decisions, markets or the
  field). Anchors:
  - 90-100: historic or field-changing (a major war escalation, a frontier model that resets the
    state of the art, a global market shock);
  - 70-89: major news this reader must know today;
  - 40-69: notable within its area;
  - 15-39: niche, minor updates, incremental product news, opinion or analysis;
  - 1-14: trivia, local, promotional or off-topic items.
  Use the whole range and spread items out; do not give most items the same few values."""

SYSTEM = """You enrich items for a news reader. For every input item return an object with:
- id: the item's id, unchanged.
- title_es: the headline translated into natural Spanish (Spain), keeping names, products and figures.
- summary_en: one or two plain sentences (max 40 words) saying what the story reports. It must add at
  least one concrete detail that is not in the headline (who, what exactly, figures, why it matters).
- summary_es: the same description in natural Spanish (Spain).
- topics: 1-4 short lowercase English topics, e.g. "semiconductors", "ukraine war", "rust".
- topics_es: the same topics in Spanish, same order and count, e.g. "semiconductores", "guerra de ucrania".
- {importance}

Rules:
- Use only the information in the title, excerpt and article text. Never add names, numbers, dates,
  causes or outcomes that are not stated there.
- If they add nothing beyond the headline, return empty strings for summary_en and summary_es: a
  restated headline is not a description. Still translate the title and assign topics and global_score.
- Do not start with "This article" or "The story"; state the content directly.
- Return every input id exactly once."""

RESCORE_SYSTEM = """You rate news items. For every input item return its id, unchanged, and:
- {importance}

Use only the information given; return every input id exactly once."""


def system_prompt(today: date) -> str:
    return SYSTEM.replace("{importance}", IMPORTANCE.replace("{today}", today.isoformat()))


def rescore_prompt(today: date) -> str:
    return RESCORE_SYSTEM.replace("{importance}", IMPORTANCE.replace("{today}", today.isoformat()))


class EnrichedItem(BaseModel):
    id: int
    title_es: str = Field(max_length=400)
    summary_en: str = Field(default="", max_length=400)
    summary_es: str = Field(default="", max_length=450)
    topics: list[str] = Field(max_length=4)
    topics_es: list[str] = Field(max_length=4)
    importance: int = Field(ge=1, le=100)


class EnrichmentBatch(BaseModel):
    items: list[EnrichedItem]


class ScoredItem(BaseModel):
    id: int
    importance: int = Field(ge=1, le=100)


class ScoreBatch(BaseModel):
    items: list[ScoredItem]


def build_prompt(articles: list[dict]) -> str:
    lines = []
    for a in articles:
        lines.append(f"[id={a['id']}] source={a['source']}" + (f" section={a['section']}" if a.get("section") else ""))
        lines.append(f"title: {a['title']}")
        if a.get("summary"):
            lines.append(f"excerpt: {a['summary'][:600]}")
        if a.get("body"):
            lines.append(f"article text: {a['body']}")
        lines.append("")
    return "Items:\n\n" + "\n".join(lines)
