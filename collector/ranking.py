"""Compute a story's rank_score (0-100).

Weighted mix (weights + caps in config.py, mirrored in the settings table):
  video_score, credibility, source_count, reddit_engagement, youtube_trend,
  and a freshness decay (half-life). Each component is normalized to 0-1,
  multiplied by its weight, summed, and scaled to 0-100.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from config import (
    FRESHNESS_HALFLIFE_HOURS,
    RANK_WEIGHTS,
    REDDIT_ENGAGEMENT_CAP,
    SOURCE_COUNT_CAP,
)


def freshness_factor(age_hours: float, halflife_hours: float = FRESHNESS_HALFLIFE_HOURS) -> float:
    """Exponential decay: 1.0 at age 0, 0.5 at one half-life."""
    if age_hours <= 0:
        return 1.0
    return float(0.5 ** (age_hours / halflife_hours))


def _clamp01(x: float) -> float:
    return 0.0 if x < 0 else 1.0 if x > 1 else x


def compute_rank_score(
    story: dict[str, Any],
    *,
    now: datetime | None = None,
    weights: dict[str, float] | None = None,
) -> float:
    """Return a 0-100 rank score for a story dict.

    Recognized story keys (all optional, sensible defaults):
        video_score (0-10), credibility (0-1), source_count (int),
        reddit_score (int), reddit_comments (int),
        youtube_trend_match (0-1), first_seen_at (datetime).
    """
    w = weights or RANK_WEIGHTS
    now = now or datetime.now(timezone.utc)

    video = _clamp01((story.get("video_score") or 0) / 10.0)
    credibility = _clamp01(float(story.get("credibility") or 0.0))
    source_count = _clamp01((story.get("source_count") or 1) / SOURCE_COUNT_CAP)
    engagement = _clamp01(
        ((story.get("reddit_score") or 0) + (story.get("reddit_comments") or 0))
        / REDDIT_ENGAGEMENT_CAP
    )
    youtube = _clamp01(float(story.get("youtube_trend_match") or 0.0))

    first_seen = story.get("first_seen_at")
    if isinstance(first_seen, datetime):
        if first_seen.tzinfo is None:
            first_seen = first_seen.replace(tzinfo=timezone.utc)
        age_hours = max(0.0, (now - first_seen).total_seconds() / 3600.0)
    else:
        age_hours = 0.0
    freshness = freshness_factor(age_hours)

    components = {
        "video_score": video,
        "credibility": credibility,
        "source_count": source_count,
        "reddit_engagement": engagement,
        "youtube_trend": youtube,
        "freshness": freshness,
    }
    score = sum(w.get(k, 0.0) * v for k, v in components.items())
    return round(score * 100, 2)
