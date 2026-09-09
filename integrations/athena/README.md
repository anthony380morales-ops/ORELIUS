# Connect ORELIUS ⇄ ATHENA (design agent)

ATHENA is your autonomous design/content agent. She runs 24/7 on **your machine**
and only listens on `127.0.0.1:8787`, so cloud-hosted ORELIUS can't call her
directly. This bridge closes the loop from inside your machine — **no code changes
to ATHENA, and nothing about ATHENA is exposed to the internet.**

## How it works

```
  You: "ORELIUS, have Athena design a launch post"
        │
        ▼
  ORELIUS brain calls its athena_design tool
        │  writes a `design_request` event
        ▼
  ORELIUS shared memory (Postgres)  ◀───────────────┐
        │                                            │
        │  bridge polls for new design_requests      │  bridge writes a
        ▼                                            │  `design_result` back
  athena_orelius_bridge.py  ──POST /jobs──▶ ATHENA ──┘
   (runs on YOUR machine)     localhost 8787
```

Next time you talk to ORELIUS, it already sees ATHENA's `design_result` in shared
memory (LUCIUS sees it too — all three now share one memory).

## 1. Install

On the machine where ATHENA runs:

```bash
pip install requests python-dotenv
```

Copy `athena_orelius_bridge.py` anywhere convenient (e.g. next to ATHENA).

## 2. Configure

Create a `.env` next to the bridge file:

```
ORELIUS_URL=https://orelius.onrender.com
ORELIUS_SHARED_SECRET=OreliusLucius2026
ATHENA_BASE_URL=http://127.0.0.1:8787
ATHENA_API_TOKEN=<the same ATHENA_API_TOKEN ATHENA uses>
```

- `ORELIUS_SHARED_SECRET` must match the `LUCIUS_SHARED_SECRET` set on ORELIUS in
  Render (it's the shared password for `/api/memory` — same one LUCIUS uses).
- `ATHENA_API_TOKEN` is ATHENA's own bearer token (from ATHENA's `.env`). The bridge
  sends it as `Authorization: Bearer …` on every job call.
- `ATHENA_BASE_URL` / `ATHENA_PORT` — change only if you run ATHENA on a non-default
  host/port.

Optional tuning: `BRIDGE_POLL_SECONDS` (default 15), `BRIDGE_JOB_TIMEOUT` (default
1800s), `BRIDGE_HEARTBEAT_SECONDS` (default 600), `BRIDGE_STATE_FILE`.

### Heartbeat — ATHENA's own activity in shared memory
Beyond the jobs ORELIUS dispatches, the bridge also polls ATHENA's `/status` on a
heartbeat (default every 10 min) and mirrors ATHENA's **autonomous** activity into
ORELIUS shared memory as `athena_activity` events — new posts scheduled to the
feed, and posts held below the quality gate. So ORELIUS always knows what ATHENA
did on its own, exactly like LUCIUS. The first heartbeat only records a baseline
(no backlog flood); after that it reports deltas only.

## 3. Run it (keep it running)

Quick test in a terminal:

```bash
python athena_orelius_bridge.py
```

You should see `Bridge online. ORELIUS=… ATHENA=…`. Ask ORELIUS for something
design related and watch it dispatch a `design_request` to ATHENA.

Since ATHENA already runs under **PM2**, add the bridge the same way so it stays up
and restarts with your machine:

```bash
pm2 start athena_orelius_bridge.py --name athena-bridge --interpreter python
pm2 save
```

(Windows without PM2: run it in its own terminal, or use Task Scheduler /
`pm2-installer`. It's a plain long-running Python script.)

## What ORELIUS sends

The brain tags each request with a `kind`, and the bridge routes it to the right
ATHENA endpoint (all polled at `/jobs/:id`):

| kind | endpoint | ATHENA does |
|---|---|---|
| `design` | `POST /design {prompt}` | generate a design asset (logo, poster, social graphic, product/lifestyle art…) → saved to `output/design` |
| `instagram_post` | `POST /jobs {action}` | research + create + publish/schedule a real Instagram post (`action`: `once` default, `autopilot`, `batch`, `research`, `brief`) |
| `website` | `POST /site {prompt}` | build a website / landing page |

The bridge waits for the job to finish, then writes a `design_result` back to
ORELIUS with the outcome (file paths, quality score, or "scheduled to Instagram").
Design and website jobs do **not** block on ATHENA's single-flight lock, so they
can run anytime — even during an autopilot post run.

## Publishing the RIGHT content to the RIGHT account (multi-brand)

ORELIUS builds brand-tailored posts for more than one account — **ibluezcluezflow**
(Instagram reels) and **NXG Life Group** (Facebook post) — and stamps every
content-publish request with routing + the exact content. As of the multi-account
fix, the bridge **forwards all of it** to ATHENA in the job body (it previously sent
only `{"action": "once"}`, which made ATHENA run its own autopilot for its default
connected account and ignore what ORELIUS compiled):

```jsonc
POST /jobs
{
  "action":  "once",
  "brand":   "NXG Life Group",     // or "ibluezcluezflow"
  "target":  "facebook_page",      // or "instagram_reels"
  "publish": true,
  "format":  "facebook_post",      // or "reel"
  "content": "…the exact caption + facts + post idea ORELIUS compiled…",
  "brief":   "…same text, alias key…"
}
```

**ATHENA must read these fields.** For each account to receive the correct financial
post, ATHENA's `/jobs` (and `/design`) handler needs to:

1. Route by `brand` / `target` to the correct connected account — **not** default to
   whatever account autopilot normally posts to (e.g. herironwill).
2. Publish the supplied `content` / `brief` **verbatim** (subject to ATHENA's quality
   gate + roadmap) instead of generating its own topic.

If ATHENA ignores the body and just runs `action: once`, it will keep posting its own
autopilot content to its default account — that is the symptom this fix targets on
the ORELIUS side; the matching change is in ATHENA's job handler. The field names
above are what the bridge sends; align ATHENA's handler to them (or tell us the names
ATHENA expects and we'll match them exactly).

## Notes

- **Best-effort & self-healing.** If ORELIUS is asleep (free-tier cold start) or
  ATHENA is busy (`409`), the request stays queued and is retried on the next poll.
  The loop never dies on a single bad event.
- **De-duplication.** Processed request IDs are tracked in `athena_bridge_state.json`
  so a request is dispatched to ATHENA exactly once, even across restarts.
- **Security.** The bridge only makes **outbound** calls — HTTPS to ORELIUS and
  localhost to ATHENA. ATHENA stays bound to `127.0.0.1`; nothing new is opened to
  the internet.
