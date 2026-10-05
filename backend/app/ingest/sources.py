"""Pure per-source parsers. They take the raw response so they can be tested with recorded fixtures."""

import calendar
import html
import re
from datetime import UTC, date, datetime
from urllib.parse import urlsplit
from xml.etree import ElementTree

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

# Reuters has no RSS. Its news sitemap (listed in robots.txt for every crawler) is near real time
# and carries the canonical URL, whose first path segment is the site section. Each page holds 50
# entries (about an hour); three pages per refresh leave margin if the worker was down for a while.
REUTERS_SITEMAP_URL = "https://www.reuters.com/arc/outboundfeeds/news-sitemap/?outputType=xml&from={offset}"
REUTERS_SITEMAP_PAGES = 3
REUTERS_PAGE_SIZE = 50
REUTERS_SECTIONS = ("world", "technology")

# /front: the stories that made the front page on a given day. It is HN's summary of the day;
# the live front page is too noisy. robots.txt asks for 30 s between requests.
HN_FRONT_URL = "https://news.ycombinator.com/front"
HN_ITEM_URL = "https://hacker-news.firebaseio.com/v0/item/{id}.json"
ALGOLIA_ITEM_URL = "https://hn.algolia.com/api/v1/items/{id}"


def reuters_sitemap_urls() -> list[str]:
    return [REUTERS_SITEMAP_URL.format(offset=i * REUTERS_PAGE_SIZE) for i in range(REUTERS_SITEMAP_PAGES)]


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
        media = [m.get("url") for m in e.get("media_content", []) if m.get("medium", "image") == "image"]
        out.append(ParsedArticle(
            source="ars", external_id=e.get("id") or e.link, url=e.link, title=e.title.strip(),
            published_at=_entry_datetime(e), summary=_short(e.get("summary")), section=section,
            author=e.get("author"), image_url=next((u for u in media if u), None),
        ))
    return out


_NS = {
    "sm": "http://www.sitemaps.org/schemas/sitemap/0.9",
    "news": "http://www.google.com/schemas/sitemap-news/0.9",
    "image": "http://www.google.com/schemas/sitemap-image/1.1",
}
REUTERS_IMAGE_WIDTH = 960  # Reuters' resizer keeps the signed URL valid for other widths


def parse_reuters_sitemap(xml: str) -> list[ParsedArticle]:
    """Stories from Reuters' news sitemap in the sections we follow. The section is the first path
    segment, exactly as on reuters.com, so translations (/es/, /de/…), markets or sports are left out.
    publication_date moves forward when Reuters updates a story, like the "15 mins ago" on the site."""
    out = []
    for url in ElementTree.fromstring(xml).iterfind("sm:url", _NS):
        loc = (url.findtext("sm:loc", "", _NS) or "").strip()
        title = html.unescape(url.findtext("news:news/news:title", "", _NS) or "").strip()
        published = url.findtext("news:news/news:publication_date", "", _NS)
        section = urlsplit(loc).path.strip("/").split("/")[0]
        if section not in REUTERS_SECTIONS or not title or not published:
            continue
        image = (url.findtext("image:image/image:loc", "", _NS) or "").strip() or None
        if image:
            image = re.sub(r"([?&])width=\d+", rf"\g<1>width={REUTERS_IMAGE_WIDTH}", image)
        out.append(ParsedArticle(
            source="reuters", external_id=urlsplit(loc).path, url=loc, title=title,
            published_at=datetime.fromisoformat(published.replace("Z", "+00:00")), section=section,
            image_url=image,
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
