"""Build the AI enrichment prompt (system + user text).

Batches several stories into one call to save quota. The user text carries:
  - recent YouTube trend topics (so ideas match what's hot),
  - the creator's recent Used/Rejected picks (so ideas match their taste),
  - the stories to enrich, each with a stable ``ref``.
"""

from __future__ import annotations

import json
from typing import Any

SYSTEM_PROMPT = """You are a sharp research assistant for a YouTube channel that \
covers Grand Theft Auto VI (GTA 6). You judge news for its potential as a YouTube \
video and pitch concrete ideas.

For EACH story you receive, decide if it is genuinely about GTA 6 (not GTA 5 / GTA \
Online / older titles), then summarize and score it.

Return ONLY valid JSON, no prose, no markdown fences, matching exactly:
{
  "stories": [
    {
      "ref": "<echo the story's ref>",
      "is_gta6": true,
      "headline": "clean rewritten headline",
      "summary": "2-3 sentence neutral summary",
      "category": "official|leak|rumor|trailer_media|price_date|gameplay_detail|community_drama|other",
      "credibility": 0.0,
      "credibility_reason": "one line",
      "video_score": 0,
      "video_score_reason": "one line on why it would/wouldn't work as a video",
      "video_ideas": [
        {"title": "YouTube-style title", "hook": "first 10 seconds", "format": "news_breakdown|reaction|theory|everything_we_know|comparison|short", "angle": "one line"}
      ]
    }
  ]
}

Rules:
- credibility is 0.0-1.0. video_score is an integer 0-10.
- Give 2-3 video_ideas per story.
- If is_gta6 is false, still return the object but keep video_score low and ideas empty.
- Echo each ref exactly. Return one object per input story, in any order."""


def _context_block(
    trends: list[str] | None,
    used_rejected: list[dict[str, Any]] | None,
) -> str:
    parts: list[str] = []
    if trends:
        parts.append(
            "Currently trending GTA 6 topics on YouTube (favor ideas that ride these):\n"
            + "\n".join(f"- {t}" for t in trends[:15])
        )
    if used_rejected:
        lines = []
        for h in used_rejected[:30]:
            status = h.get("status", "?")
            cat = h.get("category", "?")
            head = h.get("headline", "")
            lines.append(f"- [{status}/{cat}] {head}")
        parts.append(
            "The creator's recent picks (USED = they made a video; REJECTED = they "
            "passed). Bias your scores/ideas toward what they USE:\n" + "\n".join(lines)
        )
    return "\n\n".join(parts)


def build_prompt(
    stories: list[dict[str, Any]],
    *,
    trends: list[str] | None = None,
    used_rejected: list[dict[str, Any]] | None = None,
) -> tuple[str, str]:
    """Return (system_prompt, user_prompt).

    Each story dict should have: ref, title, snippet, sources (list[str]),
    source_count, credibility_hint (0-1 from source credibility).
    """
    context = _context_block(trends, used_rejected)

    payload = []
    for s in stories:
        payload.append(
            {
                "ref": str(s["ref"]),
                "title": s.get("title") or "",
                "snippet": (s.get("snippet") or "")[:600],
                "sources": s.get("sources") or [],
                "source_count": s.get("source_count", 1),
                "source_credibility_hint": round(float(s.get("credibility_hint") or 0.0), 2),
            }
        )

    user_parts = []
    if context:
        user_parts.append(context)
    user_parts.append(
        "Enrich these stories and return the JSON described. Stories:\n"
        + json.dumps(payload, ensure_ascii=False, indent=2)
    )
    return SYSTEM_PROMPT, "\n\n".join(user_parts)
