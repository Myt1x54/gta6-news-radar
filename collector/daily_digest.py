"""Daily digest email: top stories from the last 24h + best idea + trends.

Run by GitHub Actions once a day (04:00 UTC = 09:00 PKT).

    python collector/daily_digest.py
"""

from __future__ import annotations

import sys
import traceback
from datetime import datetime, timedelta, timezone

import db
from config import ALERT_TO, DIGEST_TOP_N
from emailer.sender import email_configured, send_email
from emailer.templates import render_digest_email
from processing import _recent_trend_topics


def run() -> int:
    if not email_configured() or not ALERT_TO:
        print("Email not configured — skipping digest.")
        return 0

    client = db.get_client()
    settings = db.get_settings(client)
    if settings.get("email_enabled") is False:
        print("Email disabled in settings — skipping digest.")
        return 0

    run_id = db.start_run(client, "digest")
    now = datetime.now(timezone.utc)
    since = (now - timedelta(hours=24)).isoformat()

    stories = db.get_digest_stories(client, since, DIGEST_TOP_N)
    ideas = db.get_best_ideas_for(client, [s["id"] for s in stories])
    trends = _recent_trend_topics(client)

    subject, html = render_digest_email(stories, ideas, trends)
    send_email(ALERT_TO, subject, html)
    print(f"Digest sent: {len(stories)} stories to {ALERT_TO}")

    db.finish_run(client, run_id, new_articles=0, new_stories=0)
    return 0


def main() -> int:
    try:
        return run()
    except Exception:  # noqa: BLE001
        traceback.print_exc()
        return 2


if __name__ == "__main__":
    sys.exit(main())
