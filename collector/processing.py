"""Phase 3 DB-driven pipeline stages: cluster -> enrich -> rank.

Called by run.py after new articles are inserted. Each stage is a thin layer of
DB glue around the pure logic in clustering.py / ai/ / ranking.py.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Iterable

import db
from ai.enrich import enrich_stories
from clustering import assign_clusters, significant_tokens
from config import (
    CLUSTER_WINDOW_HOURS,
    RANK_RECOMPUTE_MAX_AGE_HOURS,
)
from ranking import compute_rank_score


def _parse_dt(value: Any) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _chunks(seq: list, n: int) -> Iterable[list]:
    for i in range(0, len(seq), n):
        yield seq[i : i + n]


# ---------------------------------------------------------------------------
# Stage 1: cluster articles into stories
# ---------------------------------------------------------------------------
def cluster_and_store(client) -> tuple[list[str], int]:
    """Cluster all story-less articles, attaching to recent stories or creating
    new ones. Returns (new_story_ids, articles_attached_to_existing)."""
    articles = db.get_articles_without_story(client)
    if not articles:
        return [], 0

    cred_map = db.source_credibility_map(client)
    for a in articles:
        a["published_at"] = _parse_dt(a.get("published_at"))

    existing = db.get_recent_stories(client, CLUSTER_WINDOW_HOURS)
    seeds = [
        {
            "story_id": s["id"],
            "title": s["headline"],
            "anchor_time": _parse_dt(s.get("last_updated_at") or s.get("first_seen_at")),
        }
        for s in existing
    ]

    results = assign_clusters(articles, seeds)

    new_clusters: dict[Any, list[dict[str, Any]]] = {}
    existing_attach: dict[str, list[int]] = {}
    for r in results:
        art = r["article"]
        if r["story_id"]:
            existing_attach.setdefault(r["story_id"], []).append(art["id"])
        else:
            new_clusters.setdefault(r["cluster_key"], []).append(art)

    # attach to existing stories
    attached = 0
    for sid, ids in existing_attach.items():
        db.set_article_story(client, ids, sid)
        db.update_story(client, sid, {"last_updated_at": _now_iso()})
        attached += len(ids)

    # create a story per new cluster
    now = datetime.now(timezone.utc)
    new_story_ids: list[str] = []
    for arts in new_clusters.values():
        arts_sorted = sorted(arts, key=lambda a: a.get("published_at") or now)
        rep = arts_sorted[0]
        first_seen = min((a["published_at"] for a in arts if a.get("published_at")), default=now)
        best_cred = max(
            (float((cred_map.get(a["source_id"]) or {}).get("credibility") or 0.0) for a in arts),
            default=0.0,
        )
        fields = {
            "headline": (rep.get("title") or "GTA 6 story")[:500],
            "first_seen_at": first_seen.isoformat(),
            "last_updated_at": _now_iso(),
            "source_count": len({a["source_id"] for a in arts}),
            "credibility": round(best_cred, 3),
            "rank_score": 0,
            "status": "new",
        }
        sid = db.create_story(client, fields)
        db.set_article_story(client, [a["id"] for a in arts], sid)
        new_story_ids.append(sid)

    return new_story_ids, attached


# ---------------------------------------------------------------------------
# Stage 2: AI-enrich new stories (batched)
# ---------------------------------------------------------------------------
def enrich_new_stories(client, story_ids: list[str], *, batch_size: int = 6) -> int:
    if not story_ids:
        return 0

    cred_map = db.source_credibility_map(client)
    used_rejected = db.get_used_rejected(client)
    trends = _recent_trend_topics(client)

    total_calls = 0
    for batch in _chunks(story_ids, batch_size):
        payloads = []
        for sid in batch:
            arts = (
                client.table("articles")
                .select("title,snippet,source_id")
                .eq("story_id", sid)
                .limit(10)
                .execute()
            ).data
            titles = [a["title"] for a in arts if a.get("title")]
            names = {(cred_map.get(a["source_id"]) or {}).get("name") for a in arts}
            names.discard(None)
            best_cred = max(
                (float((cred_map.get(a["source_id"]) or {}).get("credibility") or 0.0) for a in arts),
                default=0.0,
            )
            snippet = " ".join((a.get("snippet") or "") for a in arts)[:600]
            payloads.append(
                {
                    "ref": sid,
                    "title": titles[0] if titles else "",
                    "snippet": snippet,
                    "sources": sorted(names),
                    "source_count": len(names),
                    "credibility_hint": best_cred,
                }
            )

        try:
            results, model, calls = enrich_stories(
                payloads, trends=trends, used_rejected=used_rejected
            )
        except Exception as exc:  # noqa: BLE001 - don't lose the whole run
            print(f"  [ai] batch failed: {type(exc).__name__}: {exc}")
            continue
        total_calls += calls

        for sid in batch:
            e = results.get(sid)
            if not e:
                continue
            db.update_story(
                client,
                sid,
                {
                    "headline": e.headline[:500],
                    "summary": e.summary,
                    "category": e.category,
                    "credibility": e.credibility,
                    "credibility_reason": e.credibility_reason,
                    "video_score": e.video_score,
                    "video_score_reason": e.video_score_reason,
                    "ai_model_used": model,
                    "last_updated_at": _now_iso(),
                },
            )
            db.insert_video_ideas(client, sid, e.video_ideas)

    return total_calls


def _recent_trend_topics(client) -> list[str]:
    """Frequency-ranked YouTube trend keywords for prompt context (Phase 7).
    Returns [] until the youtube_trends table has recent data."""
    try:
        return db.get_trending_keywords(client, hours=6, top_n=15)
    except Exception:  # noqa: BLE001
        return []


# ---------------------------------------------------------------------------
# Stage 3: (re)compute rank_score for recent stories
# ---------------------------------------------------------------------------
def _trend_match(headline: str | None, trend_tokens: set[str]) -> float:
    """0-1 score for how well a story matches currently-trending YT topics."""
    if not trend_tokens:
        return 0.0
    shared = len(significant_tokens(headline) & trend_tokens)
    if shared >= 2:
        return 1.0
    if shared == 1:
        return 0.6
    return 0.0


def rerank_recent(client) -> int:
    cred_map = db.source_credibility_map(client)
    stories = db.get_stories_for_rerank(client, RANK_RECOMPUTE_MAX_AGE_HOURS)
    ids = [s["id"] for s in stories]
    signals = db.aggregate_story_signals(client, ids, cred_map)
    trend_tokens = set(db.get_trending_keywords(client, hours=6, top_n=25))
    # Weights come from the settings table (dashboard-tunable), else config defaults.
    weights = db.get_settings(client).get("weights") or None

    n = 0
    for s in stories:
        sig = signals.get(s["id"], {})
        story_for_rank = {
            "video_score": s.get("video_score") or 0,
            "credibility": s.get("credibility") or 0.0,
            "source_count": sig.get("source_count", 1),
            "reddit_score": sig.get("reddit_score", 0),
            "reddit_comments": sig.get("reddit_comments", 0),
            "youtube_trend_match": _trend_match(s.get("headline"), trend_tokens),
            "first_seen_at": _parse_dt(s.get("first_seen_at")),
        }
        score = compute_rank_score(story_for_rank, weights=weights)
        db.update_story(
            client,
            s["id"],
            {"rank_score": score, "source_count": sig.get("source_count", 1)},
        )
        n += 1
    return n
