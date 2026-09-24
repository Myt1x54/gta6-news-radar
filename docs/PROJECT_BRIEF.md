# Project Brief: GTA 6 News Radar

> This is the original project brief, kept verbatim for reference. The living
> source of truth for current status is `CLAUDE.md` in the repo root.

---

## 1. Background

I work part-time as a **GTA 6 news and content researcher** for a YouTube content creator. My job is to:

1. Find the latest GTA 6 news.
2. Judge and rank the stories by how good they are for a YouTube video.
3. Suggest video ideas based on them.

I want to automate most of this with a personal web app that:

- collects GTA 6 news from the web automatically every ~10 minutes,
- cleans, de-duplicates, and groups it,
- uses AI to summarize, score, and suggest video ideas,
- shows everything on a ranked dashboard,
- emails me when something big breaks.

---

## 2. Hard Constraints

- **Budget is $0.** Every service must be on a free tier. No credit card required anywhere. If something would cost money, stop and tell me.
- **1–2 users only.** This is a private tool, not a public product. Keep it simple. Don't over-engineer for scale.
- **A mobile app may come later.** Keep the backend (database + auth) independent from the website so a future mobile app can reuse it. Make the website an installable **PWA** for now.
- **Code will live in a public GitHub repo.** This gets us unlimited free GitHub Actions minutes. **Never commit secrets.** All keys go in GitHub Secrets or local `.env` files, which must be in `.gitignore`. Provide a `.env.example` file.
- **Prefer RSS/JSON feeds over HTML scraping.** Only scrape HTML when there is no feed. Respect robots.txt, send a clear User-Agent, and don't hammer sites.

---

## 3. Tech Stack (decided)

| Part | Choice |
|---|---|
| Scheduler | **GitHub Actions** cron (`*/10 * * * *`). Scheduled runs can be delayed a few minutes, which is fine. |
| Collector / processor | **Python 3.12**: `feedparser`, `httpx`, `rapidfuzz` (dedupe), `trafilatura` (article text, only if needed), `supabase-py` |
| Database + auth | **Supabase** (free tier): Postgres + Supabase Auth |
| AI (primary) | **Google Gemini** free tier, **Flash / Flash-Lite models only** (Pro is not free). Put the model name in an env var. Check the current model names in Google's docs; don't hardcode old ones. |
| AI (fallback) | **Groq** free tier (OpenAI-compatible API). Use it when Gemini returns 429 or errors. |
| Frontend | **Next.js (App Router) + TypeScript + Tailwind**, deployed on **Cloudflare Pages** |
| On-demand AI endpoint | A small serverless function (Cloudflare Pages Function or Supabase Edge Function) for the "Generate more ideas" button, so the AI key never reaches the browser |
| Email | **Gmail SMTP with an App Password** (free). Wrap it in a small `send_email()` module so the provider can be swapped (e.g. for Resend) later. |
| YouTube trends | **YouTube Data API v3** (free quota: 10,000 units/day) + free YouTube channel RSS feeds |

If you believe a choice here is wrong or no longer free, **tell me before changing it**.

---

## 4. Architecture

```
GitHub Actions (every 10 min)                    GitHub Actions (every 2–3 h)
  └─ collector/run.py                              └─ collector/youtube_trends.py
       1. Fetch all sources                             - search GTA 6 videos (last 48h)
       2. Normalize → articles table                    - compute view velocity
       3. Skip URLs already seen                        - store in youtube_trends table
       4. Cluster duplicates into "stories"
       5. AI-enrich NEW stories only       GitHub Actions (daily, 9:00 PKT = 04:00 UTC)
       6. Compute rank score                 └─ collector/daily_digest.py → email top 5
       7. Email alert if score ≥ threshold
                 │
                 ▼
            Supabase (Postgres + Auth)
                 ▲
                 │
   Next.js dashboard (Cloudflare Pages, PWA)
   + serverless function for "Generate more ideas"
```

---

## 5. News Sources (start list; keep it configurable in one file)

