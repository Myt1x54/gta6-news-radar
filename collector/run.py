"""Collector v1 (Phase 2).

Pipeline: fetch every enabled source -> parse -> GTA 6 relevance filter ->
normalize URL + hash -> dedupe (in-run and against the DB) -> insert into the
articles table. Clustering into stories and AI enrichment come in Phase 3.

Usage:
    python collector/run.py            # live: writes to Supabase
    python collector/run.py --dry-run  # fetch + parse only, no DB writes
    python collector/run.py --limit 3  # only the first N enabled sources
"""

from __future__ import annotations

import argparse
import sys
import time
import traceback
from typing import Any

import httpx

# Politeness delay (seconds) between consecutive requests to the same rate-
# limited host. Reddit returns 429 on bursts from datacenter IPs.
REDDIT_MIN_INTERVAL = 5.0
REDDIT_RETRY_SLEEP = 12.0  # wait then retry once on a 429

import db
import processing
from config import AI_BATCH_SIZE, AI_MAX_STORIES_PER_RUN
from fetchers import (
    fetch_source,
    get_reddit_token,
    reddit_oauth_available,
)
from normalize import is_gta6_relevant, normalize_url, url_hash
from sources import enabled_sources


def _is_gta6_scoped(source: dict[str, Any]) -> bool:
    """Sources that are already GTA 6-scoped, so we keep every item without a
    keyword check: the GTA 6 Google News searches and the r/GTA6 subreddit."""
    if source["type"] == "google_news":
        return True
    if source["type"] == "reddit" and "/r/gta6" in source["url"].lower():
        return True
    return False


def build_rows(
    items: list[dict[str, Any]],
    source: dict[str, Any],
    source_id: int | None,
) -> list[dict[str, Any]]:
    """Turn fetched items into article rows, applying the relevance filter and
    normalizing URLs. Deduplicates within this batch by url_hash."""
    scoped = _is_gta6_scoped(source)
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for it in items:
        url = it.get("url")
        if not url:
            continue
        if not scoped and not is_gta6_relevant(it.get("title"), it.get("snippet")):
            continue
        h = url_hash(url)
        if h in seen:
            continue
        seen.add(h)
        published = it.get("published_at")
        rows.append(
            {
                "source_id": source_id,
                "url": normalize_url(url),
                "url_hash": h,
                "title": it.get("title"),
                "snippet": it.get("snippet"),
                "published_at": published.isoformat() if published else None,
                "reddit_score": it.get("reddit_score"),
                "reddit_comments": it.get("reddit_comments"),
            }
        )
    return rows


