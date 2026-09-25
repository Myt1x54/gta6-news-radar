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

def _env(name: str, default: str = "") -> str:
    """os.getenv but treats an empty/whitespace value as unset. GitHub Actions
    renders a missing secret as "", which would otherwise blank out defaults."""
    val = os.getenv(name)
    return val.strip() if val and val.strip() else default


GEMINI_API_KEY = _env("GEMINI_API_KEY")
GEMINI_MODEL = _env("GEMINI_MODEL", "gemini-3.5-flash-lite")

GROQ_API_KEY = _env("GROQ_API_KEY")
GROQ_MODEL = _env("GROQ_MODEL", "openai/gpt-oss-120b")

SMTP_HOST = _env("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(_env("SMTP_PORT", "587"))
SMTP_USER = _env("SMTP_USER")
SMTP_PASS = _env("SMTP_PASS")
ALERT_TO = _env("ALERT_TO")

YOUTUBE_API_KEY = _env("YOUTUBE_API_KEY")

REDDIT_CLIENT_ID = _env("REDDIT_CLIENT_ID")
REDDIT_CLIENT_SECRET = _env("REDDIT_CLIENT_SECRET")

USER_AGENT = _env(
    "USER_AGENT",
    "GTA6NewsRadar/0.1 (+https://github.com/YOUR_USERNAME/gta6-news-radar)",
)
APP_TIMEZONE = _env("APP_TIMEZONE", "Asia/Karachi")
# Breaking-alert threshold (0-100). 65 chosen because reddit-engagement and
# youtube-trend signals (20% of the score) aren't live yet, so the current
# practical max is ~67; 75 would never fire. Raise toward 75 once those land.
ALERT_THRESHOLD = float(_env("ALERT_THRESHOLD", "65"))

# Base URL of the deployed dashboard, used for links in emails.
DASHBOARD_URL = _env("DASHBOARD_URL", "https://gta6-news-radar.vercel.app").rstrip("/")


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
# Clustering matches on the *significant* tokens of a title (generic words like
# "gta"/"6"/"rockstar" are ignored) so paraphrased coverage of the same event
# merges, without lumping together everything that merely mentions GTA 6.
# Two titles are the same event if they share >= MIN_SHARED significant tokens
# AND (token Jaccard >= MIN_JACCARD OR fuzzy score >= FUZZY_THRESHOLD).
CLUSTER_MIN_SHARED_TOKENS = 2
CLUSTER_MIN_JACCARD = 0.45
CLUSTER_FUZZY_THRESHOLD = 77
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

# AI enrichment throughput (protects Gemini/Groq free quotas).
AI_BATCH_SIZE = 6              # stories per AI call
AI_MAX_STORIES_PER_RUN = 24    # cap enrichment per run; backfill spreads out


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
