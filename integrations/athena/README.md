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
1800s), `BRIDGE_STATE_FILE`.

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

The brain picks an `action` for each request (mirrors ATHENA's `/jobs` actions):

| action | ATHENA does |
|---|---|
| `brief` (default) | draft a creative brief / plan |
| `once` | produce one design/post now |
| `batch` | produce a batch |
| `research` | gather references/ideas first |
| `autopilot` | run her full autonomous pipeline |
| `status` | just report what she's doing |

The bridge posts `{action, days?}` to ATHENA's `POST /jobs`, waits for the job to
finish (`GET /jobs/:id`), then writes a `design_result` back to ORELIUS.

## Notes

- **Best-effort & self-healing.** If ORELIUS is asleep (free-tier cold start) or
  ATHENA is busy (`409`), the request stays queued and is retried on the next poll.
  The loop never dies on a single bad event.
- **De-duplication.** Processed request IDs are tracked in `athena_bridge_state.json`
  so a request is dispatched to ATHENA exactly once, even across restarts.
- **Security.** The bridge only makes **outbound** calls — HTTPS to ORELIUS and
  localhost to ATHENA. ATHENA stays bound to `127.0.0.1`; nothing new is opened to
  the internet.
