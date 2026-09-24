"""Supabase access layer for the collector.

Uses the SERVICE ROLE key (bypasses RLS) and must only ever run server-side
(local dev or GitHub Actions), never in the browser.

Import of ``supabase`` is lazy so unit tests and ``--dry-run`` work without the
package or credentials installed.
"""

from __future__ import annotations

from datetime import datetime, timezone
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
