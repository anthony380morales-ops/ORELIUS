# ORELIUS ⇄ LUCIUS Shared Memory

ORELIUS is the **shared-memory hub**. Both systems share one durable log stored in
ORELIUS's Postgres database. LUCIUS reads and writes it over a small secured API;
ORELIUS injects the most recent shared events into its brain on every message, so
**anything LUCIUS records, ORELIUS knows — and vice-versa.**

```
        LUCIUS  ──POST /api/memory──▶  ┌────────────────────┐
        (any     ◀──GET  /api/memory── │  ORELIUS (hub)     │
         stack)                        │  Postgres: shared  │──▶ injected into
                                       │  memory table      │    ORELIUS's persona
        ORELIUS writes its own          └────────────────────┘    each turn
        exchanges directly to the table
```

## 1. Turn it on (one env var)

On ORELIUS (Render → **orelius** → **Environment**), add:

| Variable | Value |
|---|---|
| `LUCIUS_SHARED_SECRET` | a long random string — the shared password between LUCIUS and ORELIUS |

Generate one: `openssl rand -hex 32`. Save it — LUCIUS sends it on every call.
(Until this is set, the `/api/memory` endpoints return **503**, by design.)

## 2. The API

Base URL: `https://orelius.onrender.com`
Auth header on every call: `X-Shared-Secret: <LUCIUS_SHARED_SECRET>`

### Write an event (LUCIUS → shared memory)
```
POST /api/memory
Content-Type: application/json
X-Shared-Secret: <secret>

{ "content": "Booked appointment with Jane Doe for Tue 2pm", "kind": "action", "actor": "LUCIUS",
  "meta": { "lead_id": 4821 } }
```
`kind` is a free label (`action`, `note`, `call`, `appointment`, …). `meta` is optional JSON.

### Read recent events (shared memory → LUCIUS)
```
GET /api/memory?limit=20            # newest last
GET /api/memory?limit=20&actor=ORELIUS   # only ORELIUS's entries
X-Shared-Secret: <secret>
```
Returns `{ "events": [ { ts, actor, kind, content, meta, created_at }, ... ], "count": N }`.

## 3. Drop-in LUCIUS clients

**Python**
```python
import httpx
ORELIUS = "https://orelius.onrender.com"
SECRET  = "<LUCIUS_SHARED_SECRET>"
H = {"X-Shared-Secret": SECRET}

def remember(content, kind="action", meta=None):
    httpx.post(f"{ORELIUS}/api/memory",
               json={"content": content, "kind": kind, "actor": "LUCIUS", "meta": meta or {}},
               headers=H, timeout=10)

def recall(limit=20):
    return httpx.get(f"{ORELIUS}/api/memory", params={"limit": limit}, headers=H, timeout=10).json()["events"]
```

**Node / JavaScript**
```js
const ORELIUS = "https://orelius.onrender.com";
const SECRET  = process.env.LUCIUS_SHARED_SECRET;
const H = { "X-Shared-Secret": SECRET, "Content-Type": "application/json" };

export const remember = (content, kind = "action", meta = {}) =>
  fetch(`${ORELIUS}/api/memory`, { method: "POST", headers: H,
    body: JSON.stringify({ content, kind, actor: "LUCIUS", meta }) });

export const recall = async (limit = 20) =>
  (await (await fetch(`${ORELIUS}/api/memory?limit=${limit}`, { headers: H })).json()).events;
```

**curl (quick test)**
```bash
curl -X POST https://orelius.onrender.com/api/memory \
  -H "X-Shared-Secret: $LUCIUS_SHARED_SECRET" -H "Content-Type: application/json" \
  -d '{"content":"LUCIUS online","kind":"note","actor":"LUCIUS"}'

curl "https://orelius.onrender.com/api/memory?limit=5" -H "X-Shared-Secret: $LUCIUS_SHARED_SECRET"
```

## 4. Where LUCIUS should call these

- **After every meaningful LUCIUS action** (a call handled, appointment booked, lead
  updated) → `remember(...)`. That entry then shows up in ORELIUS's next reply.
- **When LUCIUS wants ORELIUS's recent context** → `recall(...)` and feed it into
  whatever LUCIUS does.

## 5. Optional: push ORELIUS → LUCIUS too

If LUCIUS also exposes an HTTP endpoint, set these on ORELIUS and it will best-effort
POST each new event to `‹LUCIUS_API_URL›/memory` as it happens:

| Variable | Value |
|---|---|
| `LUCIUS_API_URL` | e.g. `https://lucius.example.com` |
| `LUCIUS_API_KEY` | optional bearer token LUCIUS expects |

Not required — LUCIUS pulling via `GET /api/memory` already keeps both in sync.

---

**Send me your LUCIUS code** (its language/stack and where it records what it does)
and I'll wire these calls into the exact right spots for you instead of you pasting
the snippets by hand.
