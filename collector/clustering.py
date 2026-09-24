"""Group articles about the same event into one "story" (cluster).

Approach (per PROJECT_BRIEF §6.1): fuzzy title similarity within a time window.
New articles can either join an existing recent story or form a new cluster, and
new articles also cluster among themselves in the same pass.

Pure functions over plain dicts — no DB access — so it's easy to unit-test.
The DB glue (loading recent stories, writing assignments) lives in run.py.
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import Any

from rapidfuzz import fuzz

from config import CLUSTER_WINDOW_HOURS, TITLE_SIMILARITY_THRESHOLD

# Strip a trailing " - Publisher" / " | Publisher" suffix (common in Google
# News and outlet titles) so it doesn't distort similarity.
_PUBLISHER_SUFFIX_RE = re.compile(r"\s+[-|–—]\s+[^-|–—]{1,40}$")
_APOS_RE = re.compile(r"[’'`]")
_NON_ALNUM_RE = re.compile(r"[^a-z0-9 ]+")
_WS_RE = re.compile(r"\s+")


def normalize_title(title: str | None) -> str:
    """Lowercase, drop a trailing publisher suffix and punctuation."""
    if not title:
        return ""
    t = title.strip()
    t = _PUBLISHER_SUFFIX_RE.sub("", t)
    t = t.lower()
    t = _APOS_RE.sub("", t)  # drop apostrophes so "collector's" -> "collectors"
    t = _NON_ALNUM_RE.sub(" ", t)
    return _WS_RE.sub(" ", t).strip()


def title_similarity(a: str | None, b: str | None) -> float:
    """0-100 similarity between two titles (order/extra-word tolerant)."""
    na, nb = normalize_title(a), normalize_title(b)
    if not na or not nb:
        return 0.0
    return float(fuzz.token_set_ratio(na, nb))


def _anchor_time(dt: datetime | None) -> datetime:
    if dt is None:
        return datetime.now(timezone.utc)
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def _within_window(a: datetime, b: datetime, hours: int) -> bool:
    return abs((a - b).total_seconds()) <= hours * 3600


def assign_clusters(
    articles: list[dict[str, Any]],
    existing_stories: list[dict[str, Any]] | None = None,
    *,
    threshold: int = TITLE_SIMILARITY_THRESHOLD,
    window_hours: int = CLUSTER_WINDOW_HOURS,
) -> list[dict[str, Any]]:
    """Assign each article to a story cluster.

    Args:
        articles: dicts with at least ``id``, ``title``, ``published_at``.
        existing_stories: recent stories to (possibly) attach to; dicts with
            ``story_id``, ``title``, ``anchor_time``.

    Returns a list parallel to sorted input, each item:
        {"article": <article>,
         "story_id": <existing id or None>,
         "cluster_key": <stable key: ("existing", id) or ("new", n)>}
    New clusters share a ``("new", n)`` key so the caller can create one story
    per new cluster and attach all its articles.
    """
    clusters: list[dict[str, Any]] = []
    for s in existing_stories or []:
        clusters.append(
            {
                "key": ("existing", s["story_id"]),
                "story_id": s["story_id"],
                "title": s["title"],
                "time": _anchor_time(s.get("anchor_time")),
            }
        )

    results: list[dict[str, Any]] = []
    next_new = 0

    # Oldest first so a cluster's representative is its earliest article.
    ordered = sorted(articles, key=lambda a: _anchor_time(a.get("published_at")))
    for art in ordered:
        atime = _anchor_time(art.get("published_at"))
        best = None
        best_score = 0.0
        for c in clusters:
            if not _within_window(atime, c["time"], window_hours):
                continue
            score = title_similarity(art.get("title"), c["title"])
            if score > best_score:
                best_score = score
                best = c

        if best is not None and best_score >= threshold:
            # keep the cluster's anchor time at the most recent member
            if atime > best["time"]:
                best["time"] = atime
            results.append(
                {"article": art, "story_id": best["story_id"], "cluster_key": best["key"]}
            )
        else:
            key = ("new", next_new)
            next_new += 1
            clusters.append(
                {"key": key, "story_id": None, "title": art.get("title"), "time": atime}
            )
            results.append({"article": art, "story_id": None, "cluster_key": key})

    return results
