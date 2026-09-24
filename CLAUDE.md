# CLAUDE.md — GTA 6 News Radar

> Project memory. Read this first every session. Update it at the end of every
> work session and every phase so the next session can pick up exactly here.

## Project summary

A **private** ($0-budget, 1–2 users) web app that automatically collects GTA 6
news, de-duplicates and clusters it into "stories", uses AI to summarize / score
/ suggest YouTube video ideas, ranks everything on a dashboard, and emails the
user when something big breaks. Built for a part-time GTA 6 news researcher who
feeds a YouTube content creator.

Full original brief: [docs/PROJECT_BRIEF.md](docs/PROJECT_BRIEF.md).

## Hard constraints (do not violate)

- **$0 budget.** Everything on a free tier, no credit card. If something would
  cost money, STOP and tell the user.
- **Public GitHub repo.** NEVER commit secrets. Keys live in GitHub Secrets or a
  local `.env` (gitignored). `.env.example` documents names only.
- **1–2 users.** Keep it simple; don't over-engineer for scale.
- **Backend independent of frontend** (so a future mobile app can reuse Supabase
  DB + Auth). Website is an installable PWA.
- **Prefer RSS/JSON feeds over HTML scraping.** Respect robots.txt, send a clear
  User-Agent, don't hammer sites.
- Ask before adding a paid service, a major dependency, or changing the stack.

## Tech stack

- **Scheduler:** GitHub Actions cron (collect every 10 min; youtube every 2–3 h;
  digest daily 04:00 UTC = 09:00 PKT).
- **Collector:** Python 3.12 — feedparser, httpx, rapidfuzz, trafilatura,
  supabase-py, pydantic, PyYAML.
- **DB + Auth:** Supabase (Postgres + Auth), free tier, 500 MB limit.
- **AI primary:** Google Gemini free tier, Flash/Flash-Lite only (model in
  `GEMINI_MODEL` env var). **AI fallback:** Groq (OpenAI-compatible) on 429/error.
- **Frontend:** Next.js (App Router) + TypeScript + Tailwind on Cloudflare Pages, PWA.
- **On-demand AI:** serverless function (Cloudflare Pages Function or Supabase
  Edge Function) so the AI key never reaches the browser.
- **Email:** Gmail SMTP + App Password, wrapped in a swappable `send_email()`.
- **YouTube trends:** YouTube Data API v3 (10k units/day) + channel RSS feeds.

## Architecture

```
GitHub Actions (10 min)   → collector/run.py           → Supabase
GitHub Actions (2–3 h)    → collector/youtube_trends.py → Supabase
GitHub Actions (daily)    → collector/daily_digest.py   → email
Next.js dashboard (Cloudflare Pages, PWA) ← reads Supabase (RLS, authenticated)
serverless fn "Generate more ideas" ← calls AI server-side
```

Collector pipeline: fetch sources → normalize to `articles` → skip seen URLs →
cluster duplicates into `stories` → AI-enrich NEW stories → compute `rank_score`
→ email alert if score ≥ threshold.

## Repo structure

```
/collector          run.py, youtube_trends.py, daily_digest.py, sources.yaml,
                    config.py, requirements.txt, ai/, email/, tests/
/web                Next.js app (not started yet)
/supabase/migrations  0001_initial_schema.sql
/.github/workflows  collect.yml, youtube.yml, digest.yml (not created yet)
/docs               PROJECT_BRIEF.md
CLAUDE.md  README.md  .env.example  .gitignore
```

## Key commands

> Nothing is runnable end-to-end yet (Phase 1 = setup only).

```bash
# Collector (from repo root, once Python + deps installed)
python -m venv .venv && source .venv/Scripts/activate   # Windows Git Bash
pip install -r collector/requirements.txt
python collector/run.py                 # (Phase 2) run the collector once

# Tests
pytest collector/tests

# Web (once scaffolded in Phase 5)
cd web && npm install && npm run dev

# Supabase migrations — run 0001_initial_schema.sql in the Supabase SQL editor,
# or with the Supabase CLI:  supabase db push
```

