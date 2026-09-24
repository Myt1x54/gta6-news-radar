"""Orchestrate AI enrichment: Gemini primary, Groq fallback, JSON-validated.

Flow (PROJECT_BRIEF §6.2):
  build prompt -> try Gemini (retry once on bad JSON) -> on provider error/429
  fall back to Groq (retry once on bad JSON) -> validate with pydantic.
"""

from __future__ import annotations

import json
import re
from typing import Any

from pydantic import ValidationError

from config import GEMINI_API_KEY, GEMINI_MODEL, GROQ_API_KEY, GROQ_MODEL
from ai import providers
from ai.prompt import build_prompt
from ai.schema import EnrichmentBatch, StoryEnrichment

_FENCE_RE = re.compile(r"^\s*```(?:json)?\s*|\s*```\s*$", re.IGNORECASE)


def _strip_fences(text: str) -> str:
    """Remove ```json ... ``` markdown fences if the model added them."""
    return _FENCE_RE.sub("", text.strip())


def parse_enrichment(text: str) -> EnrichmentBatch:
    """Parse+validate the model's raw text into an EnrichmentBatch.

    Raises json.JSONDecodeError or pydantic.ValidationError on bad output.
    """
    data = json.loads(_strip_fences(text))
    return EnrichmentBatch.model_validate(data)


def enrich_stories(
    stories: list[dict[str, Any]],
    *,
    trends: list[str] | None = None,
    used_rejected: list[dict[str, Any]] | None = None,
) -> tuple[dict[str, StoryEnrichment], str, int]:
    """Enrich a batch of stories.

    Returns (results_by_ref, model_used, ai_calls). Raises RuntimeError if all
    providers fail.
    """
    if not stories:
        return {}, "", 0

    system, user = build_prompt(stories, trends=trends, used_rejected=used_rejected)

    providers_to_try: list[tuple[str, str]] = []
    if GEMINI_API_KEY:
        providers_to_try.append(("gemini", GEMINI_MODEL))
    if GROQ_API_KEY:
        providers_to_try.append(("groq", GROQ_MODEL))
    if not providers_to_try:
        raise RuntimeError("No AI provider configured (set GEMINI_API_KEY or GROQ_API_KEY).")

    ai_calls = 0
    last_err: Exception | None = None

    for provider, model in providers_to_try:
        call = providers.call_gemini if provider == "gemini" else providers.call_groq
        for attempt in range(2):  # retry once on invalid JSON from same provider
            try:
                ai_calls += 1
                text = call(system, user, model)
                batch = parse_enrichment(text)
                results = {e.ref: e for e in batch.stories}
                return results, f"{provider}:{model}", ai_calls
            except (json.JSONDecodeError, ValidationError) as exc:
                last_err = exc
                continue  # bad JSON -> retry once
            except Exception as exc:  # network / 429 / auth -> next provider
                last_err = exc
                break

    raise RuntimeError(f"AI enrichment failed on all providers: {last_err}")
