"""
athena_orelius_bridge.py  —  ORELIUS ⇄ ATHENA design bridge (runs on YOUR machine).

ATHENA listens only on localhost (127.0.0.1:8787), so cloud-hosted ORELIUS can't
reach her directly. This tiny daemon closes the loop from *inside* your machine:

    1. Polls ORELIUS shared memory for new `design_request` events (the ones the
       ORELIUS brain files whenever you ask it for design work).
    2. For each new request, calls ATHENA's local job API
       (POST /jobs {action, days?}) and waits for the job to finish.
    3. Writes a `design_result` event back into ORELIUS shared memory, so ORELIUS
       (and LUCIUS) can see what ATHENA did on the next turn.

Nothing about ATHENA is exposed to the internet — this process is the only thing
that talks to her, and it only talks *out* to ORELIUS over HTTPS.

------------------------------------------------------------------ setup
Put this file anywhere on your machine (e.g. next to ATHENA), install deps:

    pip install requests python-dotenv

Create a `.env` next to it (or set these in the environment):

    ORELIUS_URL=https://orelius.onrender.com
    ORELIUS_SHARED_SECRET=OreliusLucius2026        # must match ORELIUS's secret
    ATHENA_BASE_URL=http://127.0.0.1:8787
    ATHENA_API_TOKEN=<your ATHENA bearer token>    # same ATHENA_API_TOKEN ATHENA uses
    # optional:
    # BRIDGE_POLL_SECONDS=15
    # BRIDGE_JOB_TIMEOUT=1800
    # BRIDGE_STATE_FILE=./athena_bridge_state.json

Run it (keep it running — see README for PM2):

    python athena_orelius_bridge.py

It's best-effort and self-healing: if ORELIUS is asleep or ATHENA is busy, it
retries on the next poll. It never crashes on a single bad event.
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent / ".env")
    load_dotenv()
except Exception:
    pass

import requests


# ----------------------------------------------------------------- config
def _env(name: str, default: str = "") -> str:
    return (os.getenv(name) or default).strip()


ORELIUS_URL = _env("ORELIUS_URL", "https://orelius.onrender.com").rstrip("/")
ORELIUS_SECRET = _env("ORELIUS_SHARED_SECRET")
ATHENA_BASE_URL = _env("ATHENA_BASE_URL", "http://127.0.0.1:8787").rstrip("/")
ATHENA_TOKEN = _env("ATHENA_API_TOKEN")

POLL_SECONDS = int(_env("BRIDGE_POLL_SECONDS", "15") or "15")
JOB_TIMEOUT = int(_env("BRIDGE_JOB_TIMEOUT", "1800") or "1800")  # 30 min
# Heartbeat: how often to mirror ATHENA's own autonomous activity into ORELIUS
# shared memory (so ORELIUS knows what ATHENA did on its own, like LUCIUS does).
HEARTBEAT_SECONDS = int(_env("BRIDGE_HEARTBEAT_SECONDS", "600") or "600")  # 10 min
STATE_FILE = Path(_env("BRIDGE_STATE_FILE", "") or (Path(__file__).resolve().parent / "athena_bridge_state.json"))

# ATHENA's /jobs API actions. "publish" is the account-aware handler that publishes
# ORELIUS-SUPPLIED content to a specific account (accountId + content in the body);
# the others are ATHENA's own autopilot modes. An unknown action is coerced to "once".
ATHENA_ACTIONS = {"once", "batch", "autopilot", "research", "brief", "publish"}


class PermanentDispatchError(Exception):
    """ATHENA rejected the request with a 4xx — retrying won't help (e.g. it doesn't
    support the 'publish' action yet). Skip it instead of looping forever."""

_ORELIUS_HEADERS = {"X-Shared-Secret": ORELIUS_SECRET, "Content-Type": "application/json"}
_ATHENA_HEADERS = {"Authorization": f"Bearer {ATHENA_TOKEN}", "Content-Type": "application/json"}


def log(msg: str) -> None:
    print(f"[athena-bridge {time.strftime('%H:%M:%S')}] {msg}", flush=True)


# ----------------------------------------------------------------- state
def load_state() -> dict:
    """Full bridge state: last processed request id + heartbeat bookkeeping."""
    try:
        s = json.loads(STATE_FILE.read_text())
        if isinstance(s, dict):
            s.setdefault("last_id", 0)
            s.setdefault("seen_flagged", [])
            s.setdefault("last_scheduled", 0)
            s.setdefault("hb_seeded", False)
            return s
    except Exception:
        pass
    return {"last_id": 0, "seen_flagged": [], "last_scheduled": 0, "hb_seeded": False}


def save_state(state: dict) -> None:
    try:
        STATE_FILE.write_text(json.dumps(state))
    except Exception as e:
        log(f"warn: could not persist state ({e})")


# ----------------------------------------------------------------- ORELIUS
def fetch_events(limit: int = 50) -> list[dict]:
    """Recent shared-memory events (newest last)."""
    try:
        r = requests.get(
            f"{ORELIUS_URL}/api/memory",
            params={"limit": limit},
            headers=_ORELIUS_HEADERS,
            timeout=20,
        )
        if r.status_code == 200:
            return r.json().get("events", []) or []
        log(f"ORELIUS GET /api/memory -> {r.status_code}")
    except Exception as e:
        log(f"ORELIUS unreachable on read ({e})")
    return []


def write_event(content: str, kind: str, meta: dict) -> bool:
    """Write one event into ORELIUS shared memory as actor ATHENA."""
    payload = {"content": content, "kind": kind, "actor": "ATHENA", "meta": meta}
    for attempt in range(2):
        try:
            r = requests.post(
                f"{ORELIUS_URL}/api/memory",
                json=payload,
                headers=_ORELIUS_HEADERS,
                timeout=20,
            )
            if r.status_code < 400:
                return True
            log(f"ORELIUS POST /api/memory -> {r.status_code}")
        except Exception as e:
            log(f"ORELIUS unreachable on write ({e})")
        if attempt == 0:
            time.sleep(2)
    return False


def write_result(content: str, meta: dict) -> None:
    write_event(content, "design_result", meta)


# ----------------------------------------------------------------- ATHENA
def _post_athena(path: str, body: dict) -> str | None:
    """POST to an ATHENA endpoint that returns 202 {jobId}. Returns the jobId."""
    try:
        r = requests.post(f"{ATHENA_BASE_URL}{path}", json=body, headers=_ATHENA_HEADERS, timeout=30)
        if r.status_code == 202:
            return r.json().get("jobId")
        if r.status_code == 409:
            log(f"ATHENA busy (409) on {path} — will retry this request next poll")
            return None
        if 400 <= r.status_code < 500:
            # permanent: bad request / unsupported action → don't retry forever
            raise PermanentDispatchError(f"{r.status_code}: {r.text[:200]}")
        log(f"ATHENA POST {path} -> {r.status_code}: {r.text[:300]}")
    except PermanentDispatchError:
        raise
    except Exception as e:
        log(f"ATHENA unreachable ({e}) — is she running on {ATHENA_BASE_URL}?")
    return None


def _routing(meta: dict, brief: str) -> dict:
    """The account-routing + content fields ATHENA needs to publish the RIGHT
    content to the RIGHT account.

    Without these, ATHENA's /jobs pipeline just runs its own autopilot for its
    default connected account and ignores what ORELIUS actually compiled. ORELIUS
    stamps `brand` + `target` (e.g. brand='NXG Life Group', target='facebook_page')
    on every content-publish request, and `content` carries the exact caption/facts
    to publish. We forward them all so ATHENA's configured handler can route + use
    them. (Unknown fields are harmless if ATHENA ignores them.)"""
    r: dict = {}
    for k in ("accountId", "brandId", "brand", "platform", "target", "account",
              "publish", "format"):
        if meta.get(k) is not None:
            r[k] = meta[k]
    struct = meta.get("content")
    if isinstance(struct, dict):
        r["content"] = struct         # structured post ORELIUS compiled (caption/facts/…)
        if brief:
            r["brief"] = brief        # human-readable version of the same
    elif brief:
        r["content"] = brief          # the exact post ORELIUS compiled
        r["brief"] = brief            # alias — whichever key ATHENA reads
    return r


def athena_dispatch(kind: str, brief: str, meta: dict) -> str | None:
    """Start the right ATHENA job for this request kind. Returns a jobId to poll."""
    routing = _routing(meta, brief)
    tag = f" brand={routing.get('brand')} target={routing.get('target')}" if routing.get("brand") else ""

    if kind == "instagram_post":
        action = str(meta.get("action") or "once").lower()
        if action not in ATHENA_ACTIONS:
            action = "once"
        # IMPORTANT: forward the compiled content + account routing, not just the
        # action — otherwise ATHENA publishes its own autopilot content instead.
        body: dict = {"action": action, **routing}
        days = meta.get("days")
        if isinstance(days, int):
            body["days"] = days
        log(f"-> POST /jobs action={action}{tag}")
        return _post_athena("/jobs", body)

    if kind == "website":
        log(f"-> POST /site{tag}")
        return _post_athena("/site", {"prompt": brief, **routing})

    # default: design engine
    body = {"prompt": brief, **routing}
    task = meta.get("task")
    if isinstance(task, str) and task:
        body["task"] = task
    log(f"-> POST /design{f' task={task}' if task else ''}{tag}")
    return _post_athena("/design", body)


def athena_wait(job_id: str) -> dict:
    """Poll a job until it's no longer running or the timeout is hit."""
    deadline = time.time() + JOB_TIMEOUT
    last: dict = {"state": "unknown"}
    while time.time() < deadline:
        try:
            r = requests.get(f"{ATHENA_BASE_URL}/jobs/{job_id}", headers=_ATHENA_HEADERS, timeout=20)
            if r.status_code == 200:
                last = r.json() or last
                state = str(last.get("state") or last.get("status") or "").lower()
                if state in ("done", "success", "succeeded", "complete", "completed", "error", "failed"):
                    return last
        except Exception as e:
            log(f"ATHENA job poll error ({e})")
        time.sleep(5)
    last["state"] = last.get("state") or "timeout"
    return last


