from datetime import datetime, timedelta, timezone

from ranking import compute_rank_score, freshness_factor

NOW = datetime(2026, 9, 24, 12, 0, tzinfo=timezone.utc)


def test_freshness_halflife():
    assert freshness_factor(0) == 1.0
    assert abs(freshness_factor(12, 12) - 0.5) < 1e-9
    assert abs(freshness_factor(24, 12) - 0.25) < 1e-9


def test_perfect_fresh_story_scores_high():
    story = {
        "video_score": 10,
        "credibility": 1.0,
        "source_count": 6,
        "reddit_score": 4000,
        "reddit_comments": 1000,
        "youtube_trend_match": 1.0,
        "first_seen_at": NOW,
    }
    assert compute_rank_score(story, now=NOW) == 100.0


def test_empty_story_scores_freshness_plus_one_source():
    # brand new, no AI signals: freshness (0.15*100=15) + the implicit
    # source_count of 1 (1/6 * 0.15 * 100 = 2.5) -> 17.5
    story = {"first_seen_at": NOW}
    score = compute_rank_score(story, now=NOW)
    assert abs(score - 17.5) < 0.01


def test_older_story_decays():
    story = {"video_score": 10, "credibility": 1.0, "first_seen_at": NOW - timedelta(hours=24)}
    fresh = compute_rank_score({**story, "first_seen_at": NOW}, now=NOW)
    old = compute_rank_score(story, now=NOW)
    assert old < fresh


def test_caps_prevent_overflow():
    story = {
        "video_score": 10,
        "credibility": 1.0,
        "source_count": 99,       # way above cap
        "reddit_score": 999999,   # way above cap
        "reddit_comments": 999999,
        "youtube_trend_match": 5,  # above 1
        "first_seen_at": NOW,
    }
    assert compute_rank_score(story, now=NOW) == 100.0
