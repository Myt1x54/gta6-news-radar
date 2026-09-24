"""Group articles about the same event into one "story" (cluster).

Approach (PROJECT_BRIEF §6.1, tuned in Phase 3.1): match on a title's
*significant* tokens within a time window. Generic words (gta, 6, rockstar,
"reveals"...) are stripped first so that shared boilerplate doesn't merge
unrelated stories, and so that paraphrased coverage of the same event still
merges. A candidate joins a cluster if it matches ANY member of that cluster.

Pure functions over plain dicts — no DB access — so it's easy to unit-test.
The DB glue (loading recent stories, writing assignments) lives in processing.py.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

from rapidfuzz import fuzz

from config import (
    CLUSTER_FUZZY_THRESHOLD,
    CLUSTER_MIN_JACCARD,
    CLUSTER_MIN_SHARED_TOKENS,
    CLUSTER_WINDOW_HOURS,
)

# Strip a trailing " - Publisher" / " | Publisher" suffix.
_PUBLISHER_SUFFIX_RE = re.compile(r"\s+[-|–—]\s+[^-|–—]{1,40}$")
_APOS_RE = re.compile(r"[’'`′]")
_NON_ALNUM_RE = re.compile(r"[^a-z0-9 ]+")
_WS_RE = re.compile(r"\s+")

# Words too generic to help distinguish one GTA 6 event from another.
_STOPWORDS = set(
    "the a an of for to in on at is are was be by with and or vs new latest "
    "reveals reveal revealed unveils unveil shows show reportedly report reports "
    "according has have had will its it this that as from you your".split()
)
_GENERIC = set("gta grand theft auto 6 vi game games rockstar".split())


def normalize_title(title: str | None) -> str:
    """Lowercase, drop a trailing publisher suffix, apostrophes and punctuation."""
    if not title:
        return ""
    t = _PUBLISHER_SUFFIX_RE.sub("", title.strip()).lower()
    t = _APOS_RE.sub("", t)
    t = _NON_ALNUM_RE.sub(" ", t)
    return _WS_RE.sub(" ", t).strip()


def significant_tokens(title: str | None) -> set[str]:
    """The distinguishing tokens of a title (no stopwords / generic GTA words)."""
    return {
        w
        for w in normalize_title(title).split()
        if len(w) > 2 and w not in _STOPWORDS and w not in _GENERIC
    }


def _sig_string(title: str | None) -> str:
    return " ".join(sorted(significant_tokens(title)))


def same_event(
    a: str | None,
    b: str | None,
    *,
    min_shared: int = CLUSTER_MIN_SHARED_TOKENS,
    min_jaccard: float = CLUSTER_MIN_JACCARD,
    fuzzy: int = CLUSTER_FUZZY_THRESHOLD,
) -> bool:
    """True if two titles describe the same event."""
    sa, sb = significant_tokens(a), significant_tokens(b)
    if not sa or not sb:
        return False
    shared = len(sa & sb)
    if shared < min_shared:
        return False
    jaccard = shared / len(sa | sb)
    if jaccard >= min_jaccard:
        return True
    return fuzz.token_set_ratio(_sig_string(a), _sig_string(b)) >= fuzzy


def title_similarity(a: str | None, b: str | None) -> float:
    """0-100 fuzzy similarity over significant tokens (kept for diagnostics)."""
    sa, sb = _sig_string(a), _sig_string(b)
    if not sa or not sb:
        return 0.0
    return float(fuzz.token_set_ratio(sa, sb))


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
    window_hours: int = CLUSTER_WINDOW_HOURS,
) -> list[dict[str, Any]]:
    """Assign each article to a story cluster.

    Args:
        articles: dicts with at least ``id``, ``title``, ``published_at``.
        existing_stories: recent stories to (possibly) attach to; dicts with
            ``story_id``, ``title``, ``anchor_time``.

    Returns a list parallel to sorted input, each item:
        {"article": <article>, "story_id": <existing id or None>,
         "cluster_key": ("existing", id) | ("new", n)}
    """
    # Each cluster tracks its member titles so a candidate can match ANY member.
    clusters: list[dict[str, Any]] = []
    for s in existing_stories or []:
        clusters.append(
            {
                "key": ("existing", s["story_id"]),
                "story_id": s["story_id"],
                "titles": [s["title"]],
                "time": _anchor_time(s.get("anchor_time")),
            }
        )

    results: list[dict[str, Any]] = []
    next_new = 0

    # Oldest first so a cluster forms around its earliest article.
    ordered = sorted(articles, key=lambda a: _anchor_time(a.get("published_at")))
    for art in ordered:
        atime = _anchor_time(art.get("published_at"))
        title = art.get("title")
        match = None
        for c in clusters:
            if not _within_window(atime, c["time"], window_hours):
                continue
            if any(same_event(title, m) for m in c["titles"]):
                match = c
                break

        if match is not None:
            match["titles"].append(title)
            if atime > match["time"]:
                match["time"] = atime
            results.append(
                {"article": art, "story_id": match["story_id"], "cluster_key": match["key"]}
            )
        else:
            key = ("new", next_new)
            next_new += 1
            clusters.append(
                {"key": key, "story_id": None, "titles": [title], "time": atime}
            )
            results.append({"article": art, "story_id": None, "cluster_key": key})

    return results
