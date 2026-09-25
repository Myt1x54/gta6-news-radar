from datetime import datetime, timedelta, timezone

import youtube_api
from processing import _trend_match

NOW = datetime(2026, 9, 25, 12, 0, tzinfo=timezone.utc)

VIDEOS_RESPONSE = {
    "items": [
        {
            "id": "vid1",
            "snippet": {
                "title": "GTA 6 Trailer 2 Breakdown - Vice City Map Details",
                "channelTitle": "GTA Central",
                "publishedAt": "2026-09-24T12:00:00Z",  # 24h before NOW
                "tags": ["gta 6", "vice city", "leonida"],
            },
            "statistics": {"viewCount": "240000"},
        }
    ]
}

SEARCH_RESPONSE = {
    "items": [
        {"id": {"kind": "youtube#video", "videoId": "v1"}},
        {"id": {"kind": "youtube#video", "videoId": "v2"}},
        {"id": {"kind": "youtube#channel", "channelId": "c1"}},  # not a video
    ]
}


def test_compute_velocity():
    pub = NOW - timedelta(hours=24)
    assert youtube_api.compute_velocity(240000, pub, NOW) == 10000.0
    assert youtube_api.compute_velocity(0, pub, NOW) == 0.0
    assert youtube_api.compute_velocity(1000, None, NOW) == 0.0


def test_extract_topic_keywords_drops_generic():
    kws = youtube_api.extract_topic_keywords(
        "GTA 6 Trailer 2 Breakdown - Vice City Map", ["gta 6", "vice city"]
    )
    assert "vice" in kws
    assert "city" in kws
    assert "gta" not in kws       # generic, stripped
    assert "the" not in kws       # stopword


def test_parse_search_ids_only_videos():
    assert youtube_api.parse_search_ids(SEARCH_RESPONSE) == ["v1", "v2"]


def test_parse_videos_builds_rows():
    rows = youtube_api.parse_videos(VIDEOS_RESPONSE, NOW)
    assert len(rows) == 1
    r = rows[0]
    assert r["video_id"] == "vid1"
    assert r["views"] == 240000
    assert r["view_velocity"] == 10000.0  # 240k over 24h
    assert r["channel"] == "GTA Central"
    assert isinstance(r["topic_keywords"], list) and r["topic_keywords"]


def test_trend_match_scoring():
    trend = {"vice", "city", "map"}
    assert _trend_match("GTA 6 Vice City map leak surfaces", trend) == 1.0  # >=2
    assert _trend_match("New GTA 6 map teaser", trend) == 0.6               # 1
    assert _trend_match("GTA 6 soundtrack announced", trend) == 0.0         # 0
    assert _trend_match("anything", set()) == 0.0                          # no trends
