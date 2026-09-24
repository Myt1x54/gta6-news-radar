from datetime import datetime, timezone

from run import _dedupe_batch, _is_gta6_scoped, build_rows

RSS_SOURCE = {"name": "IGN", "url": "https://ign.com/feed", "type": "rss"}
GNEWS_SOURCE = {
    "name": "Google News - GTA 6",
    "url": "https://news.google.com/rss/search?q=GTA6",
    "type": "google_news",
}
GTA6_SUB = {"name": "r/GTA6", "url": "https://www.reddit.com/r/GTA6/new/.json", "type": "reddit"}
GTA_SUB = {"name": "r/GTA", "url": "https://www.reddit.com/r/GTA/new/.json", "type": "reddit"}


def _item(url, title, snippet=None):
    return {
        "url": url,
        "title": title,
        "snippet": snippet,
        "published_at": datetime(2025, 9, 22, tzinfo=timezone.utc),
        "reddit_score": None,
        "reddit_comments": None,
    }


def test_scoped_detection():
    assert _is_gta6_scoped(GNEWS_SOURCE)
    assert _is_gta6_scoped(GTA6_SUB)
    assert not _is_gta6_scoped(RSS_SOURCE)
    assert not _is_gta6_scoped(GTA_SUB)


def test_build_rows_filters_non_relevant_for_broad_source():
    items = [
        _item("https://ign.com/gta6", "GTA 6 delayed again"),
        _item("https://ign.com/zelda", "New Zelda announced"),
    ]
    rows = build_rows(items, RSS_SOURCE, source_id=1)
    assert len(rows) == 1
    assert rows[0]["title"] == "GTA 6 delayed again"
    assert rows[0]["source_id"] == 1
    assert rows[0]["published_at"] == "2025-09-22T00:00:00+00:00"


def test_build_rows_keeps_all_for_scoped_source():
    items = [
        _item("https://news.google.com/x", "Map details surface"),
        _item("https://news.google.com/y", "Release window rumor"),
    ]
    rows = build_rows(items, GNEWS_SOURCE, source_id=2)
    assert len(rows) == 2  # no keyword filter applied


def test_build_rows_dedupes_within_batch():
    items = [
        _item("https://ign.com/gta6?utm_source=a", "GTA 6 news"),
        _item("https://ign.com/gta6?utm_source=b", "GTA 6 news"),  # same after normalize
    ]
    rows = build_rows(items, RSS_SOURCE, source_id=1)
    assert len(rows) == 1


def test_dedupe_batch_across_sources():
    rows = [
        {"url_hash": "h1", "url": "a"},
        {"url_hash": "h2", "url": "b"},
        {"url_hash": "h1", "url": "a-dupe"},
    ]
    out = _dedupe_batch(rows)
    assert [r["url_hash"] for r in out] == ["h1", "h2"]
