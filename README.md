# GTA 6 News Radar

A private, $0-budget tool that automatically collects GTA 6 news, de-duplicates
and clusters it into stories, uses AI to summarize / score / suggest YouTube
video ideas, ranks it all on a dashboard, and emails you when something big
breaks.

- **Collector:** Python 3.12 (runs on GitHub Actions cron)
- **Database + Auth:** Supabase (free tier)
- **AI:** Google Gemini (primary) + Groq (fallback)
- **Frontend:** Next.js + Tailwind on Cloudflare Pages (PWA)
- **Email:** Gmail SMTP (App Password)

> **Project memory lives in [`CLAUDE.md`](CLAUDE.md).** Read it to see current
> status, decisions, and what's next. Full brief: [`docs/PROJECT_BRIEF.md`](docs/PROJECT_BRIEF.md).

---

## ⚠️ Never commit secrets

This repo is public. All keys go in a local `.env` (gitignored) or GitHub
Secrets. `.env.example` lists the variable **names** only. Double-check `git
status` never shows `.env` before committing.

---

## Setup (one-time manual steps)

Everything below is free and requires **no credit card**. Do these in order.
You only need to finish Steps 1–3 before development can start on Phase 2; the
rest can wait until their phase.

### Step 1 — Clone and create your local `.env`

1. Clone the repo and `cd` into it.
2. Copy the example env file:
   ```bash
   cp .env.example .env
   ```
3. Leave it open — you'll paste keys into it as you create them below.

### Step 2 — Supabase (database + auth)

1. Go to <https://supabase.com> and sign up (GitHub login is fine). Free tier,
   no card.
2. Click **New project**. Pick a name (e.g. `gta6-news-radar`), a strong
   database password (save it in your password manager), and the region closest
   to you. Wait ~2 minutes for it to provision.
3. In the project, go to **Project Settings → API**. Copy these into `.env`:
   - **Project URL** → `SUPABASE_URL`
   - **`anon` `public` key** → `SUPABASE_ANON_KEY`
   - **`service_role` key** (click to reveal) → `SUPABASE_SERVICE_ROLE_KEY`
     *(secret — collector only, never in the browser)*
4. Create the tables: go to **SQL Editor → New query**, open
   [`supabase/migrations/0001_initial_schema.sql`](supabase/migrations/0001_initial_schema.sql),
   paste its full contents, and click **Run**. You should see the 7 tables under
   **Table Editor**.
5. **Disable public sign-ups:** **Authentication → Sign In / Providers → Email**
   (or **Authentication → Settings**), turn **Allow new users to sign up** OFF.
6. **Create your login account manually:** **Authentication → Users → Add user →
   Create new user**. Enter your email + a password and confirm. (Repeat for a
   2nd user if needed.) This is how you'll log into the dashboard later.

### Step 3 — Google Gemini API key (primary AI)

1. Go to <https://aistudio.google.com/apikey> and sign in with a Google account.
2. Click **Create API key** (free tier, no card). Copy it → `GEMINI_API_KEY`.
3. Leave `GEMINI_MODEL=gemini-3.5-flash-lite` (the default). Only change it if
   you hit quality/limits — see the note in `.env.example`. **Never** pick a Pro
   model (not free).

### Step 4 — Groq API key (fallback AI)

1. Go to <https://console.groq.com/keys> and sign up (free, no card).
2. Click **Create API Key**, copy it → `GROQ_API_KEY`.
3. Check the current free model list at <https://console.groq.com/docs/models>
   and set `GROQ_MODEL` accordingly (default `llama-3.3-70b-versatile` — verify
   it still exists).

### Step 5 — Gmail App Password (email)

> Requires 2-Step Verification enabled on your Google account.

