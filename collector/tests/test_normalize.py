from normalize import (
    is_gta6_relevant,
    is_probably_old_gta,
    normalize_url,
    url_hash,
)


def test_normalize_strips_tracking_and_fragment():
    url = "https://Example.com/News/GTA6/?utm_source=tw&id=5#top"
    assert normalize_url(url) == "https://example.com/News/GTA6?id=5"


def test_normalize_sorts_query_and_trailing_slash():
    # query order is canonicalized (sorted)
    assert normalize_url("https://x.com/a?b=2&a=1") == normalize_url("https://x.com/a?a=1&b=2")
    # trailing slash on the path is removed
    assert normalize_url("https://x.com/a/") == "https://x.com/a"


def test_url_hash_equal_for_equivalent_urls():
    h1 = url_hash("https://x.com/p?utm_campaign=z&k=1")
    h2 = url_hash("https://x.com/p?k=1")
    assert h1 == h2
    assert len(h1) == 64


def test_relevance_matches_variants():
    assert is_gta6_relevant("GTA 6 trailer is here")
    assert is_gta6_relevant("New details on Grand Theft Auto VI")
    assert is_gta6_relevant(None, "leaked gta6 map")


def test_relevance_rejects_unrelated_and_boundary_false_positives():
    assert not is_gta6_relevant("Best GTA San Andreas mods")
    # "gta vi" must NOT match inside "gta vice city"
    assert not is_gta6_relevant("Revisiting GTA Vice City today")
    assert not is_gta6_relevant("Random RPG news")


def test_probably_old_gta():
    assert is_probably_old_gta("GTA Online weekly update")
    # mentions both -> treated as GTA 6, not old
    assert not is_probably_old_gta("GTA 6 vs GTA Online comparison")