## Env vars & secrets (names only — see .env.example)

Collector / CI: `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `SUPABASE_ANON_KEY`,
`GEMINI_API_KEY`, `GEMINI_MODEL`, `GROQ_API_KEY`, `GROQ_MODEL`, `SMTP_HOST`,
`SMTP_PORT`, `SMTP_USER`, `SMTP_PASS`, `ALERT_TO`, `YOUTUBE_API_KEY`,
`USER_AGENT`, `APP_TIMEZONE`, `ALERT_THRESHOLD`.

Frontend (Phase 5, `web/.env.local`): `NEXT_PUBLIC_SUPABASE_URL`,
`NEXT_PUBLIC_SUPABASE_ANON_KEY` (+ the serverless function's own AI key server-side).

The `SUPABASE_SERVICE_ROLE_KEY` is used ONLY by the collector and must never
reach the browser.

## Current Status

**Phase 1 (Setup) — COMPLETE, pending user's manual account setup + review.**

Done:
- Repo initialized (git), directory structure created.
- `CLAUDE.md`, `README.md`, `.env.example`, `.gitignore`.
- `docs/PROJECT_BRIEF.md` (verbatim brief).
- `collector/sources.yaml` (start sources; YouTube channels are placeholders).
- `collector/config.py` (env loading, keyword filters, ranking weights, thresholds).
- `collector/requirements.txt`.
- `supabase/migrations/0001_initial_schema.sql` (all 7 tables + RLS + settings seed).

**Next (before Phase 2):** the USER must do the manual setup steps in the README
(create Supabase project, run migration, create AI/YouTube keys, Gmail App
Password, GitHub repo + Secrets) and hand over the YouTube creator channel list.

**Then Phase 2 (Collector v1):** implement fetching per source type → normalize
→ `articles` → URL dedupe, runnable locally, with tests for feed parsing + dedupe.

## Decisions Log

- **2026-09-24 — Gemini default model = `gemini-3.5-flash-lite`.** The brief's
  era 2.5 models are now access-restricted to prior users, so a fresh API key
  can't use them. 3.5 Flash-Lite is GA, cheapest, and built for high-volume/low
  latency — ideal for batched story enrichment. `gemini-3-flash-preview` is a
  more capable free-tier alternative if quality is lacking. Model is env-driven
  (`GEMINI_MODEL`) so it's a one-line change. (Verified via ai.google.dev docs.)
- **2026-09-24 — Groq default = `llama-3.3-70b-versatile`.** Needs verification
  against current Groq free models before Phase 3 (see Known Issues).
- **2026-09-24 — RLS policy: authenticated users get full access to all tables.**
  Fine for 1–2 trusted private users; the collector bypasses RLS via service role.
- **2026-09-24 — Ranking weights + freshness half-life live in `collector/config.py`
  AND mirrored in the `settings` table** (so the dashboard can eventually tune
  them without a deploy). config.py holds the code defaults for now.

## Known Issues / TODO

- [ ] **User manual setup** not done yet (Supabase, keys, secrets) — see README §Setup.
- [x] **YouTube creator channels added** (2026-09-24): Rockstar Games, GTA Series
      Videos, TGG, GhillieMaster, MrBossFTW, Broughy1322, DarkViperAU. Channel IDs
      resolved from each channel page. **Tez2 skipped** — @Tez2 on YouTube is an
      unrelated channel ("jasmineee"); the GTA leaker Tez2 is on X, not YouTube.
- [ ] **Verify Groq free model name** (`GROQ_MODEL`) before Phase 3.
- [ ] Confirm each RSS feed URL in `sources.yaml` actually resolves (Phase 2).
- [ ] Pin/verify Python dep versions install cleanly on 3.12 (Phase 2).
- [ ] Decide serverless host for "Generate more ideas" (Cloudflare Pages Function
      vs Supabase Edge Function) in Phase 8.
```
