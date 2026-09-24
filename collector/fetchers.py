"""Fetch and parse each source type into a common item shape.

Parsing (``parse_feed`` / ``parse_reddit``) is split from network I/O so it can
be unit-tested with sample payloads. ``fetch_source`` does the actual HTTP.

Every parser returns a list of dicts with this shape (missing keys => None):
    {
      "url": str,
      "title": str | None,
      "snippet": str | None,
      "published_at": datetime | None,   # timezone-aware UTC
      "reddit_score": int | None,
      "reddit_comments": int | None,
    }
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Any

import feedparser

from config import REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET, USER_AGENT

_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")


def _clean_text(html: str | None, limit: int = 500) -> str | None:
    if not html:
        return None
    text = _WS_RE.sub(" ", _TAG_RE.sub(" ", html)).strip()
    return text[:limit] or None


def _struct_to_dt(struct: Any) -> datetime | None:
    if not struct:
        return None
    try:
        return datetime(*struct[:6], tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None


def parse_feed(content: str | bytes) -> list[dict[str, Any]]:
    """Parse an RSS/Atom feed (also covers google_news and youtube_rss)."""
    parsed = feedparser.parse(content)
    items: list[dict[str, Any]] = []
    for entry in parsed.entries:
        link = entry.get("link")
        if not link:
            continue
        items.append(
            {
                "url": link,
                "title": (entry.get("title") or "").strip() or None,
                "snippet": _clean_text(entry.get("summary")),
                "published_at": _struct_to_dt(
                    entry.get("published_parsed") or entry.get("updated_parsed")
                ),
                "reddit_score": None,
                "reddit_comments": None,
            }
        )
    return items


def parse_reddit(payload: str | bytes | dict[str, Any]) -> list[dict[str, Any]]:
    """Parse a Reddit ``/new/.json`` or ``/hot/.json`` listing."""
    if isinstance(payload, (str, bytes)):
        payload = json.loads(payload)
    items: list[dict[str, Any]] = []
    for child in payload.get("data", {}).get("children", []):
        d = child.get("data", {})
        permalink = d.get("permalink")
        url = f"https://www.reddit.com{permalink}" if permalink else d.get("url")
        if not url:
            continue
        created = d.get("created_utc")
        items.append(
            {
                "url": url,
                "title": (d.get("title") or "").strip() or None,
                "snippet": _clean_text(d.get("selftext")),
                "published_at": datetime.fromtimestamp(created, tz=timezone.utc)
                if created
                else None,
                "reddit_score": d.get("score"),
                "reddit_comments": d.get("num_comments"),
            }
        )
    return items


def reddit_oauth_available() -> bool:
    return bool(REDDIT_CLIENT_ID and REDDIT_CLIENT_SECRET)


def get_reddit_token(client) -> str:
    """App-only OAuth (client_credentials). Returns a bearer token."""
    resp = client.post(
        "https://www.reddit.com/api/v1/access_token",
        data={"grant_type": "client_credentials"},
        auth=(REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET),
        headers={"User-Agent": USER_AGENT},
        timeout=25,
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


def _to_oauth_url(url: str) -> str:
    """Turn a public reddit listing URL into its oauth.reddit.com JSON form."""
    url = url.replace("www.reddit.com", "oauth.reddit.com").replace(
        "old.reddit.com", "oauth.reddit.com"
    )
    return url.replace("/.rss", "/.json").replace(".rss?", ".json?")


def fetch_source(source: dict[str, Any], client, reddit_token: str | None = None) -> list[dict[str, Any]]:
    """Fetch one source over HTTP and parse it into items.

    ``client`` is an ``httpx.Client``. If ``reddit_token`` is given, Reddit
    sources are fetched via the authenticated JSON API (reliable + engagement
    counts); otherwise they fall back to the open .rss feed. Raises on HTTP
    errors so the caller can record source health.
    """
    stype = source["type"]
    if stype == "html":
        # No HTML-scraping sources are enabled yet; add trafilatura here when
        # a feed-less source is introduced (see PROJECT_BRIEF §5).
        return []

    if stype == "reddit" and reddit_token:
        resp = client.get(
            _to_oauth_url(source["url"]),
            headers={"User-Agent": USER_AGENT, "Authorization": f"bearer {reddit_token}"},
            timeout=25,
            follow_redirects=True,
        )
        resp.raise_for_status()
        return parse_reddit(resp.json())

    resp = client.get(
        source["url"],
        headers={"User-Agent": USER_AGENT, "Accept": "*/*"},
        timeout=25,
        follow_redirects=True,
    )
    resp.raise_for_status()

    if stype == "reddit":
        # Fallback: .rss is open but omits upvote/comment counts; .json is
        # bot-walled for datacenter IPs.
        if ".rss" in source["url"]:
            return parse_feed(resp.content)
        return parse_reddit(resp.json())
    # rss, google_news, youtube_rss all parse as feeds
    return parse_feed(resp.content)
