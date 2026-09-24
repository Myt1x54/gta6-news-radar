"""Load and validate the source list from sources.yaml."""

from __future__ import annotations

from typing import Any

import yaml

from config import SOURCES_FILE

VALID_TYPES = {"rss", "reddit", "google_news", "youtube_rss", "html"}


def load_sources(path=SOURCES_FILE) -> list[dict[str, Any]]:
    """Return the list of source dicts from the YAML file, validated."""
    with open(path, "r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    sources = data.get("sources", [])
    for s in sources:
        _validate(s)
    return sources


def enabled_sources(path=SOURCES_FILE) -> list[dict[str, Any]]:
    return [s for s in load_sources(path) if s.get("enabled", False)]


def _validate(s: dict[str, Any]) -> None:
    for field in ("name", "url", "type"):
        if not s.get(field):
            raise ValueError(f"source missing required field '{field}': {s!r}")
    if s["type"] not in VALID_TYPES:
        raise ValueError(f"source '{s['name']}' has invalid type '{s['type']}'")
    cred = s.get("credibility", 0.5)
    if not (0.0 <= float(cred) <= 1.0):
        raise ValueError(f"source '{s['name']}' credibility must be 0-1")
