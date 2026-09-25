from emailer.templates import render_alert_email, render_digest_email

STORY = {
    "id": "abc-123",
    "headline": "GTA 6 $400 Collector's Set revealed",
    "summary": "Rockstar revealed a pricey set.",
    "category": "price_date",
    "video_score": 9,
    "rank_score": 82.4,
    "source_count": 3,
}


def test_alert_single_story():
    subject, html = render_alert_email([STORY])
    assert "Breaking" in subject
    assert "GTA 6 $400 Collector's Set revealed" in subject
    assert "/story/abc-123" in html
    assert "Rockstar revealed" in html
    assert "82" in html  # rounded rank


def test_alert_multiple_bundled():
    subject, html = render_alert_email([STORY, {**STORY, "id": "d2"}])
    assert "2 breaking" in subject
    assert "/story/abc-123" in html
    assert "/story/d2" in html


def test_alert_escapes_html():
    s = {**STORY, "headline": "GTA 6 <script>alert(1)</script> leak"}
    _, html = render_alert_email([s])
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;" in html


def test_digest_with_idea_and_trends():
    ideas = {"abc-123": {"title": "The $400 Box", "hook": "Would you pay?"}}
    subject, html = render_digest_email([STORY], ideas, ["Vice City map", "Trailer 2"])
    assert "digest" in subject.lower()
    assert "The $400 Box" in html
    assert "Vice City map" in html


def test_digest_empty():
    subject, html = render_digest_email([], {}, [])
    assert "digest" in subject.lower()
    assert "No notable" in html
