"""Pydantic models for validating the AI's JSON output (PROJECT_BRIEF §6.2)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator

Category = Literal[
    "official",
    "leak",
    "rumor",
    "trailer_media",
    "price_date",
    "gameplay_detail",
    "community_drama",
    "other",
]

VideoFormat = Literal[
    "news_breakdown",
    "reaction",
    "theory",
    "everything_we_know",
    "comparison",
    "short",
]


class VideoIdea(BaseModel):
    title: str
    hook: str
    format: VideoFormat
    angle: str


class StoryEnrichment(BaseModel):
    """One story's AI enrichment. ``ref`` ties it back to the input story."""

    ref: str
    is_gta6: bool
    headline: str
    summary: str
    category: Category = "other"
    credibility: float = Field(ge=0.0, le=1.0)
    credibility_reason: str = ""
    video_score: int = Field(ge=0, le=10)
    video_score_reason: str = ""
    video_ideas: list[VideoIdea] = Field(default_factory=list)

    @field_validator("credibility", mode="before")
    @classmethod
    def _clamp_credibility(cls, v):
        try:
            return max(0.0, min(1.0, float(v)))
        except (TypeError, ValueError):
            return 0.0

    @field_validator("video_score", mode="before")
    @classmethod
    def _clamp_score(cls, v):
        try:
            return max(0, min(10, int(round(float(v)))))
        except (TypeError, ValueError):
            return 0


class EnrichmentBatch(BaseModel):
    """Top-level shape we ask the model to return: {"stories": [ ... ]}."""

    stories: list[StoryEnrichment] = Field(default_factory=list)
