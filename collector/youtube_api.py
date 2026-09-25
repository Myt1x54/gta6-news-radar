"""YouTube Data API v3 helpers for the trends job.

Parsing / math functions are split from the HTTP calls so they're unit-testable
with sample payloads. Quota costs: search.list = 100 units, videos.list = 1 unit.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

API_BASE = "https://www.googleapis.com/youtube/v3"
SEARCH_COST = 100
VIDEOS_COST = 1

_WORD_RE = re.compile(r"[a-z0-9]+")
# Words too generic to be a useful trend topic (GTA boilerplate + video filler).
_STOP = {
    "gta", "grand", "theft", "auto", "vi", "game", "games", "rockstar",
    "the", "a", "an", "of", "for", "to", "in", "on", "and", "or", "new", "ii",
    "video", "videos", "official", "watch", "full", "part", "update", "news",
    "explained", "review", "reaction", "vs", "you", "your", "this", "that",
    "how", "why", "what", "is", "are", "with", "all", "get", "now",
    "has", "was", "were", "not", "shorts", "gaming", "live", "stream",
    "playthrough", "gameplay", "funny", "moments", "best", "top", "his", "her",
}


def _tokens(text: str | None) -> list[str]:
    return [w for w in _WORD_RE.findall((text or "").lower()) if len(w) > 2 and w not in _STOP]


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def compute_velocity(views: int | None, published_at: datetime | None, now: datetime | None = None) -> float:
    """Views per hour since upload (min 1h to avoid brand-new spikes)."""
    if not views or not published_at:
        return 0.0
    now = now or datetime.now(timezone.utc)
    hours = max(1.0, (now - published_at).total_seconds() / 3600.0)
    return round(views / hours, 2)


def extract_topic_keywords(title: str | None, tags: list[str] | None = None, limit: int = 6) -> list[str]:
    """Distinguishing keywords from a video title (+ optional tags), de-duped."""
    words = _tokens(title)
    for tag in (tags or [])[:5]:
        words.extend(_tokens(tag))
    out: list[str] = []
    for w in words:
        if w not in out:
            out.append(w)
    return out[:limit]


def parse_search_ids(payload: dict[str, Any]) -> list[str]:
    ids: list[str] = []
    for item in payload.get("items", []):
        vid = (item.get("id") or {}).get("videoId")
        if vid:
            ids.append(vid)
    return ids


def parse_videos(payload: dict[str, Any], now: datetime | None = None) -> list[dict[str, Any]]:
    """Turn a videos.list response into trend rows (with velocity + keywords)."""
    now = now or datetime.now(timezone.utc)
    rows: list[dict[str, Any]] = []
    for item in payload.get("items", []):
        snippet = item.get("snippet", {})
        stats = item.get("statistics", {})
        published = _parse_dt(snippet.get("publishedAt"))
        views = int(stats["viewCount"]) if stats.get("viewCount") is not None else None
        title = snippet.get("title")
        rows.append(
            {
                "video_id": item.get("id"),
                "channel": snippet.get("channelTitle"),
                "title": title,
                "published_at": published.isoformat() if published else None,
                "views": views,
                "view_velocity": compute_velocity(views, published, now),
                "topic_keywords": extract_topic_keywords(title, snippet.get("tags")),
            }
        )
    return rows


# ---------------------------------------------------------------------------
# HTTP (network)
# ---------------------------------------------------------------------------
def search_recent(http, api_key: str, query: str, published_after_iso: str, max_results: int = 50) -> tuple[list[str], int]:
    resp = http.get(
        f"{API_BASE}/search",
        params={
            "key": api_key,
            "q": query,
            "part": "snippet",
            "type": "video",
            "order": "viewCount",
            "publishedAfter": published_after_iso,
            "maxResults": max_results,
        },
        timeout=25,
    )
    resp.raise_for_status()
    return parse_search_ids(resp.json()), SEARCH_COST


def fetch_video_stats(http, api_key: str, video_ids: list[str], now: datetime | None = None) -> tuple[list[dict[str, Any]], int]:
    if not video_ids:
        return [], 0
    units = 0
    rows: list[dict[str, Any]] = []
    for i in range(0, len(video_ids), 50):
        chunk = video_ids[i : i + 50]
        resp = http.get(
            f"{API_BASE}/videos",
            params={
                "key": api_key,
                "id": ",".join(chunk),
                "part": "snippet,statistics",
            },
            timeout=25,
        )
        resp.raise_for_status()
        rows.extend(parse_videos(resp.json(), now))
        units += VIDEOS_COST
    return rows, units
