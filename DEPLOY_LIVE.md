# Deploy ORELIUS Live (and onto your phone home screen)

This is the simplest path to a live, HTTPS ORELIUS you can install as an app on
your phone. It uses **DigitalOcean App Platform** — it builds straight from this
GitHub repo, gives you a secure `https://…ondigitalocean.app` address, and runs a
managed PostgreSQL database for you. No servers to manage.

> ORELIUS installs as a **PWA** (Progressive Web App): you open the site once in
> your phone browser and "Add to Home Screen." It then behaves like a normal app
> icon — full screen, no browser bars.

---

## What you'll need (5 minutes to gather)

1. A **DigitalOcean account** — https://cloud.digitalocean.com
2. Your **Anthropic API key** — https://console.anthropic.com (Settings → API Keys).
   *(Rotate the old one that was in your docs — see the note at the bottom.)*
3. Two random secrets and a password (generated in Step 2).

Estimated cost: ~**$5/mo** backend + ~**$7/mo** dev database (App Platform basic tiers). The frontend static site is free.

---

## Step 1 — Put the code on your `main` branch

The deploy reads the `main` branch. Merge the rebuild branch into `main`
(GitHub → **Pull requests** → open a PR from `claude/orelius-github-migration-qr1ve2`
into `main` → **Merge**), or ask me to open that PR for you.

---

## Step 2 — Generate your secrets

Run these (Mac/Linux terminal, or any online "openssl" — or just make up long random strings):

```bash
openssl rand -base64 32   # use this for JWT_SECRET_KEY
openssl rand -hex 32      # use this for ENCRYPTION_KEY
```

Also decide:
- **MASTER_PASSWORD** — the password you'll type to log into ORELIUS.
- **TELEGRAM_ALLOWED_USERS** — the login *user ID* you'll type (e.g. `anthony`).
  You log in with this ID **plus** the master password.

Keep these four values handy for Step 4.

---

## Step 3 — Create the app on DigitalOcean

**Easiest (dashboard):**
1. DigitalOcean → **Apps** → **Create App** → **GitHub** → pick `anthony380morales-ops/ORELIUS`, branch `main`.
2. DigitalOcean auto-detects this repo's `/.do/app.yaml` spec — accept it. It sets up:
   - a **backend** service (Docker) on `/api` and `/ws`,
   - a **frontend** static site (the app) on `/`,
   - a **managed Postgres** database wired to the backend automatically.
3. Continue to the review screen.

**Or with the CLI** (if you use `doctl`):
```bash
doctl apps create --spec .do/app.yaml
```

---

## Step 4 — Fill in your secrets

On the app's **Settings → Environment Variables** (backend component), replace the
placeholder values:

| Variable | Set it to |
|---|---|
| `ANTHROPIC_API_KEY` | your Anthropic key |
| `JWT_SECRET_KEY` | the `openssl rand -base64 32` value |
| `ENCRYPTION_KEY` | the `openssl rand -hex 32` value |
| `MASTER_PASSWORD` | your chosen password |
| `TELEGRAM_ALLOWED_USERS` | your chosen login ID (e.g. `anthony`) |

`DATABASE_URL`, `FRONTEND_URL`, and `BACKEND_URL` are filled in automatically — leave them.

Click **Save**. The app redeploys.

---

## Step 5 — First deploy

Wait for the build to go green (~3–6 min). DigitalOcean shows your live URL at the
top, e.g. `https://orelius-xxxxx.ondigitalocean.app`. Open it — you'll see the
**ORELIUS login**. Sign in with your user ID + master password. You're live.

---

## Step 6 — Install on your phone home screen

**iPhone (Safari):**
1. Open your ORELIUS URL in **Safari**.
2. Tap the **Share** button → **Add to Home Screen** → **Add**.
3. Launch it from the new ORELIUS icon — it opens full screen, like an app.

**Android (Chrome):**
1. Open the URL in **Chrome**.
2. Tap **⋮** → **Install app** (or **Add to Home screen**) → **Install**.

Log in once and it stays logged in (tokens refresh automatically for 30 days).

---

## Optional — a custom domain

App → **Settings → Domains** → add e.g. `orelius.yourdomain.com` and point the DNS
CNAME as DigitalOcean instructs. HTTPS is issued automatically. Then reinstall from
the new address.

---

## Notes & troubleshooting

- **Redis is not required** — the rate limiter runs in-memory, so the minimal setup
  (Postgres only) is all you need. You can add managed Redis later and set `REDIS_URL`.
- **Telegram is optional** — leave `TELEGRAM_BOT_TOKEN` unset and the bot simply
  doesn't start. Set `TELEGRAM_ALLOWED_USERS` regardless; it's your login allow-list.
- **Build fails on the backend?** Check the build logs — usually a missing secret.
  All five secrets in Step 4 must be set.
- **Can't log in (403)?** The user ID you typed isn't in `TELEGRAM_ALLOWED_USERS`.
- **Can't log in (401)?** Wrong master password.
- 🔐 **Rotate your Anthropic key.** The one previously written into your deployment
  docs should be regenerated in the Anthropic Console and only the new one used here.

---

## Even simpler alternative (Render.com)

If you'd rather not use DigitalOcean, **Render** is similar: New → **Blueprint**,
point it at this repo, and it can auto-provision a free Postgres. I can add a
`render.yaml` on request. DigitalOcean App Platform is the path documented above
because you already use DigitalOcean.
