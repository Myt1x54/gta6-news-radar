import json

import pytest

from ai import enrich as enrich_mod
from ai.enrich import enrich_stories, parse_enrichment
from ai.prompt import build_prompt
from ai.schema import StoryEnrichment

VALID_JSON = json.dumps(
    {
        "stories": [
            {
                "ref": "s1",
                "is_gta6": True,
                "headline": "GTA 6 Collector's Edition revealed",
                "summary": "Rockstar revealed a $400 collector's set.",
                "category": "price_date",
                "credibility": 0.9,
                "credibility_reason": "official",
                "video_score": 8,
                "video_score_reason": "high interest",
                "video_ideas": [
                    {"title": "The $400 GTA 6 Box", "hook": "Would you pay $400?", "format": "news_breakdown", "angle": "value"}
                ],
            }
        ]
    }
)


def test_parse_valid_json():
    batch = parse_enrichment(VALID_JSON)
    assert len(batch.stories) == 1
    assert batch.stories[0].ref == "s1"
    assert batch.stories[0].video_ideas[0].format == "news_breakdown"


def test_parse_strips_markdown_fences():
    fenced = "```json\n" + VALID_JSON + "\n```"
    batch = parse_enrichment(fenced)
    assert batch.stories[0].headline.startswith("GTA 6")


def test_schema_clamps_out_of_range_values():
    e = StoryEnrichment(
        ref="x", is_gta6=True, headline="h", summary="s",
        category="other", credibility=1.7, credibility_reason="",
        video_score=42, video_score_reason="",
    )
    assert e.credibility == 1.0
    assert e.video_score == 10


def test_build_prompt_includes_ref_trends_and_history():
    system, user = build_prompt(
        [{"ref": "42", "title": "GTA 6 news", "snippet": "x", "sources": ["IGN"], "source_count": 1, "credibility_hint": 0.8}],
        trends=["Vice City map"],
        used_rejected=[{"status": "used", "category": "leak", "headline": "Prev leak"}],
    )
    assert "JSON" in system
    assert '"ref": "42"' in user
    assert "Vice City map" in user
    assert "Prev leak" in user


def test_enrich_falls_back_to_groq(monkeypatch):
    monkeypatch.setattr(enrich_mod, "GEMINI_API_KEY", "x")
    monkeypatch.setattr(enrich_mod, "GROQ_API_KEY", "y")

    def boom(*a, **k):
        raise RuntimeError("429 rate limited")

    monkeypatch.setattr(enrich_mod.providers, "call_gemini", boom)
    monkeypatch.setattr(enrich_mod.providers, "call_groq", lambda *a, **k: VALID_JSON)

    results, model_used, ai_calls = enrich_stories([{"ref": "s1", "title": "t"}])
    assert model_used.startswith("groq")
    assert "s1" in results


def test_enrich_retries_once_on_bad_json(monkeypatch):
    monkeypatch.setattr(enrich_mod, "GEMINI_API_KEY", "x")
    monkeypatch.setattr(enrich_mod, "GROQ_API_KEY", "")

    calls = {"n": 0}

    def flaky(*a, **k):
        calls["n"] += 1
        return "not json" if calls["n"] == 1 else VALID_JSON

    monkeypatch.setattr(enrich_mod.providers, "call_gemini", flaky)
    results, model_used, ai_calls = enrich_stories([{"ref": "s1", "title": "t"}])
    assert model_used.startswith("gemini")
    assert ai_calls == 2  # first bad, retry good
    assert "s1" in results