# ----------------------------------------------------------------- heartbeat
def athena_status() -> dict | None:
    """GET ATHENA's current status snapshot (scheduled / flagged / in-flight)."""
    try:
        r = requests.get(f"{ATHENA_BASE_URL}/status", headers=_ATHENA_HEADERS, timeout=15)
        if r.status_code == 200:
            return r.json()
        log(f"ATHENA GET /status -> {r.status_code}")
    except Exception as e:
        log(f"ATHENA status unreachable ({e})")
    return None


def heartbeat(state: dict) -> None:
    """Mirror ATHENA's own autonomous activity into ORELIUS shared memory.

    On first run it just records a baseline (so ORELIUS isn't flooded with the
    existing backlog). After that it reports only NEW activity: posts ATHENA
    newly scheduled to the feed, and posts it newly flagged below its gate.
    """
    st = athena_status()
    if not st:
        return

    handle = st.get("brandHandle") or "the brand"
    scheduled = int(st.get("scheduledUpcoming") or 0)
    flagged = st.get("flaggedForReview") or []
    flagged_ids = [int(f.get("id")) for f in flagged if f.get("id") is not None]
    seen = set(state.get("seen_flagged", []))

    # First heartbeat: seed the baseline, announce once, don't spam the backlog.
    if not state.get("hb_seeded"):
        write_event(
            f"ATHENA is online for {handle} — {scheduled} post(s) scheduled, {len(flagged_ids)} held for review.",
            "athena_activity",
            {"type": "online", "scheduled": scheduled, "flagged": len(flagged_ids), "handle": handle},
        )
        state["seen_flagged"] = flagged_ids[-200:]
        state["last_scheduled"] = scheduled
        state["hb_seeded"] = True
        save_state(state)
        return

    changed = False

    # Newly scheduled posts (queue grew) → ATHENA published/scheduled on its own.
    if scheduled > int(state.get("last_scheduled", 0)):
        diff = scheduled - int(state["last_scheduled"])
        write_event(
            f"ATHENA scheduled {diff} new post(s) to {handle}'s feed ({scheduled} upcoming).",
            "athena_activity",
            {"type": "scheduled", "new": diff, "upcoming": scheduled, "handle": handle},
        )
        changed = True
    if scheduled != int(state.get("last_scheduled", 0)):
        state["last_scheduled"] = scheduled
        changed = True

    # Newly flagged posts → ATHENA created content that didn't clear its gate.
    new_flagged = [f for f in flagged if int(f.get("id", -1)) not in seen]
    for f in new_flagged[:5]:  # cap per beat to avoid a burst
        theme = str(f.get("theme") or "").strip()[:180]
        write_event(
            f"ATHENA created a post held for review (score {f.get('score')}): “{theme}”.",
            "athena_activity",
            {"type": "flagged", "post_id": f.get("id"), "score": f.get("score"), "handle": handle},
        )
    if new_flagged:
        seen.update(int(f.get("id")) for f in flagged if f.get("id") is not None)
        state["seen_flagged"] = sorted(seen)[-200:]
        changed = True

    if changed:
        save_state(state)