- Rockstar Newswire
- IGN, GameSpot, Eurogamer, VGC (Video Games Chronicle), Kotaku, PC Gamer, GamesRadar: their RSS feeds, filtered to GTA 6 items
- Google News RSS search: `GTA 6`, `GTA VI`, `Grand Theft Auto VI`
- Reddit: `r/GTA6`, `r/GTA` (use `.json` or `.rss` on `/new` and `/hot`; capture upvotes and comment counts)
- YouTube channel RSS feeds of selected GTA creators (I'll give you the list; make it easy to edit)

Put sources in `collector/sources.yaml` with fields: `name`, `url`, `type` (rss/reddit/google_news/youtube_rss/html), `credibility` (0–1), `enabled`.

Filter out items that aren't about GTA 6 (e.g. GTA 5 / GTA Online-only news) with keyword rules first and the AI second.

---

## 6. Processing Pipeline Details

### 6.1 De-duplication and clustering
- Exact dedupe on normalized URL (strip tracking params).
- Group articles about the same event into one **story** (cluster). Start with title similarity (rapidfuzz, ~85 threshold) within a 48h window. If that's not good enough, use the AI as a tie-breaker for borderline pairs.
- A story stores: `source_count`, the first-seen time, and the best/most credible source.

### 6.2 AI enrichment (new stories only)
- Batch several stories into one AI call when possible, to save quota.
- Force **JSON output** and validate it (pydantic). Retry once on invalid JSON.
- Output per story: is_gta6, headline, summary, category, credibility, credibility_reason, video_score (0-10), video_score_reason, and 2-3 video_ideas (title, hook, format, angle).
- The prompt should include recent YouTube trend data and my recent Used/Rejected history as context, so the ideas reflect what's actually working.

### 6.3 Ranking
Final `rank_score` (0–100) should be a weighted mix of: AI video_score, source credibility, source_count, Reddit engagement (normalized), YouTube trend match, and a freshness decay (half-life ~12h). Put all the weights in one config file. Recompute the score for stories younger than 48h on every run.

### 6.4 Housekeeping
- Delete raw article rows older than 60 days and keep only stories.
- Log each run (sources OK/failed, new articles, AI calls used) to a `runs` table.

---

## 7. YouTube Trend Check

- Every 2–3 hours: search for GTA 6 videos published in the last 48h, fetch stats.
- Compute view velocity (views/hour) and extract trending topics/keywords.
- Store in `youtube_trends`. Show a "Trending on YouTube" panel on the dashboard.
- Watch quota: `search.list` = 100 units, `videos.list` = 1 unit, of 10,000/day. Stay under ~30%. Log units used.
- Also read the free RSS feeds of creator channels I list.

---

## 8. Frontend (Next.js dashboard)

- **Feed (home):** ranked story cards with filters + sort; expand for video ideas.
- **Story detail:** all source articles, AI output, video ideas, "Generate more ideas" button, notes field.
- **Trending:** YouTube trends panel + competitor uploads.
- **Digest:** today's top 5.
- **Settings:** alert threshold, email on/off, quiet hours (PKT), ranking weights.
- **Auth:** Supabase Auth email+password, public sign-ups disabled, RLS on all tables.
- **Workflow status:** story status `new → shortlisted → pitched → used | rejected`; last ~30 used/rejected fed to AI prompt.
- **PWA:** manifest + icons, mobile-friendly, no offline mode needed.

---

## 9. Email Notifications

- **Breaking alert:** email when a new story's rank_score ≥ threshold (default 75). Never alert twice. Max 5/hour (bundle extras). Respect quiet hours (default 01:00–08:00 PKT).
- **Daily digest:** top 5 stories from last 24h + best video idea + top trending YouTube topics.
- Clean mobile-friendly HTML. Gmail SMTP via App Password. Secrets: SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS, ALERT_TO.

---

## 10. Database
Tables: `sources`, `articles`, `stories`, `video_ideas`, `youtube_trends`, `runs`, `settings`. SQL migrations in `supabase/migrations/`.

---

## 11. Repo Structure
`/collector` (Python), `/web` (Next.js), `/supabase/migrations`, `/.github/workflows`, `CLAUDE.md`, `README.md`, `.env.example`.

---

## 12. Build Order (phases)
1. Setup 2. Collector v1 3. Clustering + AI enrichment 4. GitHub Actions 5. Dashboard v1 6. Email 7. YouTube trends 8. Polish. Finish and test each phase before the next; check in at the end of each.

---

## 13. Working Rules for Claude Code
1. Create `CLAUDE.md` first (project memory: summary, constraints, stack, commands, env var names, Current Status, Decisions Log, Known Issues/TODO).
2. Update `CLAUDE.md` at the end of every session and phase.
3. Keep this brief as `docs/PROJECT_BRIEF.md`.
4. Ask before adding a paid service, major dependency, or stack change.
5. Keep code simple and readable.
6. Add basic tests for: feed parsing, dedupe/clustering, AI JSON validation, ranking math.
7. When a phase needs manual steps, give exact numbered steps.
