"""Breaking-news email alerts (PROJECT_BRIEF §9, adjusted per user).

Called at the end of a collect run. Sends at most one bundled email per run of
enriched stories whose rank_score >= threshold and that haven't been alerted yet,
capped at MAX_ALERTS_PER_HOUR stories/hour. Breaking alerts fire ANY time of day
(no quiet hours — per user request).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import db
from config import ALERT_THRESHOLD, ALERT_TO, MAX_ALERTS_PER_HOUR
from emailer.sender import email_configured, send_email
from emailer.templates import render_alert_email


def send_breaking_alerts(client, now: datetime | None = None) -> int:
    """Send bundled breaking alerts. Returns number of stories alerted."""
    now = now or datetime.now(timezone.utc)

    if not email_configured() or not ALERT_TO:
        return 0

    settings = db.get_settings(client)
    if settings.get("email_enabled") is False:
        return 0

    threshold = float(settings.get("alert_threshold") or ALERT_THRESHOLD)

    recent = db.count_recent_alerts(client, (now - timedelta(hours=1)).isoformat())
    budget = MAX_ALERTS_PER_HOUR - recent
    if budget <= 0:
        return 0

    since = (now - timedelta(hours=48)).isoformat()
    candidates = db.get_alert_candidates(client, threshold, since, budget)
    if not candidates:
        return 0

    subject, html = render_alert_email(candidates)
    send_email(ALERT_TO, subject, html)
    db.mark_stories_alerted(client, [s["id"] for s in candidates], now.isoformat())
    return len(candidates)
