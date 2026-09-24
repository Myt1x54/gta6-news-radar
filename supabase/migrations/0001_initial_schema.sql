-- ============================================================================
-- GTA 6 News Radar - initial schema
-- Migration 0001
--
-- Run via the Supabase SQL editor or the Supabase CLI:
--   supabase db push
--
-- Design notes:
--   * The collector connects with the SERVICE ROLE key, which bypasses RLS.
--   * The Next.js dashboard connects as an authenticated user; RLS below
--     restricts all app tables to authenticated users only (1-2 private users).
--   * Public sign-ups are disabled in the Supabase Auth dashboard, not here.
-- ============================================================================

-- Needed for gen_random_uuid()
create extension if not exists "pgcrypto";

-- ---------------------------------------------------------------------------
-- sources : mirror of sources.yaml + health tracking
-- ---------------------------------------------------------------------------
create table if not exists sources (
    id            bigint generated always as identity primary key,
    name          text not null unique,
    url           text not null,
    type          text not null check (type in ('rss','reddit','google_news','youtube_rss','html')),
    credibility   real not null default 0.5 check (credibility >= 0 and credibility <= 1),
    enabled       boolean not null default true,
    last_success  timestamptz,
    last_error    text,
    created_at    timestamptz not null default now()
);

-- ---------------------------------------------------------------------------
-- stories : deduped/clustered events, AI-enriched + ranked
-- ---------------------------------------------------------------------------
create table if not exists stories (
    id                    uuid primary key default gen_random_uuid(),
    headline              text not null,
    summary               text,
    category              text check (category in (
                              'official','leak','rumor','trailer_media',
                              'price_date','gameplay_detail','community_drama','other')),
    credibility           real check (credibility >= 0 and credibility <= 1),
    credibility_reason    text,
    video_score           int check (video_score >= 0 and video_score <= 10),
    video_score_reason    text,
    rank_score            real not null default 0,
    source_count          int not null default 1,
    first_seen_at         timestamptz not null default now(),
    last_updated_at       timestamptz not null default now(),
    status                text not null default 'new' check (status in (
                              'new','shortlisted','pitched','used','rejected')),
    notes                 text,
    alerted_at            timestamptz,           -- set when a breaking alert was sent
    ai_model_used         text
);

create index if not exists stories_rank_idx on stories (rank_score desc);
create index if not exists stories_first_seen_idx on stories (first_seen_at desc);
create index if not exists stories_status_idx on stories (status);
create index if not exists stories_category_idx on stories (category);

-- ---------------------------------------------------------------------------
-- articles : raw items from sources (many articles -> one story)
-- ---------------------------------------------------------------------------
create table if not exists articles (
    id                bigint generated always as identity primary key,
    source_id         bigint references sources(id) on delete set null,
    url               text not null unique,
    url_hash          text not null,             -- hash of normalized URL
    title             text,
    snippet           text,
    published_at      timestamptz,
    fetched_at        timestamptz not null default now(),
    reddit_score      int,                       -- upvotes (reddit only)
    reddit_comments   int,                       -- comment count (reddit only)
    story_id          uuid references stories(id) on delete set null
);

create index if not exists articles_url_hash_idx on articles (url_hash);
create index if not exists articles_story_idx on articles (story_id);
create index if not exists articles_fetched_idx on articles (fetched_at desc);

-- ---------------------------------------------------------------------------
-- video_ideas : AI-generated ideas per story
-- ---------------------------------------------------------------------------
create table if not exists video_ideas (
    id                    bigint generated always as identity primary key,
    story_id              uuid not null references stories(id) on delete cascade,
    title                 text not null,
    hook                  text,
    format                text check (format in (
                              'news_breakdown','reaction','theory',
                              'everything_we_know','comparison','short')),
    angle                 text,
    created_at            timestamptz not null default now(),
    generated_on_demand   boolean not null default false
);

create index if not exists video_ideas_story_idx on video_ideas (story_id);

-- ---------------------------------------------------------------------------
-- youtube_trends : trending GTA 6 videos + velocity
-- ---------------------------------------------------------------------------
create table if not exists youtube_trends (
    id              bigint generated always as identity primary key,
    video_id        text not null,
    channel         text,
    title           text,
    published_at    timestamptz,
    views           bigint,
    view_velocity   real,                        -- views per hour since upload
    topic_keywords  text[],
    captured_at     timestamptz not null default now()
);

create index if not exists youtube_trends_captured_idx on youtube_trends (captured_at desc);
create index if not exists youtube_trends_velocity_idx on youtube_trends (view_velocity desc);

-- ---------------------------------------------------------------------------
-- runs : one row per collector/job execution (observability)
-- ---------------------------------------------------------------------------
create table if not exists runs (
    id              bigint generated always as identity primary key,
    job             text not null,               -- 'collect' | 'youtube' | 'digest'
    started_at      timestamptz not null default now(),
    finished_at     timestamptz,
    new_articles    int default 0,
    new_stories     int default 0,
    ai_calls        int default 0,
    errors          jsonb
);

create index if not exists runs_job_started_idx on runs (job, started_at desc);

-- ---------------------------------------------------------------------------
-- settings : single-row app configuration
-- ---------------------------------------------------------------------------
create table if not exists settings (
    id                  int primary key default 1 check (id = 1),
    alert_threshold     real not null default 75,
    email_enabled       boolean not null default true,
    quiet_hours_start   int not null default 1,   -- PKT hour
    quiet_hours_end     int not null default 8,   -- PKT hour
    weights             jsonb not null default '{
        "video_score": 0.35,
        "credibility": 0.15,
        "source_count": 0.15,
        "reddit_engagement": 0.10,
        "youtube_trend": 0.10,
        "freshness": 0.15
    }'::jsonb,
    updated_at          timestamptz not null default now()
);

-- Seed the single settings row.
insert into settings (id) values (1) on conflict (id) do nothing;

-- ============================================================================
-- Row Level Security
-- Only authenticated users may read/write app tables. The collector uses the
-- service role key, which bypasses RLS entirely.
-- ============================================================================
alter table sources         enable row level security;
alter table articles        enable row level security;
alter table stories         enable row level security;
alter table video_ideas     enable row level security;
alter table youtube_trends  enable row level security;
alter table runs            enable row level security;
alter table settings        enable row level security;

-- Helper: create an "authenticated can do everything" policy per table.
do $$
declare
    t text;
begin
    foreach t in array array[
        'sources','articles','stories','video_ideas',
        'youtube_trends','runs','settings'
    ]
    loop
        execute format(
            'create policy %I on %I for all to authenticated using (true) with check (true);',
            t || '_authenticated_all', t
        );
    end loop;
end $$;