def run(dry_run: bool = False, limit: int | None = None, no_ai: bool = False) -> int:
    sources = enabled_sources()
    if limit:
        sources = sources[:limit]

    client = None
    run_id = None
    name_to_id: dict[str, int] = {}
    if not dry_run:
        client = db.get_client()
        name_to_id = db.sync_sources(client, sources)
        run_id = db.start_run(client, "collect")

    total_candidates = 0
    total_new = 0
    new_stories = 0
    ai_calls = 0
    errors: dict[str, str] = {}

    # retries=2 helps with flaky TLS/connect errors on some feeds.
    transport = httpx.HTTPTransport(retries=2)
    with httpx.Client(transport=transport, timeout=30) as http:
        # One Reddit OAuth token per run (reliable + upvote/comment counts).
        reddit_token = None
        if reddit_oauth_available():
            try:
                reddit_token = get_reddit_token(http)
                print("  [reddit] OAuth token acquired")
            except Exception as exc:  # noqa: BLE001 - fall back to .rss
                print(f"  [reddit] OAuth failed, using .rss fallback: {exc}")

        all_rows: list[dict[str, Any]] = []
        last_reddit_at = 0.0
        for source in sources:
            sid = name_to_id.get(source["name"])
            try:
                if source["type"] == "reddit":
                    wait = REDDIT_MIN_INTERVAL - (time.monotonic() - last_reddit_at)
                    if wait > 0:
                        time.sleep(wait)
                    last_reddit_at = time.monotonic()
                    items = _fetch_reddit_with_retry(source, http, reddit_token)
                else:
                    items = fetch_source(source, http)
                rows = build_rows(items, source, sid)
                all_rows.extend(rows)
                total_candidates += len(rows)
                print(f"  [ok]   {source['name']:<28} {len(items):>3} items -> {len(rows):>3} GTA6")
                if client and sid:
                    db.update_source_health(client, sid, ok=True)
            except Exception as exc:  # noqa: BLE001 - record and continue
                msg = f"{type(exc).__name__}: {exc}"
                errors[source["name"]] = msg
                print(f"  [FAIL] {source['name']:<28} {msg}")
                if client and sid:
                    db.update_source_health(client, sid, ok=False, error=msg)

        # De-dupe across the whole run, then against the DB, then insert.
        if not dry_run and all_rows:
            deduped = _dedupe_batch(all_rows)
            already = db.existing_url_hashes(client, (r["url_hash"] for r in deduped))
            fresh = [r for r in deduped if r["url_hash"] not in already]
            total_new = db.insert_articles(client, fresh)

    # --- Phase 3: cluster -> enrich -> rank -------------------------------
    reranked = 0
    if not dry_run:
        print("-" * 60)
        new_ids, attached = processing.cluster_and_store(client)
        new_stories = len(new_ids)
        print(f"clustering: +{new_stories} new stories, {attached} articles joined existing")

        if not no_ai:
            pending = db.get_unenriched_stories(client, AI_MAX_STORIES_PER_RUN)
            ai_calls = processing.enrich_new_stories(client, pending, batch_size=AI_BATCH_SIZE)
            print(f"AI enrichment: {len(pending)} stories -> {ai_calls} AI calls")

        reranked = processing.rerank_recent(client)
        print(f"ranking: {reranked} stories rescored")

        db.finish_run(
            client,
            run_id,
            new_articles=total_new,
            new_stories=new_stories,
            ai_calls=ai_calls,
            errors=errors or None,
        )

    print("-" * 60)
    print(f"sources: {len(sources)}  |  candidates: {total_candidates}  |  errors: {len(errors)}")
    if dry_run:
        print("DRY RUN — nothing written to the database.")
    else:
        print(
            f"new articles: {total_new}  |  new stories: {new_stories}  |  "
            f"AI calls: {ai_calls}  |  reranked: {reranked}"
        )
    # Individual source failures are expected (flaky feeds) and are recorded in
    # the DB; they must NOT fail the CI job. Only hard errors (caught in main)
    # return non-zero.
    return 0


def _fetch_reddit_with_retry(source: dict[str, Any], http: httpx.Client, token: str | None):
    """Fetch a Reddit source, retrying once after a pause on a 429."""
    try:
        return fetch_source(source, http, token)
    except httpx.HTTPStatusError as exc:
        if exc.response is not None and exc.response.status_code == 429:
            time.sleep(REDDIT_RETRY_SLEEP)
            return fetch_source(source, http, token)
        raise


def _dedupe_batch(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Keep the first row per url_hash across all sources in this run."""
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for r in rows:
        if r["url_hash"] in seen:
            continue
        seen.add(r["url_hash"])
        out.append(r)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="GTA 6 News Radar collector")
    ap.add_argument("--dry-run", action="store_true", help="fetch/parse only, no DB writes")
    ap.add_argument("--limit", type=int, default=None, help="only first N enabled sources")
    ap.add_argument("--no-ai", action="store_true", help="skip AI enrichment (cluster+rank only)")
    args = ap.parse_args()
    try:
        return run(dry_run=args.dry_run, limit=args.limit, no_ai=args.no_ai)
    except Exception:  # noqa: BLE001
        traceback.print_exc()
        return 2


if __name__ == "__main__":
    sys.exit(main())
