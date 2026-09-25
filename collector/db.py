"""Supabase access layer for the collector.

Uses the SERVICE ROLE key (bypasses RLS) and must only ever run server-side
(local dev or GitHub Actions), never in the browser.

Import of ``supabase`` is lazy so unit tests and ``--dry-run`` work without the
package or credentials installed.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Iterable

from config import SUPABASE_SERVICE_ROLE_KEY, SUPABASE_URL


def get_client():
    """Create a Supabase client from env credentials. Raises if unconfigured."""
    if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
        raise RuntimeError(
            "SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY not set. "
            "Fill them in .env, or run the collector with --dry-run."
        )
    from supabase import create_client  # lazy import

    return create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)


# ---------------------------------------------------------------------------
# sources
# ---------------------------------------------------------------------------
def sync_sources(client, sources: list[dict[str, Any]]) -> dict[str, int]:
    """Upsert sources.yaml into the sources table; return {name: id}."""
    rows = [
        {
            "name": s["name"],
            "url": s["url"],
            "type": s["type"],
            "credibility": float(s.get("credibility", 0.5)),
            "enabled": bool(s.get("enabled", False)),
        }
        for s in sources
    ]
    if rows:
        client.table("sources").upsert(rows, on_conflict="name").execute()
    resp = client.table("sources").select("id,name").execute()
    return {r["name"]: r["id"] for r in resp.data}


def update_source_health(
    client, source_id: int, ok: bool, error: str | None = None
) -> None:
    patch: dict[str, Any] = {}
    if ok:
        patch["last_success"] = _now_iso()
        patch["last_error"] = None
    else:
        patch["last_error"] = (error or "")[:1000]
    client.table("sources").update(patch).eq("id", source_id).execute()


# ---------------------------------------------------------------------------
# articles
# ---------------------------------------------------------------------------
def existing_url_hashes(client, hashes: Iterable[str]) -> set[str]:
    """Return which of ``hashes`` already exist in the articles table."""
    hashes = list({h for h in hashes if h})
    found: set[str] = set()
    # chunk to keep the "in" filter a sane size
    for i in range(0, len(hashes), 200):
        chunk = hashes[i : i + 200]
        resp = (
            client.table("articles")
            .select("url_hash")
            .in_("url_hash", chunk)
            .execute()
        )
        found.update(r["url_hash"] for r in resp.data)
    return found


def insert_articles(client, rows: list[dict[str, Any]]) -> int:
    """Insert new article rows. Uses upsert on url to be safe against races."""
    if not rows:
        return 0
    client.table("articles").upsert(rows, on_conflict="url", ignore_duplicates=True).execute()
    return len(rows)


# ---------------------------------------------------------------------------
# runs
# ---------------------------------------------------------------------------
def start_run(client, job: str) -> int | None:
    resp = client.table("runs").insert({"job": job}).execute()
    return resp.data[0]["id"] if resp.data else None


def finish_run(
    client,
    run_id: int | None,
    *,
    new_articles: int = 0,
    new_stories: int = 0,
    ai_calls: int = 0,
    errors: Any = None,
) -> None:
    if run_id is None:
        return
    client.table("runs").update(
        {
            "finished_at": _now_iso(),
            "new_articles": new_articles,
            "new_stories": new_stories,
            "ai_calls": ai_calls,
            "errors": errors,
        }
    ).eq("id", run_id).execute()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# settings / email alerts / digest
# ---------------------------------------------------------------------------
def get_settings(client) -> dict[str, Any]:
    try:
        resp = client.table("settings").select("*").eq("id", 1).single().execute()
        return resp.data or {}
    except Exception:  # noqa: BLE001 - fall back to config defaults
        return {}


_STORY_EMAIL_COLS = (
    "id,headline,summary,category,video_score,rank_score,source_count,first_seen_at"
)


def get_alert_candidates(client, threshold: float, since_iso: str, limit: int) -> list[dict[str, Any]]:
    """Enriched, un-alerted stories at/above the threshold, newest window."""
    if limit <= 0:
        return []
    resp = (
        client.table("stories")
        .select(_STORY_EMAIL_COLS)
        .gte("rank_score", threshold)
        .is_("alerted_at", "null")
        .not_.is_("ai_model_used", "null")
        .gte("first_seen_at", since_iso)
        .order("rank_score", desc=True)
        .limit(limit)
        .execute()
    )
    return resp.data


def count_recent_alerts(client, since_iso: str) -> int:
    resp = (
        client.table("stories")
        .select("id", count="exact")
        .gte("alerted_at", since_iso)
        .execute()
    )
    return resp.count or 0


def mark_stories_alerted(client, ids: list[str], when_iso: str) -> None:
    for i in range(0, len(ids), 100):
        client.table("stories").update({"alerted_at": when_iso}).in_(
            "id", ids[i : i + 100]
        ).execute()


def get_digest_stories(client, since_iso: str, limit: int) -> list[dict[str, Any]]:
    resp = (
        client.table("stories")
        .select(_STORY_EMAIL_COLS)
        .not_.is_("ai_model_used", "null")
        .gte("first_seen_at", since_iso)
        .order("rank_score", desc=True)
        .limit(limit)
        .execute()
    )
    return resp.data


# ---------------------------------------------------------------------------
# youtube_trends
# ---------------------------------------------------------------------------
def insert_youtube_trends(client, rows: list[dict[str, Any]]) -> int:
    if not rows:
        return 0
    client.table("youtube_trends").insert(rows).execute()
    return len(rows)


def get_recent_trends(client, hours: int = 6, limit: int = 15) -> list[dict[str, Any]]:
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
    resp = (
        client.table("youtube_trends")
        .select("video_id,channel,title,views,view_velocity,topic_keywords,captured_at")
        .gte("captured_at", cutoff)
        .order("view_velocity", desc=True)
        .limit(limit)
        .execute()
    )
    return resp.data


def get_trending_keywords(client, hours: int = 6, top_n: int = 15) -> list[str]:
    """Frequency-ranked topic keywords from recent trend captures."""
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
    resp = (
        client.table("youtube_trends")
        .select("topic_keywords")
        .gte("captured_at", cutoff)
        .order("view_velocity", desc=True)
        .limit(60)
        .execute()
    )
    from collections import Counter

    counts: Counter[str] = Counter()
    for r in resp.data:
        for kw in r.get("topic_keywords") or []:
            if kw:
                counts[kw] += 1
    return [kw for kw, _ in counts.most_common(top_n)]


def get_best_ideas_for(client, story_ids: list[str]) -> dict[str, dict[str, Any]]:
    """Return one representative video idea per story (first found)."""
    out: dict[str, dict[str, Any]] = {}
    if not story_ids:
        return out
    resp = (
        client.table("video_ideas")
        .select("story_id,title,hook,format")
        .in_("story_id", story_ids)
        .execute()
    )
    for r in resp.data:
        out.setdefault(r["story_id"], r)
    return out


# ---------------------------------------------------------------------------
# stories / clustering / video_ideas
# ---------------------------------------------------------------------------
def get_articles_without_story(client, limit: int = 2000) -> list[dict[str, Any]]:
    resp = (
        client.table("articles")
        .select("id,title,snippet,published_at,source_id,reddit_score,reddit_comments")
        .is_("story_id", "null")
        .order("published_at", desc=False)
        .limit(limit)
        .execute()
    )
    return resp.data


def get_recent_stories(client, hours: int) -> list[dict[str, Any]]:
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
    resp = (
        client.table("stories")
        .select("id,headline,first_seen_at,last_updated_at")
        .gte("first_seen_at", cutoff)
        .execute()
    )
    return resp.data


def source_credibility_map(client) -> dict[int, dict[str, Any]]:
    resp = client.table("sources").select("id,name,credibility").execute()
    return {r["id"]: r for r in resp.data}


def create_story(client, fields: dict[str, Any]) -> str:
    resp = client.table("stories").insert(fields).execute()
    return resp.data[0]["id"]


def update_story(client, story_id: str, fields: dict[str, Any]) -> None:
    client.table("stories").update(fields).eq("id", story_id).execute()


def set_article_story(client, article_ids: list[int], story_id: str) -> None:
    if not article_ids:
        return
    for i in range(0, len(article_ids), 100):
        chunk = article_ids[i : i + 100]
        client.table("articles").update({"story_id": story_id}).in_("id", chunk).execute()


def insert_video_ideas(
    client, story_id: str, ideas: list[Any], generated_on_demand: bool = False
) -> None:
    rows = [
        {
            "story_id": story_id,
            "title": idea.title,
            "hook": idea.hook,
            "format": idea.format,
            "angle": idea.angle,
            "generated_on_demand": generated_on_demand,
        }
        for idea in ideas
    ]
    if rows:
        client.table("video_ideas").insert(rows).execute()


def get_used_rejected(client, limit: int = 30) -> list[dict[str, Any]]:
    resp = (
        client.table("stories")
        .select("headline,category,status")
        .in_("status", ["used", "rejected"])
        .order("last_updated_at", desc=True)
        .limit(limit)
        .execute()
    )
    return resp.data


def aggregate_story_signals(
    client, story_ids: list[str], cred_map: dict[int, dict[str, Any]]
) -> dict[str, dict[str, Any]]:
    """For each story, aggregate distinct source count, summed Reddit
    engagement, and best source credibility from its articles."""
    agg: dict[str, dict[str, Any]] = {}
    if not story_ids:
        return agg
    for i in range(0, len(story_ids), 100):
        chunk = story_ids[i : i + 100]
        resp = (
            client.table("articles")
            .select("story_id,source_id,reddit_score,reddit_comments")
            .in_("story_id", chunk)
            .execute()
        )
        for r in resp.data:
            sid = r["story_id"]
            a = agg.setdefault(
                sid,
                {"source_ids": set(), "reddit_score": 0, "reddit_comments": 0, "best_cred": 0.0},
            )
            a["source_ids"].add(r["source_id"])
            a["reddit_score"] += r.get("reddit_score") or 0
            a["reddit_comments"] += r.get("reddit_comments") or 0
            cred = (cred_map.get(r["source_id"]) or {}).get("credibility") or 0.0
            a["best_cred"] = max(a["best_cred"], float(cred))
    for a in agg.values():
        a["source_count"] = len(a["source_ids"])
    return agg


def get_unenriched_stories(client, limit: int) -> list[str]:
    """Stories that haven't been AI-enriched yet (newest first)."""
    resp = (
        client.table("stories")
        .select("id")
        .is_("ai_model_used", "null")
        .order("first_seen_at", desc=True)
        .limit(limit)
        .execute()
    )
    return [r["id"] for r in resp.data]


def get_stories_for_rerank(client, hours: int) -> list[dict[str, Any]]:
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
    resp = (
        client.table("stories")
        .select("id,headline,video_score,credibility,first_seen_at")
        .gte("first_seen_at", cutoff)
        .execute()
    )
    return resp.data
