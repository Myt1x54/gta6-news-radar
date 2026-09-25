export type Category =
  | "official"
  | "leak"
  | "rumor"
  | "trailer_media"
  | "price_date"
  | "gameplay_detail"
  | "community_drama"
  | "other";

export type Status = "new" | "shortlisted" | "pitched" | "used" | "rejected";

export type VideoFormat =
  | "news_breakdown"
  | "reaction"
  | "theory"
  | "everything_we_know"
  | "comparison"
  | "short";

export const STATUSES: Status[] = [
  "new",
  "shortlisted",
  "pitched",
  "used",
  "rejected",
];

export const CATEGORIES: Category[] = [
  "official",
  "leak",
  "rumor",
  "trailer_media",
  "price_date",
  "gameplay_detail",
  "community_drama",
  "other",
];

export interface Story {
  id: string;
  headline: string;
  summary: string | null;
  category: Category | null;
  credibility: number | null;
  credibility_reason: string | null;
  video_score: number | null;
  video_score_reason: string | null;
  rank_score: number;
  source_count: number;
  first_seen_at: string;
  last_updated_at: string;
  status: Status;
  notes: string | null;
  ai_model_used: string | null;
}

export interface VideoIdea {
  id: number;
  story_id: string;
  title: string;
  hook: string | null;
  format: VideoFormat | null;
  angle: string | null;
  generated_on_demand: boolean;
}

export interface YouTubeTrend {
  id: number;
  video_id: string;
  channel: string | null;
  title: string | null;
  views: number | null;
  view_velocity: number | null;
  topic_keywords: string[] | null;
  captured_at: string;
}

export interface Article {
  id: number;
  url: string;
  title: string | null;
  snippet: string | null;
  published_at: string | null;
  source_id: number | null;
  reddit_score: number | null;
  reddit_comments: number | null;
}
