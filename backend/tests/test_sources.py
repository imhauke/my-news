import json
from pathlib import Path

from app.ingest import sources

FIX = Path(__file__).parent / "fixtures"


def test_parse_ars_feed_skips_entries_without_title():
    items = sources.parse_ars_feed((FIX / "ars.xml").read_text(), "ai")
    assert len(items) == 1
    a = items[0]
    assert (a.source, a.section, a.author) == ("ars", "ai", "Jane Doe")
    assert a.summary == "Rules changed (https://x.test)."
    assert a.image_url == "https://cdn.arstechnica.net/chips-1152x648.jpg"


def test_parse_reuters_sitemap_keeps_followed_sections_only():
    items = sources.parse_reuters_sitemap((FIX / "reuters_sitemap.xml").read_text())
    assert [(a.section, a.title) for a in items] == [
        ("world", "Spanish PM Sanchez gambles on November 29 snap election"),
        ("technology", "Chipmaker shares jump & AI demand grows"),
    ]
    world = items[0]
    assert world.url == "https://www.reuters.com/world/europe/spanish-pm-sanchez-2026-10-05/"
    assert world.external_id == "/world/europe/spanish-pm-sanchez-2026-10-05/"
    assert world.published_at.isoformat() == "2026-10-05T08:45:12+00:00"
    assert world.image_url == "https://www.reuters.com/resizer/v2/ABC.jpg?auth=xyz&smart=true&width=960"
    assert items[1].image_url is None


def test_parse_hn_item_keeps_front_stories_and_skips_non_stories():
    item = {"id": 1, "type": "story", "title": " T ", "score": 10, "time": 1790000000, "descendants": 3}
    kept = sources.parse_hn_item(item)
    assert kept and kept.section == "front" and kept.title == "T" and kept.hn_points == 10
    assert kept.url == "https://news.ycombinator.com/item?id=1"  # Ask HN: links to the thread
    assert sources.parse_hn_item({**item, "type": "job"}) is None
    assert sources.parse_hn_item({**item, "dead": True}) is None


def test_hn_front_url_asks_for_an_explicit_day():
    from datetime import date

    assert sources.hn_front_url(date(2026, 10, 4)) == "https://news.ycombinator.com/front?day=2026-10-04"
    kept = sources.parse_hn_item(
        {"id": 2, "type": "poll", "title": "P", "time": 1790000000}, front_day=date(2026, 10, 4), front_rank=7
    )
    assert kept and (kept.hn_front_day, kept.hn_front_rank) == (date(2026, 10, 4), 7)


def test_parse_hn_front_ids_in_order():
    html = (FIX / "hn_front.html").read_text()
    assert sources.parse_hn_front(html) == [45000003, 45000001, 45000002]


def test_feeds_cover_requested_sections():
    assert set(sources.ARS_FEEDS) == {"ai", "biz-it", "security"}
    assert sources.REUTERS_SECTIONS == ("world", "technology")
    assert [u.rsplit("=", 1)[1] for u in sources.reuters_sitemap_urls()] == ["0", "50", "100"]


def test_flatten_algolia_tree():
    rows = sources.flatten_algolia_tree(json.loads((FIX / "algolia_item.json").read_text()))
    by_id = {r.id: r for r in rows}
    assert [(r.id, r.depth, r.sibling_rank) for r in rows] == [(101, 0, 0), (103, 1, 0), (102, 0, 1)]
    assert by_id[101].parent_id == 100 and by_id[103].parent_id == 101
    assert by_id[102].deleted and not by_id[101].deleted
    assert "Rust (https://rust-lang.org)" in by_id[101].text
