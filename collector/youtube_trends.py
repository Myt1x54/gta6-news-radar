"""YouTube trend job (PROJECT_BRIEF §7). Runs every 2-3h.

Searches GTA 6 videos from the last 48h, fetches their stats, computes view
velocity + topic keywords, and stores snapshots in the youtube_trends table.
Cheap on quota: one search.list (100u) + one videos.list (1u) per run.

    python collector/youtube_trends.py
"""

from __future__ import annotations

import sys
import traceback
from datetime import datetime, timedelta, timezone

import httpx

import db
import youtube_api
from config import (
    YOUTUBE_API_KEY,
    YOUTUBE_DAILY_QUOTA,
    YOUTUBE_LOOKBACK_HOURS,
    YOUTUBE_QUOTA_SOFT_CAP,
)

SEARCH_QUERY = "GTA 6"


def run() -> int:
    if not YOUTUBE_API_KEY:
        print("YOUTUBE_API_KEY not set — skipping trends job.")
        return 0

    client = db.get_client()
    run_id = db.start_run(client, "youtube")
    now = datetime.now(timezone.utc)
    published_after = (now - timedelta(hours=YOUTUBE_LOOKBACK_HOURS)).isoformat()

    units = 0
    errors = {}
    stored = 0
    try:
        with httpx.Client() as http:
            ids, u1 = youtube_api.search_recent(http, YOUTUBE_API_KEY, SEARCH_QUERY, published_after)
            units += u1
            rows, u2 = youtube_api.fetch_video_stats(http, YOUTUBE_API_KEY, ids, now)
            units += u2

        # keep only rows with real velocity, take the top movers
        rows = [r for r in rows if r.get("view_velocity")]
        rows.sort(key=lambda r: r["view_velocity"], reverse=True)
        stored = db.insert_youtube_trends(client, rows[:40])
    except Exception as exc:  # noqa: BLE001
        errors["youtube"] = f"{type(exc).__name__}: {exc}"
        print(f"  [FAIL] {errors['youtube']}")

    soft_cap = int(YOUTUBE_DAILY_QUOTA * YOUTUBE_QUOTA_SOFT_CAP)
    print(f"trends: stored {stored} videos | units used this run: {units} "
          f"(daily soft cap {soft_cap})")

    db.finish_run(client, run_id, new_articles=0, new_stories=0,
                  errors={"youtube_units": units, **errors} or None)
    return 0 if not errors else 1


def main() -> int:
    try:
        return run()
    except Exception:  # noqa: BLE001
        traceback.print_exc()
        return 2


if __name__ == "__main__":
    sys.exit(main())
