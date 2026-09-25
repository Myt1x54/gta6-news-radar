from datetime import datetime, timezone

import alerts


def _story(i, rank=90):
    return {"id": f"s{i}", "headline": f"Story {i}", "summary": "x", "rank_score": rank}


def _patch(monkeypatch, *, settings=None, recent=0, candidates=None):
    monkeypatch.setattr(alerts, "ALERT_TO", "to@example.com")
    monkeypatch.setattr(alerts, "email_configured", lambda: True)
    monkeypatch.setattr(alerts.db, "get_settings", lambda c: settings or {})
    monkeypatch.setattr(alerts.db, "count_recent_alerts", lambda c, s: recent)
    monkeypatch.setattr(
        alerts.db,
        "get_alert_candidates",
        lambda c, t, s, limit: (candidates or [])[:limit],
    )
    sent = {}
    monkeypatch.setattr(alerts, "send_email", lambda to, subj, html: sent.update(to=to, subj=subj))
    marked = {}
    monkeypatch.setattr(alerts.db, "mark_stories_alerted", lambda c, ids, when: marked.update(ids=ids))
    return sent, marked


def test_sends_bundled_alert_and_marks(monkeypatch):
    sent, marked = _patch(monkeypatch, candidates=[_story(1), _story(2)])
    # 12:00 UTC -> 17:00 PKT (not quiet)
    n = alerts.send_breaking_alerts(None, now=datetime(2026, 9, 25, 12, 0, tzinfo=timezone.utc))
    assert n == 2
    assert sent["to"] == "to@example.com"
    assert marked["ids"] == ["s1", "s2"]


def test_sends_any_time_of_day(monkeypatch):
    # 21:00 UTC = 02:00 PKT — previously quiet; must now still send
    sent, _ = _patch(monkeypatch, candidates=[_story(1)])
    n = alerts.send_breaking_alerts(None, now=datetime(2026, 9, 25, 21, 0, tzinfo=timezone.utc))
    assert n == 1
    assert sent["to"] == "to@example.com"


def test_respects_hourly_budget(monkeypatch):
    sent, _ = _patch(monkeypatch, recent=5, candidates=[_story(1)])
    n = alerts.send_breaking_alerts(None, now=datetime(2026, 9, 25, 12, 0, tzinfo=timezone.utc))
    assert n == 0
    assert "to" not in sent


def test_email_disabled_in_settings(monkeypatch):
    sent, _ = _patch(monkeypatch, settings={"email_enabled": False}, candidates=[_story(1)])
    n = alerts.send_breaking_alerts(None, now=datetime(2026, 9, 25, 12, 0, tzinfo=timezone.utc))
    assert n == 0
    assert "to" not in sent
