from fetchers import parse_feed, parse_reddit

SAMPLE_RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel>
  <title>Example</title>
  <item>
    <title>GTA 6 trailer 2 drops today</title>
    <link>https://example.com/gta6-trailer?utm_source=rss</link>
    <description>&lt;p&gt;Rockstar reveals&lt;/p&gt; more.</description>
    <pubDate>Mon, 22 Sep 2025 12:00:00 GMT</pubDate>
  </item>
  <item>
    <title>Unrelated game news</title>
    <link>https://example.com/other</link>
    <description>Nothing here</description>
  </item>
</channel></rss>"""

SAMPLE_REDDIT = {
    "data": {
        "children": [
            {
                "data": {
                    "title": "GTA 6 map leak megathread",
                    "permalink": "/r/GTA6/comments/abc123/gta6_map/",
                    "selftext": "Details inside",
                    "score": 1234,
                    "num_comments": 56,
                    "created_utc": 1695379200,
                }
            }
        ]
    }
}


def test_parse_feed_fields():
    items = parse_feed(SAMPLE_RSS)
    assert len(items) == 2
    first = items[0]
    assert first["url"] == "https://example.com/gta6-trailer?utm_source=rss"
    assert first["title"] == "GTA 6 trailer 2 drops today"
    assert first["snippet"] == "Rockstar reveals more."  # html stripped
    assert first["published_at"].year == 2025
    assert first["reddit_score"] is None


def test_parse_feed_skips_entries_without_link():
    items = parse_feed("<rss><channel><item><title>no link</title></item></channel></rss>")
    assert items == []


def test_parse_reddit_captures_engagement():
    items = parse_reddit(SAMPLE_REDDIT)
    assert len(items) == 1
    it = items[0]
    assert it["url"] == "https://www.reddit.com/r/GTA6/comments/abc123/gta6_map/"
    assert it["title"] == "GTA 6 map leak megathread"
    assert it["reddit_score"] == 1234
    assert it["reddit_comments"] == 56
    assert it["published_at"].year == 2023


def test_parse_reddit_accepts_json_string():
    import json

    items = parse_reddit(json.dumps(SAMPLE_REDDIT))
    assert items[0]["reddit_score"] == 1234
