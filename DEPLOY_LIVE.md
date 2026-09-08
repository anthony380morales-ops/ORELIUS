# Deploy ORELIUS Live — Free, HTTPS, on your phone

ORELIUS runs as **one container**: the FastAPI backend also serves the phone app,
so you deploy a single service. The recommended path is **100% free**, gives a
secure `https://…onrender.com` address, and installs to your home screen.

- **App host:** Render.com — free web service, automatic HTTPS.
- **Database:** Neon.tech — free, permanent PostgreSQL.
- **Login:** built in (master password) — the URL is protected.

> Trade-off of "free": Render's free service **sleeps after ~15 min idle**, so the
> first message after a quiet spell takes ~30–60s to wake. Every message after is
> instant. If you want always-on free, use **Koyeb** instead (same steps — see the
> bottom). If you want zero cold starts, Render's paid instance is ~$7/mo.

---

## Before you start (gather 3 things)

1. **Anthropic API key** — https://console.anthropic.com → API Keys.
   🔐 Regenerate the old key that was in your docs and use the new one only.
2. A **master password** you'll type to log in (make one up, keep it safe).
3. A **login ID** you'll type (e.g. `anthony`).

You'll also create free Render and Neon accounts below (GitHub login works for both).

---

## STEP 1 — Get the code onto `main`

Render deploys the `main` branch. Merge the rebuild branch into `main`:
- GitHub → your repo → **Pull requests** → **New** → base `main`, compare
  `claude/orelius-github-migration-qr1ve2` → **Create** → **Merge**.
- Or just tell me "open the PR" and I'll open it for you.

---

## STEP 2 — Create the free database (Neon)

1. Go to **https://neon.tech** → **Sign up** (use GitHub).
2. Click **Create project** (any name, e.g. `orelius`). Pick the region nearest you.
3. On the project dashboard, find **Connection string** → copy the one labeled
   **`psql` / URI**. It looks like:
   `postgresql://user:pass@ep-xxxx.us-east-2.aws.neon.tech/neondb?sslmode=require`
4. **Save that whole string** — it's your `DATABASE_URL`. (ORELIUS already knows how
   to talk to Neon's SSL database.)

---

## STEP 3 — Deploy the app (Render)

1. Go to **https://render.com** → **Sign up** (use GitHub).
2. Click **New +** → **Blueprint**.
3. Choose your **ORELIUS** repo. Render finds the `render.yaml` in it and shows a
   service named **orelius**. Click **Apply**.
4. Render asks for the values marked "sync: false". Enter:
   | Field | Value |
   |---|---|
   | `DATABASE_URL` | the Neon string from Step 2 |
   | `ANTHROPIC_API_KEY` | your Anthropic key |
   | `MASTER_PASSWORD` | your chosen password |
   | `TELEGRAM_ALLOWED_USERS` | your login ID, e.g. `anthony` |

   (`JWT_SECRET_KEY` and `ENCRYPTION_KEY` are generated for you — leave them.)
5. Click **Apply / Create**. Render builds the container (~4–8 min the first time).

When it's done, Render shows a green **Live** badge and your URL at the top:
`https://orelius.onrender.com` (your exact name may differ).

---

## STEP 4 — First login

Open your Render URL in a browser. You'll see the **ORELIUS login**.
Sign in with your **login ID** + **master password**. You're live. 🎉

If it says:
- **403** → the ID you typed isn't in `TELEGRAM_ALLOWED_USERS` (fix it in Render → Environment).
- **401** → wrong master password.

---

## STEP 5 — Put ORELIUS on your phone home screen

**iPhone (Safari):** open the URL → tap **Share** → **Add to Home Screen** → **Add**.
**Android (Chrome):** open the URL → tap **⋮** → **Install app** → **Install**.

Launch it from the ORELIUS icon — it opens full screen like a real app, and stays
logged in (tokens auto-refresh for 30 days).

---

## Updating later

Every push to `main` auto-redeploys (Render `autoDeploy: true`). Athena's design
changes will go live on the next push with no extra steps.

---

## Optional: custom domain

Render → your service → **Settings → Custom Domains** → add
`orelius.yourdomain.com` and set the DNS CNAME Render shows. HTTPS is automatic.

---

## Always-on free alternative — Koyeb

If the free cold-start bothers you, **Koyeb** runs the same container free without
sleeping:
1. Neon database exactly as in Step 2.
2. **https://koyeb.com** → **Create Service** → **GitHub** → your repo →
   **Dockerfile** builder (it uses the root `Dockerfile`).
3. Add the same environment variables from Step 3 (for `JWT_SECRET_KEY` and
   `ENCRYPTION_KEY`, generate two long random strings yourself).
4. Deploy → you get a free `https://…koyeb.app` URL. Install to home screen as above.

---

## Notes

- **Redis not required** — rate limiting is in-memory.
- **Telegram optional** — leave `TELEGRAM_BOT_TOKEN` unset; the bot just won't start.
- **DigitalOcean** is still supported if you ever want it — the repo also ships
  `.do/app.yaml`. But the free Render + Neon path above needs no paid host.