# ----------------------------------------------------------------- loop
def _extract_assets(result: dict) -> list:
    """Best-effort pull of output file paths from an ATHENA job result."""
    if not isinstance(result, dict):
        return []
    for key in ("assets", "files", "outputs", "paths", "pngPaths", "images"):
        val = result.get(key)
        if isinstance(val, list) and val:
            return [str(v) for v in val][:10]
    return []


def handle_request(ev: dict) -> None:
    meta = ev.get("meta") or {}
    kind = str(meta.get("kind") or "design").lower()
    brief = ev.get("content") or ""
    req_id = ev.get("id")

    log(f"design_request #{req_id}: kind={kind} — dispatching to ATHENA")
    try:
        job_id = athena_dispatch(kind, brief, meta)
    except PermanentDispatchError as e:
        # ATHENA rejected it (e.g. it doesn't support the 'publish' action yet).
        # Report it once and move on — do NOT retry forever.
        action = meta.get("action")
        note = (f"ATHENA rejected the {kind} job ({e}). If action='{action}', ATHENA's "
                f"account-aware publish handler may not be live yet.")
        log(f"design_request #{req_id}: {note}")
        write_result(note, {"request_id": req_id, "kind": kind, "state": "rejected"})
        return   # caller advances last_id — skip, don't loop
    if not job_id:
        raise RuntimeError("job not accepted")  # leave unprocessed; retried next poll

    job = athena_wait(job_id)
    state = str(job.get("status") or job.get("state") or "unknown")
    inner = job.get("result") if isinstance(job.get("result"), dict) else job
    assets = _extract_assets(inner)

    # Build a human summary of what ATHENA produced.
    if state in ("failed", "error"):
        detail = str(job.get("error") or "see ATHENA logs")
        content = f"ATHENA {kind} job FAILED: {detail[:400]}"
    else:
        bits = []
        if isinstance(inner, dict):
            if "approved" in inner:
                bits.append(f"approved={inner.get('approved')} score={inner.get('score')}")
            if inner.get("note"):
                bits.append(str(inner["note"]))
            if inner.get("scheduled"):
                bits.append("scheduled to Instagram")
            if inner.get("savedTo"):
                bits.append(f"saved: {inner['savedTo']}")
        if assets:
            bits.append(f"{len(assets)} file(s): " + "; ".join(assets))
        summary = " | ".join(b for b in bits if b)
        if not summary:
            summary = json.dumps(inner)[:500] if isinstance(inner, (dict, list)) else "done"
        content = f"ATHENA {kind} job {state}. {summary}"

    write_result(
        content[:3900],
        {"request_id": req_id, "job_id": job_id, "kind": kind, "state": state, "assets": assets},
    )
    log(f"design_request #{req_id}: reported '{state}' back to ORELIUS")


