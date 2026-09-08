# ORELIUS ⇄ ATHENA (design agent)

ORELIUS can now delegate any **design / branding / visual / content** work to
**ATHENA**, your autonomous design agent — and all three systems (ORELIUS, LUCIUS,
ATHENA) share one memory.

Because ATHENA runs 24/7 on **your machine** and only listens on `127.0.0.1:8787`,
the cloud-hosted ORELIUS never calls her directly. It delegates through shared
memory, and a tiny bridge daemon on your machine does the local hand-off.

```
  You ─▶ ORELIUS (Haiku brain, cloud)
              │  athena_design tool → `design_request` event
              ▼
        Shared memory (ORELIUS Postgres)  ◀── `design_result` ──┐
              │                                                  │
        athena_orelius_bridge.py (your machine) ──POST /jobs──▶ ATHENA (localhost)
```

## What changed in ORELIUS (already done, in this repo)

- **`backend/app/core/athena.py`** — the `athena_design` tool schema, the
  `enqueue_design_request()` that files a `design_request` into shared memory, and
  ORELIUS's spoken confirmation.
- **`backend/app/core/claude_client.py`** — `complete_with_tools()` so the Haiku
  brain can call tools.
- **`backend/app/core/oreilus_engine.py`** — the non-streaming reply path now offers
  the `athena_design` tool; when the brain uses it, ORELIUS dispatches the job in a
  **single model turn** (no extra credits) and confirms to you.
- **Shared memory** now surfaces ATHENA's `design_result` events back into ORELIUS's
  persona each turn (LUCIUS sees them too).

No new secrets are required on ORELIUS. It reuses the same `LUCIUS_SHARED_SECRET`
that already guards `/api/memory`. (Toggle with `ATHENA_ENABLED`, default on.)

## What you run on your machine (one small daemon)

Everything is in **`integrations/athena/`**:

1. `pip install requests python-dotenv`
2. Copy `athena_orelius_bridge.py` next to ATHENA and add a `.env`:
   ```
   ORELIUS_URL=https://orelius.onrender.com
   ORELIUS_SHARED_SECRET=OreliusLucius2026
   ATHENA_BASE_URL=http://127.0.0.1:8787
   ATHENA_API_TOKEN=<your ATHENA bearer token>
   ```
3. Start it under PM2 (same as ATHENA):
   ```bash
   pm2 start athena_orelius_bridge.py --name athena-bridge --interpreter python
   pm2 save
   ```

Full details and troubleshooting: **`integrations/athena/README.md`**.

## Try it

Ask ORELIUS: *"Have Athena draft a creative brief for a product launch post."*
ORELIUS replies that it dispatched the job to ATHENA; the bridge runs it locally;
ATHENA's result appears in ORELIUS's shared memory and it surfaces to you on the
next message.
