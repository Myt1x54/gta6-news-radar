"""Central configuration for the GTA 6 News Radar collector.

Everything tunable lives here or in `sources.yaml`:
  - environment variables (loaded from .env locally, GitHub Secrets in CI)
  - keyword filters for GTA 6 relevance
  - ranking weights and the freshness half-life
  - clustering / dedupe thresholds

Keep this file free of secrets. Only variable *names* and default *tuning*
values belong here.
"""

from __future__ import annotations

import os
from pathlib import Path

try:
    # Optional locally; in CI env vars come from GitHub Secrets directly.
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:  # pragma: no cover
    pass


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
COLLECTOR_DIR = Path(__file__).resolve().parent
SOURCES_FILE = COLLECTOR_DIR / "sources.yaml"


# ---------------------------------------------------------------------------
# Environment variables (values come from .env / GitHub Secrets)
# ---------------------------------------------------------------------------
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")

SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASS = os.getenv("SMTP_PASS", "")
ALERT_TO = os.getenv("ALERT_TO", "")

YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY", "")

USER_AGENT = os.getenv(
    "USER_AGENT",
    "GTA6NewsRadar/0.1 (+https://github.com/YOUR_USERNAME/gta6-news-radar)",
)
APP_TIMEZONE = os.getenv("APP_TIMEZONE", "Asia/Karachi")
ALERT_THRESHOLD = float(os.getenv("ALERT_THRESHOLD", "75"))


# ---------------------------------------------------------------------------
# GTA 6 relevance keyword filter (cheap first pass; AI is the second pass)
# ---------------------------------------------------------------------------
# An item must match at least one INCLUDE term...
GTA6_INCLUDE_KEYWORDS = [
    "gta 6",
    "gta vi",
    "gta6",
    "grand theft auto 6",
    "grand theft auto vi",
]
# ...and must NOT be primarily about these (GTA 5 / Online only news).
GTA6_EXCLUDE_KEYWORDS = [
    "gta 5",
    "gta v ",
    "grand theft auto v ",
    "gta online",
    "gta 4",
    "gta san andreas",
]


# ---------------------------------------------------------------------------
# Clustering / dedupe
# ---------------------------------------------------------------------------
# rapidfuzz title-similarity threshold (0-100) to merge into one story.
TITLE_SIMILARITY_THRESHOLD = 85
# Only cluster articles within this many hours of each other.
CLUSTER_WINDOW_HOURS = 48
# URL query params stripped before dedupe (tracking junk).
TRACKING_PARAMS = [
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "utm_term",
    "utm_content",
    "fbclid",
    "gclid",
    "ref",
    "ref_src",
    "cmpid",
]


# ---------------------------------------------------------------------------
# Ranking weights (must sum to ~1.0). Tune freely.
# Each component is normalized to 0-1 before weighting; final score is x100.
# ---------------------------------------------------------------------------
RANK_WEIGHTS = {
    "video_score": 0.35,      # AI's 0-10 video potential
    "credibility": 0.15,      # source credibility 0-1
    "source_count": 0.15,     # how many outlets cover it
    "reddit_engagement": 0.10,  # upvotes + comments, normalized
    "youtube_trend": 0.10,    # matches a currently trending topic
    "freshness": 0.15,        # decays with age
}

# Freshness decay: score halves every N hours.
FRESHNESS_HALFLIFE_HOURS = 12

# Normalization caps (values at/above these count as 1.0).
SOURCE_COUNT_CAP = 6          # 6+ outlets => full source_count score
REDDIT_ENGAGEMENT_CAP = 5000  # upvotes + comments


# ---------------------------------------------------------------------------
# Housekeeping
# ---------------------------------------------------------------------------
ARTICLE_RETENTION_DAYS = 60   # delete raw articles older than this
RANK_RECOMPUTE_MAX_AGE_HOURS = 48  # re-rank stories younger than this each run


# ---------------------------------------------------------------------------
# YouTube trends quota guardrails
# ---------------------------------------------------------------------------
YOUTUBE_DAILY_QUOTA = 10_000
YOUTUBE_QUOTA_SOFT_CAP = 0.30  # stay under 30% of daily quota
YOUTUBE_LOOKBACK_HOURS = 48    # search videos published in last N hours


# ---------------------------------------------------------------------------
# Email alerting behaviour
# ---------------------------------------------------------------------------
MAX_ALERTS_PER_HOUR = 5        # bundle extras into one email
QUIET_HOURS_START = 1          # 01:00 PKT
QUIET_HOURS_END = 8            # 08:00 PKT
DIGEST_TOP_N = 5               # stories in the daily digest
