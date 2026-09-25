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

**Phase 1 (Setup) — COMPLETE.** **Phase 2 (Collector v1) — COMPLETE & VERIFIED
LIVE.** On 2026-09-24 a live run inserted **318 articles** into Supabase, synced
20 sources, and logged the run. Supabase project ref: `zudiuiezmcqxwsdnsbpb`.
User's `.env` has SUPABASE_URL + service_role + anon keys. `supabase` pip pkg
installed locally.

Phase 2 done:
- `collector/normalize.py` — URL normalization, url_hash, GTA6 keyword filter
  (boundary-safe regex; "gta vi" won't match "gta vice city").
- `collector/fetchers.py` — `parse_feed` (rss/google_news/youtube_rss),
  `parse_reddit`, `fetch_source` (reddit supports both .rss and .json).
- `collector/sources.py` — load/validate sources.yaml.
- `collector/db.py` — Supabase service-role client, sync_sources, dedupe by
  url_hash, insert_articles (upsert), runs logging, source health.
- `collector/run.py` — orchestrator: fetch → relevance filter → normalize →
  dedupe (in-run + vs DB) → insert. Flags: `--dry-run`, `--limit N`. Reddit
  politeness delay + 429 retry.
- Tests (15, all passing): normalize/relevance, feed+reddit parsing, build_rows
  filtering/dedupe.
- **Dry-run result:** ~389 GTA6 candidates from 20 enabled sources.

**Phase 3 (Clustering + AI enrichment + ranking) — COMPLETE & VERIFIED LIVE**
(2026-09-25). Live run: 318 articles → 293 stories, 24 enriched via
`gemini:gemini-3.5-flash-lite`, 45 video ideas, ranked (top 62.3). New modules:
- `collector/clustering.py` — rapidfuzz title clustering (assign_clusters).
- `collector/ranking.py` — weighted rank_score + freshness half-life.
- `collector/ai/` — schema.py (pydantic), prompt.py, providers.py (gemini/groq
  lazy), enrich.py (fallback + retry-once + JSON validation).
- `collector/processing.py` — DB stages: cluster_and_store, enrich_new_stories,
  rerank_recent.
- `run.py` extended: after insert → cluster → enrich (cap 24/run) → rerank.
  New flag `--no-ai`. Reddit OAuth wired (uses token if creds present, else .rss).
- 31 tests total, all passing.

**Phase 4 (GitHub Actions cron) — COMPLETE & VERIFIED LIVE** (2026-09-25). User
pushed to a public GitHub repo, added the 4 required secrets, and the `collect`
workflow ran GREEN via manual dispatch (now on the */10 schedule).
`.github/workflows/collect.yml`
(*/10 cron + workflow_dispatch, concurrency guard, 8-min timeout, pip cache,
Python 3.12). `run.py` now returns exit 0 on flaky-source errors (only hard
errors fail CI). `config.py` `_env()` treats empty secrets as unset so only the
4 required secrets are mandatory (SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY,
GEMINI_API_KEY, GROQ_API_KEY). README Step 7 has exact secret list + how to test
via the Actions "Run workflow" button.

**Phase 5 (Dashboard) — COMPLETE & DEPLOYED LIVE ON VERCEL** (2026-09-25) at
gta6-news-radar.vercel.app (repo Myt1x54/gta6-news-radar). Login, ranked feed,
story detail all working with real data. Gotcha hit + fixed: NEXT_PUBLIC_* env
vars must be set in Vercel BEFORE build (they're inlined at build time); missing
them → 500 "URL and Key are required". Env vars now set + redeployed.
`web/` = Next.js 16 (App Router) + React 19 + Tailwind 4 + TypeScript. Uses
`@supabase/ssr` (browser client `lib/supabase/client.ts`, server client
`lib/supabase/server.ts`, `proxy.ts` for session refresh + route gating —
Next 16 renamed middleware→proxy). Pages: `/login` (email+password), `/` (ranked
feed with sort/category/status/score/time filters + expandable video ideas +
inline status buttons), `/story/[id]` (AI output, video ideas, sources w/ links,
notes editor, status). Uses the public ANON key only (RLS enforces). `npm run
build` passes; login page + auth gating verified live via preview. `.claude/
launch.json` has a `web` dev-server config (port 3000). web/.env.local holds
NEXT_PUBLIC_SUPABASE_URL + ANON key (gitignored). Auth user exists:
abdulmoiz56898@gmail.com.

**Next — Phase 6 (Email):** breaking alerts (rank_score >= threshold, dedupe via
alerted_at, max 5/hr bundled, quiet hours) + daily digest (top 5 + best idea +
trends). Gmail SMTP via App Password in `collector/emailer/`. Needs user to make
a Gmail App Password (README Step 5) + add SMTP_* GitHub Secrets. New workflow
digest.yml (daily 04:00 UTC); alerts fire from the collect run.

**To run the collector live:** `python collector/run.py` (add `--no-ai` to skip
enrichment). AI backfill spreads 24 stories/run until all are enriched.
`python collector/recluster.py` rebuilds all stories after clustering changes.

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
- **2026-09-24 — `collector/email/` renamed to `collector/emailer/`** (Phase 2).
  Because run.py is run as a script, `collector/` goes on sys.path and a folder
  named `email` shadows Python's stdlib `email`, breaking httpx. Deviates from
  the brief's suggested name for correctness.
- **2026-09-24 — Rockstar Newswire RSS disabled** — no public feed exists
  anymore (all URLs 404). Official news covered via Rockstar's YouTube + Google
  News searches.
- **2026-09-25 — Frontend host: Vercel instead of Cloudflare Pages** (deviates
  from the brief). Why: the dashboard is a server-rendered Next.js App Router app
  (SSR + auth middleware/proxy + cookies). Vercel runs Next.js natively — one
  import from GitHub, zero config, free Hobby tier is plenty for 1–2 users.
  Cloudflare Pages would need an SSR adapter + Edge-runtime tweaks (more setup
  and gotchas). Constraint from user: **keep the app free of Vercel-only
  features** (no Vercel KV/Blob/Edge Config/Cron/Analytics) so relocating stays
  easy — it currently uses none. **If we ever move to Cloudflare, use the
  OpenNext adapter `@opennextjs/cloudflare`, NOT the deprecated
  `@cloudflare/next-on-pages`.**
- **2026-09-24 — Reddit uses `.rss` not `.json`** — `.json` is bot-walled for
  datacenter IPs (403/HTML interstitial). `.rss` works but omits upvote/comment
  counts. Engagement will be added later via free Reddit OAuth (script app).

## Known Issues / TODO

- [ ] **User manual setup** not done yet (Supabase, keys, secrets) — see README §Setup.
- [x] **YouTube creator channels added** (2026-09-24): Rockstar Games, GTA Series
      Videos, TGG, GhillieMaster, MrBossFTW, Broughy1322, DarkViperAU. Channel IDs
      resolved from each channel page. **Tez2 skipped** — @Tez2 on YouTube is an
      unrelated channel ("jasmineee"); the GTA leaker Tez2 is on X, not YouTube.
- [x] **Groq model verified** (2026-09-24 via models API): `llama-3.3-70b-versatile`
      is gone. Available chat models: `openai/gpt-oss-120b` (chosen default),
      `openai/gpt-oss-20b`, `qwen/qwen3.8-27b`. Set in .env + config default.
- [x] Confirmed feed URLs resolve (Phase 2 dry-run). Exceptions below.
- [ ] **Reddit reliability (CONFIRMED problem):** even with a 5s throttle + 429
      retry, the live run got only 1 of 3 Reddit feeds (others 403/429). Reddit
      blocks datacenter IPs hard; GitHub Actions will be worse. **Proper fix =
      Reddit OAuth (free "script" app)** → reliable access + restores upvote/
      comment counts. Recommended as first task of Phase 3. Needs user to create
      the app (REDDIT_CLIENT_ID/SECRET).
- [~] **Clustering improved (Phase 3.1, 2026-09-25):** switched from raw
      token_set_ratio@85 to significant-token matching (strip generic gta/6/
      rockstar words; match ANY cluster member; share>=2 tokens AND (jaccard>=
      0.45 OR fuzzy>=77)). Rebuilt: 341 articles -> 261 stories, main event now
      a 26-article cluster (was ~6 splits). Params in config.py. `recluster.py`
      rebuilds after tuning. RESIDUAL: ~4-5 of top-15 are still the same event
      split by pricing/wording ("$399 swag box" vs "£349.99 premium box") —
      lexical ceiling. Next lever = optional AI tie-breaker for borderline
      pairs (user to decide; adds AI cost/complexity).
- [ ] **Reddit OAuth coded but not yet live-tested** — activates when the user
      adds REDDIT_CLIENT_ID/SECRET. Falls back to .rss until then.
- [ ] **GitHub cron is throttled (CONFIRMED 2026-09-25).** Scheduled `collect`
      runs DO fire but GitHub free/public repos heavily throttle `*/10` crons —
      observed gaps of 2h and 5h (runs at 3:43, 5:56, 11:03 AM PKT), not 10 min.
      This is a GitHub limitation; no yaml change fixes it. **Solution: external
      cron (cron-job.org, free) POSTing to the GitHub `workflow_dispatch` API
      every 10 min** (workflow_dispatch is not throttled). Needs a fine-grained
      GitHub PAT (repo: gta6-news-radar, Actions: read+write) stored IN
      cron-job.org (not in our repo). The `schedule:` block stays as a fallback.
      Endpoint: POST /repos/Myt1x54/gta6-news-radar/actions/workflows/collect.yml/dispatches
      body {"ref":"main"}. Alt (no external svc): a self-looping workflow — hacky,
      rejected for now. STATUS: instructions given to user; awaiting setup.
- [ ] **Vercel Deployment Protection blocks public access (2026-09-25).** New
      Vercel projects enable "Vercel Authentication" which puts a Vercel SSO login
      in front of ALL deployments — user couldn't open/share the site. Fix:
      Vercel → project → Settings → Deployment Protection → disable Vercel
      Authentication. Safe: our own Supabase login + RLS still gate the app.
      STATUS: instructions given to user; awaiting toggle.
- [ ] **web dev server must use webpack, not Turbopack** on this machine. Next 16
      Turbopack DEV fails to resolve `@swc/helpers/_/_interop_require_*` (500s),
      while the production `next build` (also Turbopack) resolves them fine.
      `.claude/launch.json` runs `next dev --webpack`. Cloudflare uses the
      production build, so deploy is unaffected. Root cause looks like a
      Turbopack-dev + @swc/helpers exports bug (not our code).
- [ ] **npm on this machine occasionally extracts packages incompletely**
      (hit missing next type files + apparent @swc/helpers gaps). Fix when seen:
      `npm cache clean --force` + delete node_modules + `npm install`.
- [ ] **Hydration warning in the user's Opera** (`MetadataWrapper hidden`) is
      browser-extension interference (dev overlay only). The one real risk —
      relative timestamps using Date.now() — is fixed via `components/TimeAgo.tsx`
      (client-only render).
- [ ] **Kotaku feed** SSL-handshake-times-out from the dev sandbox; likely a
      local network quirk — recheck on GitHub Actions, disable if it persists.
- [ ] **YouTube channel filtering:** broad channels (GTA Series Videos, TGG,
      MrBossFTW) often yield 0 GTA6 items via keyword filter; that's expected.
      Competitor-upload tracking (all uploads) is a separate Phase 7 flow.
- [ ] Pin/verify Python dep versions install cleanly on 3.12 in CI (dev machine
      runs 3.14, which works).
- [ ] Decide serverless host for "Generate more ideas" (Cloudflare Pages Function
      vs Supabase Edge Function) in Phase 8.
```