def main() -> None:
    if not ORELIUS_SECRET:
        log("FATAL: ORELIUS_SHARED_SECRET is not set (must match ORELIUS). Exiting.")
        return
    if not ATHENA_TOKEN:
        log("WARNING: ATHENA_API_TOKEN is empty — ATHENA will reject jobs until it's set.")

    state = load_state()
    last_id = int(state.get("last_id", 0))
    log(
        f"Bridge online. ORELIUS={ORELIUS_URL}  ATHENA={ATHENA_BASE_URL}  "
        f"last_id={last_id}  heartbeat={HEARTBEAT_SECONDS}s"
    )

    last_hb = 0.0
    while True:
        try:
            events = fetch_events(limit=50)
            # New design requests only, in chronological order.
            pending = sorted(
                (e for e in events
                 if e.get("kind") == "design_request" and int(e.get("id") or 0) > last_id),
                key=lambda e: int(e.get("id") or 0),
            )
            for ev in pending:
                ev_id = int(ev.get("id") or 0)
                try:
                    handle_request(ev)
                    last_id = max(last_id, ev_id)
                    state["last_id"] = last_id
                    save_state(state)
                except Exception as e:
                    # Don't advance last_id: this request will be retried next cycle.
                    log(f"design_request #{ev_id} deferred ({e})")
                    break

            # Heartbeat: mirror ATHENA's own autonomous activity into shared memory.
            if time.time() - last_hb >= HEARTBEAT_SECONDS:
                heartbeat(state)
                last_hb = time.time()
        except Exception as e:  # noqa: BLE001 - the loop must never die
            log(f"loop error ({e})")
        time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    main()
