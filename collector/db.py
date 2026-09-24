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
        .select("id,video_score,credibility,first_seen_at")
        .gte("first_seen_at", cutoff)
        .execute()
    )
    return resp.data
