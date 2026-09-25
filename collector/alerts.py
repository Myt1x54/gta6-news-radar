"""Breaking-news email alerts (PROJECT_BRIEF §9).

Called at the end of a collect run. Sends at most one bundled email per run of
enriched stories whose rank_score >= threshold and that haven't been alerted yet,
capped at MAX_ALERTS_PER_HOUR stories/hour and suppressed during quiet hours
(held stories go out in a later run since alerted_at stays NULL).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import db
from config import (
    ALERT_THRESHOLD,
    ALERT_TO,
    APP_TIMEZONE,
    MAX_ALERTS_PER_HOUR,
    QUIET_HOURS_END,
    QUIET_HOURS_START,
)
from emailer.sender import email_configured, send_email
from emailer.templates import render_alert_email


def is_quiet_hour(hour: int, start: int, end: int) -> bool:
    """True if `hour` (0-23) falls in the quiet window. Handles midnight wrap."""
    if start == end:
        return False
    if start < end:
        return start <= hour < end
    return hour >= start or hour < end


def _local_hour(now_utc: datetime, tz: str) -> int:
    try:
        return now_utc.astimezone(ZoneInfo(tz)).hour
    except Exception:  # noqa: BLE001 - tz db missing; fall back to UTC+5 (PKT)
        return (now_utc.hour + 5) % 24


def send_breaking_alerts(client, now: datetime | None = None) -> int:
    """Send bundled breaking alerts. Returns number of stories alerted."""
    now = now or datetime.now(timezone.utc)

    if not email_configured() or not ALERT_TO:
        return 0

    settings = db.get_settings(client)
    if settings.get("email_enabled") is False:
        return 0

    threshold = float(settings.get("alert_threshold") or ALERT_THRESHOLD)
    q_start = int(settings.get("quiet_hours_start", QUIET_HOURS_START))
    q_end = int(settings.get("quiet_hours_end", QUIET_HOURS_END))

    if is_quiet_hour(_local_hour(now, APP_TIMEZONE), q_start, q_end):
        return 0  # hold — stories stay un-alerted and go out after quiet hours

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
