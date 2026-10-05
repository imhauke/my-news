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


def test_parse_reuters_strips_suffix():
    [a] = sources.parse_reuters_feed((FIX / "reuters.xml").read_text(), "geopolitics")
    assert a.title == "Talks resume in Geneva" and a.source == "reuters"


def test_parse_hn_item_keeps_front_stories_and_skips_non_stories():
    item = {"id": 1, "type": "story", "title": " T ", "score": 10, "time": 1790000000, "descendants": 3}
    kept = sources.parse_hn_item(item)
    assert kept and kept.section == "front" and kept.title == "T" and kept.hn_points == 10
    assert kept.url == "https://news.ycombinator.com/item?id=1"  # Ask HN: enlaza al hilo
    assert sources.parse_hn_item({**item, "type": "job"}) is None
    assert sources.parse_hn_item({**item, "dead": True}) is None


def test_parse_hn_front_ids_in_order():
    html = (FIX / "hn_front.html").read_text()
    assert sources.parse_hn_front(html) == [45000003, 45000001, 45000002]


def test_feeds_cover_requested_sections():
    assert set(sources.ARS_FEEDS) == {"ai", "biz-it", "security"}
    assert set(sources.REUTERS_QUERIES) == {"world", "technology"}
    assert "site%3Areuters.com/world" in sources.reuters_feed_url(sources.REUTERS_QUERIES["world"][0])


def test_flatten_algolia_tree():
    rows = sources.flatten_algolia_tree(json.loads((FIX / "algolia_item.json").read_text()))
    by_id = {r.id: r for r in rows}
    assert [(r.id, r.depth, r.sibling_rank) for r in rows] == [(101, 0, 0), (103, 1, 0), (102, 0, 1)]
    assert by_id[101].parent_id == 100 and by_id[103].parent_id == 101
    assert by_id[102].deleted and not by_id[101].deleted
    assert "Rust (https://rust-lang.org)" in by_id[101].text
