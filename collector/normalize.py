"""URL normalization, hashing, and GTA 6 relevance filtering.

Pure functions with no network / DB access, so they're easy to unit-test.
"""

from __future__ import annotations

import hashlib
import re
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from config import (
    GTA6_INCLUDE_KEYWORDS,
    GTA6_EXCLUDE_KEYWORDS,
    TRACKING_PARAMS,
)

_TRACKING = {p.lower() for p in TRACKING_PARAMS}


def _build_keyword_regex(keywords: list[str]) -> re.Pattern[str]:
    """Turn the config keyword list into a word-boundary regex.

    Spaces in a keyword become ``\\s*`` so "gta 6", "gta  6" and "gta6" all
    match, while boundaries stop "gta vi" from matching inside "gta vice".
    """
    parts = [re.escape(k.strip()).replace(r"\ ", r"\s*") for k in keywords if k.strip()]
    return re.compile(r"\b(?:" + "|".join(parts) + r")\b", re.IGNORECASE)


_INCLUDE_RE = _build_keyword_regex(GTA6_INCLUDE_KEYWORDS)
_EXCLUDE_RE = _build_keyword_regex(GTA6_EXCLUDE_KEYWORDS)


def normalize_url(url: str) -> str:
    """Canonicalize a URL for dedupe: lowercase host, drop tracking params and
    fragments, sort remaining query keys, strip a trailing slash."""
    if not url:
        return ""
    parts = urlsplit(url.strip())
    scheme = (parts.scheme or "https").lower()
    netloc = parts.netloc.lower()
    query = sorted(
        (k, v)
        for k, v in parse_qsl(parts.query, keep_blank_values=True)
        if k.lower() not in _TRACKING
    )
    path = parts.path.rstrip("/") or "/"
    return urlunsplit((scheme, netloc, path, urlencode(query), ""))


def url_hash(url: str) -> str:
    """Stable hash of the normalized URL (used as the dedupe key)."""
    return hashlib.sha256(normalize_url(url).encode("utf-8")).hexdigest()


def is_gta6_relevant(*texts: str | None) -> bool:
    """Cheap first-pass filter. True if any text mentions GTA 6 by a
    boundary-safe keyword. (The AI does the smarter second pass in Phase 3.)"""
    blob = " ".join(t for t in texts if t)
    return bool(_INCLUDE_RE.search(blob))


def is_probably_old_gta(*texts: str | None) -> bool:
    """True if the text looks like GTA 5 / Online / older-title news AND does
    not also mention GTA 6. Used to demote likely-irrelevant items."""
    blob = " ".join(t for t in texts if t)
    return bool(_EXCLUDE_RE.search(blob)) and not bool(_INCLUDE_RE.search(blob))
