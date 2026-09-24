"""Rebuild all stories from the existing articles (maintenance / tuning tool).

Deletes every story — which, via the schema's foreign keys, cascade-deletes
video_ideas and sets articles.story_id back to NULL — then re-runs clustering,
enrichment (capped per config), and ranking. Use after changing clustering
params. Does NOT re-fetch feeds.

    python collector/recluster.py
"""

from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import db  # noqa: E402
import processing  # noqa: E402
from config import AI_BATCH_SIZE, AI_MAX_STORIES_PER_RUN  # noqa: E402


def main() -> int:
    client = db.get_client()
    before = client.table("stories").select("id", count="exact").execute().count
    print(f"deleting {before} existing stories (cascades ideas, nulls article links)...")
    client.table("stories").delete().gte("first_seen_at", "1900-01-01").execute()

    new_ids, attached = processing.cluster_and_store(client)
    print(f"clustered -> {len(new_ids)} stories")

    pending = db.get_unenriched_stories(client, AI_MAX_STORIES_PER_RUN)
    calls = processing.enrich_new_stories(client, pending, batch_size=AI_BATCH_SIZE)
    print(f"enriched {len(pending)} stories in {calls} AI calls")

    n = processing.rerank_recent(client)
    print(f"reranked {n} stories")
    return 0


if __name__ == "__main__":
    sys.exit(main())
