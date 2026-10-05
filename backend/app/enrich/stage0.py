"""Ranking stage 0: once per article and shared by all users, Gemini Flash-Lite assigns a
translated headline, a short description (EN/ES), topics and a global relevance score."""

from pydantic import BaseModel, Field

SYSTEM = """You enrich items for a news reader. For every input item return an object with:
- id: the item's id, unchanged.
- title_es: the headline translated into natural Spanish (Spain), keeping names, products and figures.
- summary_en: one or two plain sentences (max 40 words) saying what the story reports. It must add at
  least one concrete detail that is not in the headline (who, what exactly, figures, why it matters).
- summary_es: the same description in natural Spanish (Spain).
- topics: 1-4 short lowercase English topics, e.g. "semiconductors", "ukraine war", "rust".
- topics_es: the same topics in Spanish, same order and count, e.g. "semiconductores", "guerra de ucrania".
- global_score: 0-1, how important the story is for a well-informed general reader today.

Rules:
- Use only the information in the title, excerpt and article text. Never add names, numbers, dates,
  causes or outcomes that are not stated there.
- If they add nothing beyond the headline, return empty strings for summary_en and summary_es: a
  restated headline is not a description. Still translate the title and assign topics and global_score.
- Do not start with "This article" or "The story"; state the content directly.
- Return every input id exactly once."""


class EnrichedItem(BaseModel):
    id: int
    title_es: str = Field(max_length=400)
    summary_en: str = Field(default="", max_length=400)
    summary_es: str = Field(default="", max_length=450)
    topics: list[str] = Field(max_length=4)
    topics_es: list[str] = Field(max_length=4)
    global_score: float = Field(ge=0, le=1)


class EnrichmentBatch(BaseModel):
    items: list[EnrichedItem]


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
