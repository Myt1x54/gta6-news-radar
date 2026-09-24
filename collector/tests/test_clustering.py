from datetime import datetime, timedelta, timezone

from clustering import (
    assign_clusters,
    normalize_title,
    same_event,
    significant_tokens,
    title_similarity,
)

BASE = datetime(2026, 9, 24, 12, 0, tzinfo=timezone.utc)


def _art(id, title, hours=0):
    return {"id": id, "title": title, "published_at": BASE + timedelta(hours=hours)}


def test_normalize_title_strips_publisher_suffix():
    assert normalize_title("GTA 6 Collector's Edition Revealed - IGN") == "gta 6 collectors edition revealed"
    assert normalize_title("Big News | PC Gamer") == "big news"


def test_similar_titles_score_high():
    s = title_similarity(
        "GTA 6 $400 Collector's Edition revealed by Rockstar",
        "Rockstar reveals GTA 6 collectors edition for $400",
    )
    assert s >= 85


def test_near_duplicates_cluster_together():
    arts = [
        _art(1, "GTA 6 $400 Collector's Edition revealed by Rockstar"),
        _art(2, "Rockstar reveals the GTA 6 Collector's Edition for $400", hours=2),
        _art(3, "Zelda remake announced at Nintendo Direct", hours=1),
    ]
    res = assign_clusters(arts)
    key = {r["article"]["id"]: r["cluster_key"] for r in res}
    assert key[1] == key[2]      # duplicates share a cluster
    assert key[3] != key[1]      # unrelated is its own cluster
    # all are new clusters (no existing stories)
    assert all(r["story_id"] is None for r in res)


def test_article_attaches_to_existing_story():
    existing = [{"story_id": "abc", "title": "GTA 6 Collector's Edition costs $400", "anchor_time": BASE}]
    arts = [_art(9, "Rockstar's GTA 6 collectors edition is $400", hours=3)]
    res = assign_clusters(arts, existing)
    assert res[0]["story_id"] == "abc"
    assert res[0]["cluster_key"] == ("existing", "abc")


def test_significant_tokens_drop_generic_words():
    # "gta", "6", "rockstar", "reveals" are generic/stopwords and dropped
    assert significant_tokens("Rockstar Reveals GTA 6 Collector's Box") == {"collectors", "box"}


def test_same_event_matches_paraphrases():
    assert same_event(
        "Rockstar Reveals $400 GTA 6 Collector's Box That Doesn't Include The Game",
        "GTA 6 Collector's Box Is $400, Doesn't Include the Game",
    )


def test_same_event_rejects_shared_generic_only():
    # both mention GTA 6 but are unrelated events -> must NOT merge
    assert not same_event(
        "GTA 6 Will Make Pro Athletes Perform Worse, NBA Star Says",
        "Rockstar Reveals $400 GTA 6 Collector's Box",
    )
    assert not same_event(
        "GTA 6 soundtrack album announced with Travis Scott",
        "GTA 6 map leak surfaces online",
    )


def test_unrelated_gta6_titles_stay_separate():
    arts = [
        _art(1, "Rockstar Reveals $400 GTA 6 Collector's Box"),
        _art(2, "GTA 6 soundtrack album announced with Travis Scott", hours=1),
        _art(3, "Rainbow Six Siege director braces for GTA 6 launch", hours=2),
    ]
    res = assign_clusters(arts)
    keys = {r["article"]["id"]: r["cluster_key"] for r in res}
    assert len({keys[1], keys[2], keys[3]}) == 3  # three distinct clusters


def test_same_title_outside_window_does_not_cluster():
    arts = [
        _art(1, "GTA 6 map leak surfaces online"),
        _art(2, "GTA 6 map leak surfaces online", hours=72),  # 3 days later
    ]
    res = assign_clusters(arts)
    assert res[0]["cluster_key"] != res[1]["cluster_key"]