1. Enable 2-Step Verification: <https://myaccount.google.com/signinoptions/two-step-verification>.
2. Go to <https://myaccount.google.com/apppasswords>. Name it `GTA6 News Radar`
   and click **Create**. Google shows a **16-character password** — copy it
   (spaces don't matter) → `SMTP_PASS`.
3. Set `SMTP_USER` to your Gmail address and `ALERT_TO` to where you want alerts
   (can be the same address). Leave `SMTP_HOST=smtp.gmail.com` and `SMTP_PORT=587`.

### Step 6 — YouTube Data API v3 key (trends, Phase 7)

1. Go to <https://console.cloud.google.com/> and create a project (free).
2. **APIs & Services → Library**, search **YouTube Data API v3**, click **Enable**.
3. **APIs & Services → Credentials → Create credentials → API key**. Copy it →
   `YOUTUBE_API_KEY`. (Optionally restrict the key to the YouTube Data API.)

### Step 7 — GitHub repo + Secrets (scheduler, Phase 4)

The collector runs on GitHub Actions via [`.github/workflows/collect.yml`](.github/workflows/collect.yml)
(every 10 minutes). To enable it:

1. **Push this repo to a PUBLIC GitHub repo** (public = free unlimited Actions
   minutes). Make sure `.env` is NOT committed (it's gitignored — verify with
   `git status`).
2. In the repo: **Settings → Secrets and variables → Actions → New repository
   secret**. Add these:

   **Required** (the collector won't work without them):
   - `SUPABASE_URL`
   - `SUPABASE_SERVICE_ROLE_KEY`
   - `GEMINI_API_KEY`
   - `GROQ_API_KEY`

   **For email (Phase 6 — breaking alerts + daily digest):**
   - `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASS`, `ALERT_TO` (from README
     Step 5). Without these, the app still works — it just won't send email.

   **Optional** (only if you set up that source / want to override a default):
   - `REDDIT_CLIENT_ID`, `REDDIT_CLIENT_SECRET` (if you did the Reddit app)
   - `YOUTUBE_API_KEY` (used from Phase 7)
   - `DASHBOARD_URL` (defaults to the Vercel URL; only set if you use a custom domain)
   - `GEMINI_MODEL`, `GROQ_MODEL`, `USER_AGENT`, `APP_TIMEZONE`, `ALERT_THRESHOLD`
     (all have sensible defaults in code — only add to override)

   *(You do NOT need `SUPABASE_ANON_KEY` or the `SMTP_*` secrets here yet — anon
   is for the frontend; SMTP is added in Phase 6.)*

3. **Test it now:** go to the **Actions** tab → **collect** workflow → **Run
   workflow** (manual trigger). Watch it run green, then check new rows in your
   Supabase tables.

> Notes: GitHub only runs `schedule:` workflows on the **default branch**, and it
> **pauses schedules after 60 days with no repo commits** (just push anything to
> resume). Scheduled runs can be delayed a few minutes at peak times — expected.

### Step 8 — Deploy the dashboard to Vercel (Phase 5)

We deploy the Next.js dashboard to **Vercel** (free Hobby tier, no card). It runs
Next.js natively — no adapter needed. The app deliberately uses **no Vercel-only
features**, so it stays portable. (If you ever move to Cloudflare, use the
OpenNext adapter `@opennextjs/cloudflare` — not the deprecated
`@cloudflare/next-on-pages`.)

1. Make sure your latest code (the `web/` app) is **pushed to GitHub**.
2. Go to <https://vercel.com> → sign in **with GitHub** (free, no card).
3. **Add New… → Project** → **Import** your `gta6-news-radar` repo.
4. In the import screen:
   - **Root Directory:** click **Edit** and set it to **`web`** (important — the
     Next app lives in the `web/` subfolder).
   - Framework preset auto-detects **Next.js**. Leave build/output defaults.
5. Expand **Environment Variables** and add the two public frontend vars (copy
   values from `web/.env.local`):
   - `NEXT_PUBLIC_SUPABASE_URL`
   - `NEXT_PUBLIC_SUPABASE_ANON_KEY`
6. Click **Deploy**. After ~1–2 min you get a live URL like
   `https://gta6-news-radar.vercel.app`. Open it and log in with your Supabase
   account.

> Every future `git push` to the default branch auto-deploys. The service-role
> key is **never** in the frontend — only the public anon key, with RLS enforcing
> access.

---

## Running locally

```bash
# Python collector
python -m venv .venv
source .venv/Scripts/activate          # Windows Git Bash;  use bin/activate on macOS/Linux
pip install -r collector/requirements.txt
python collector/run.py                # (available from Phase 2)

# Tests
pytest collector/tests
```

---

## Development phases

See [`CLAUDE.md`](CLAUDE.md) for live status. Order: **1 Setup ✅ → 2 Collector →
3 Clustering + AI → 4 GitHub Actions → 5 Dashboard → 6 Email → 7 YouTube trends →
8 Polish (PWA, on-demand ideas, settings, housekeeping).**

Each phase is finished and tested before the next begins.
