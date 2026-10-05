"""Pure per-source parsers. They take the raw response so they can be tested with recorded fixtures."""

import calendar
import re
from datetime import UTC, date, datetime
from urllib.parse import quote

import feedparser

from app.ingest.normalize import html_to_text
from app.ingest.types import ParsedArticle, ParsedComment

# Sections of interest per source (section → feeds). A story returned by several feeds keeps the
# last section that returns it.
ARS_FEEDS = {
    "ai": ["https://arstechnica.com/ai/feed/"],
    "biz-it": ["https://arstechnica.com/information-technology/feed/"],
    "security": ["https://arstechnica.com/security/feed/"],
}

# Reuters has no RSS: Google News filtered by path. The /technology path only returns a few stories
# per week, so it is complemented with a search on technology terms.
REUTERS_QUERIES = {
    "world": ["site:reuters.com/world when:2d"],
    "technology": [
        "site:reuters.com/technology when:7d",
        'site:reuters.com (AI OR semiconductors OR chipmaker OR software OR cybersecurity OR "big tech") when:2d',
    ],
}

# /front: the stories that made the front page on a given day. It is HN's summary of the day;
# the live front page is too noisy. robots.txt asks for 30 s between requests.
HN_FRONT_URL = "https://news.ycombinator.com/front"
HN_ITEM_URL = "https://hacker-news.firebaseio.com/v0/item/{id}.json"
ALGOLIA_ITEM_URL = "https://hn.algolia.com/api/v1/items/{id}"


def reuters_feed_url(query: str) -> str:
    return f"https://news.google.com/rss/search?q={quote(query)}&hl=en-US&gl=US&ceid=US:en"


_FRONT_ID = re.compile(r'<tr class="athing submission" id="(\d+)"')


def parse_hn_front(html: str) -> list[int]:
    """Story ids on /front, in page order."""
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


def hn_front_url(day: date) -> str:
    return f"{HN_FRONT_URL}?day={day.isoformat()}"


def parse_hn_item(
    item: dict | None, *, section: str = "front", front_day: date | None = None, front_rank: int | None = None
) -> ParsedArticle | None:
    if not item or item.get("type") not in ("story", "poll") or item.get("dead") or item.get("deleted"):
        return None
    points = item.get("score", 0)
    return ParsedArticle(
        source="hn", external_id=str(item["id"]),
        url=item.get("url") or f"https://news.ycombinator.com/item?id={item['id']}",
        title=item["title"].strip(), summary=_short(item.get("text")), section=section,
        published_at=datetime.fromtimestamp(item["time"], tz=UTC), author=item.get("by"),
        hn_points=points, hn_comment_count=item.get("descendants", 0),
        hn_front_day=front_day, hn_front_rank=front_rank,
    )


def flatten_algolia_tree(story: dict) -> list[ParsedComment]:
    """Algolia's nested tree → flat rows with parent, depth and position."""
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
