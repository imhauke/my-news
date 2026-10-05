"""Parsers puros por fuente. Reciben la respuesta cruda para poder probarlos con respuestas grabadas."""

import calendar
import re
from datetime import UTC, datetime
from urllib.parse import quote

import feedparser

from app.ingest.normalize import html_to_text
from app.ingest.types import ParsedArticle, ParsedComment

# Secciones que interesan de cada fuente (sección → feeds). Una noticia que aparece en varias
# búsquedas se queda con la última sección que la trae.
ARS_FEEDS = {
    "ai": ["https://arstechnica.com/ai/feed/"],
    "biz-it": ["https://arstechnica.com/information-technology/feed/"],
    "security": ["https://arstechnica.com/security/feed/"],
}

# Reuters no tiene RSS: Google News filtrado por ruta. La ruta /technology solo devuelve unas
# pocas noticias por semana, así que se completa con una búsqueda por términos de tecnología.
REUTERS_QUERIES = {
    "world": ["site:reuters.com/world when:2d"],
    "technology": [
        "site:reuters.com/technology when:7d",
        'site:reuters.com (AI OR semiconductors OR chipmaker OR software OR cybersecurity OR "big tech") when:2d',
    ],
}

# /front: las historias que pasaron por la portada el día anterior. Es el resumen del día de HN;
# la portada en vivo mete demasiado ruido. robots.txt pide 30 s entre peticiones.
HN_FRONT_URL = "https://news.ycombinator.com/front"
HN_ITEM_URL = "https://hacker-news.firebaseio.com/v0/item/{id}.json"
ALGOLIA_ITEM_URL = "https://hn.algolia.com/api/v1/items/{id}"


def reuters_feed_url(query: str) -> str:
    return f"https://news.google.com/rss/search?q={quote(query)}&hl=en-US&gl=US&ceid=US:en"


_FRONT_ID = re.compile(r'<tr class="athing submission" id="(\d+)"')


def parse_hn_front(html: str) -> list[int]:
    """Ids de historia de /front, en el orden en que aparecen."""
    return [int(i) for i in _FRONT_ID.findall(html)]


def _entry_datetime(entry: feedparser.FeedParserDict) -> datetime:
    parsed = entry.get("published_parsed") or entry.get("updated_parsed")
    if not parsed:
        return datetime.now(UTC)
    return datetime.fromtimestamp(calendar.timegm(parsed), tz=UTC)


def _short(text: str | None, limit: int = 500) -> str | None:
    clean = html_to_text(text)
    return (clean[: limit - 1] + "…") if len(clean) > limit else (clean or None)


def parse_ars_feed(xml: str, section: str) -> list[ParsedArticle]:
    out = []
    for e in feedparser.parse(xml).entries:
        if not e.get("link") or not e.get("title"):
            continue
        out.append(ParsedArticle(
            source="ars", external_id=e.get("id") or e.link, url=e.link, title=e.title.strip(),
            published_at=_entry_datetime(e), summary=_short(e.get("summary")), section=section,
            author=e.get("author"),
        ))
    return out


def parse_reuters_feed(xml: str, section: str) -> list[ParsedArticle]:
    out = []
    for e in feedparser.parse(xml).entries:
        title = re.sub(r"\s+-\s+Reuters$", "", e.get("title", "")).strip()
        if not e.get("link") or not title:
            continue
        out.append(ParsedArticle(
            source="reuters", external_id=e.get("id") or e.link, url=e.link, title=title,
            published_at=_entry_datetime(e), summary=None, section=section,
        ))
    return out


def parse_hn_item(item: dict | None, *, section: str = "front") -> ParsedArticle | None:
    if not item or item.get("type") != "story" or item.get("dead") or item.get("deleted"):
        return None
    points = item.get("score", 0)
    return ParsedArticle(
        source="hn", external_id=str(item["id"]),
        url=item.get("url") or f"https://news.ycombinator.com/item?id={item['id']}",
        title=item["title"].strip(), summary=_short(item.get("text")), section=section,
        published_at=datetime.fromtimestamp(item["time"], tz=UTC), author=item.get("by"),
        hn_points=points, hn_comment_count=item.get("descendants", 0),
    )


def flatten_algolia_tree(story: dict) -> list[ParsedComment]:
    """Árbol anidado de Algolia → filas planas con padre, profundidad y posición."""
    story_id = int(story["id"])
    out: list[ParsedComment] = []

    def walk(node: dict, parent_id: int, depth: int, rank: int) -> None:
        deleted = node.get("text") is None and node.get("author") is None
        out.append(ParsedComment(
            id=int(node["id"]), story_id=story_id, parent_id=parent_id,
            author=node.get("author"), text=html_to_text(node.get("text")) or None,
            created_at=datetime.fromtimestamp(node["created_at_i"], tz=UTC),
            depth=depth, sibling_rank=rank, deleted=deleted,
        ))
        for i, child in enumerate(node.get("children") or []):
            walk(child, int(node["id"]), depth + 1, i)

    for i, child in enumerate(story.get("children") or []):
        walk(child, story_id, 0, i)
    return out
