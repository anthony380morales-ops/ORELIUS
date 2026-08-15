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
STATE_FILE = Path(_env("BRIDGE_STATE_FILE", "") or (Path(__file__).resolve().parent / "athena_bridge_state.json"))

# ATHENA's job API accepts these actions; anything else is coerced to "brief".
ATHENA_ACTIONS = {"once", "batch", "autopilot", "research", "brief"}

_ORELIUS_HEADERS = {"X-Shared-Secret": ORELIUS_SECRET, "Content-Type": "application/json"}
_ATHENA_HEADERS = {"Authorization": f"Bearer {ATHENA_TOKEN}", "Content-Type": "application/json"}


def log(msg: str) -> None:
    print(f"[athena-bridge {time.strftime('%H:%M:%S')}] {msg}", flush=True)


# ----------------------------------------------------------------- state
def _load_last_id() -> int:
    try:
        return int(json.loads(STATE_FILE.read_text()).get("last_id", 0))
    except Exception:
        return 0


def _save_last_id(last_id: int) -> None:
    try:
        STATE_FILE.write_text(json.dumps({"last_id": last_id}))
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


def write_result(content: str, meta: dict) -> None:
    payload = {"content": content, "kind": "design_result", "actor": "ATHENA", "meta": meta}
    for attempt in range(2):
        try:
            r = requests.post(
                f"{ORELIUS_URL}/api/memory",
                json=payload,
                headers=_ORELIUS_HEADERS,
                timeout=20,
            )
            if r.status_code < 400:
                return
            log(f"ORELIUS POST /api/memory -> {r.status_code}")
        except Exception as e:
            log(f"ORELIUS unreachable on write ({e})")
        if attempt == 0:
            time.sleep(2)


# ----------------------------------------------------------------- ATHENA
def athena_start_job(action: str, days) -> str | None:
    body: dict = {"action": action}
    if isinstance(days, int):
        body["days"] = days
    try:
        r = requests.post(f"{ATHENA_BASE_URL}/jobs", json=body, headers=_ATHENA_HEADERS, timeout=20)
        if r.status_code == 202:
            return r.json().get("jobId")
        if r.status_code == 409:
            log("ATHENA is busy (409) — will retry this request next poll")
            return None
        log(f"ATHENA POST /jobs -> {r.status_code}: {r.text[:200]}")
    except Exception as e:
        log(f"ATHENA unreachable ({e}) — is she running on {ATHENA_BASE_URL}?")
    return None


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


# ----------------------------------------------------------------- loop
def handle_request(ev: dict) -> None:
    meta = ev.get("meta") or {}
    action = str(meta.get("action") or "brief").lower()
    if action not in ATHENA_ACTIONS:
        action = "brief"
    days = meta.get("days")
    brief = ev.get("content") or ""
    req_id = ev.get("id")

    log(f"design_request #{req_id}: action={action} — dispatching to ATHENA")
    job_id = athena_start_job(action, days)
    if not job_id:
        raise RuntimeError("job not accepted")  # leave unprocessed; retried next poll

    result = athena_wait(job_id)
    state = str(result.get("state") or result.get("status") or "unknown")
    summary = result.get("summary") or result.get("result") or result.get("message") or ""
    if isinstance(summary, (dict, list)):
        summary = json.dumps(summary)[:600]

    content = (
        f"ATHENA {action} job {state}. "
        + (f"Brief: {str(brief)[:200]}. " if brief else "")
        + (f"Result: {str(summary)[:600]}" if summary else "See ATHENA logs for details.")
    )
    write_result(content, {"request_id": req_id, "job_id": job_id, "action": action, "state": state})
    log(f"design_request #{req_id}: reported '{state}' back to ORELIUS")


def main() -> None:
    if not ORELIUS_SECRET:
        log("FATAL: ORELIUS_SHARED_SECRET is not set (must match ORELIUS). Exiting.")
        return
    if not ATHENA_TOKEN:
        log("WARNING: ATHENA_API_TOKEN is empty — ATHENA will reject jobs until it's set.")

    last_id = _load_last_id()
    log(f"Bridge online. ORELIUS={ORELIUS_URL}  ATHENA={ATHENA_BASE_URL}  last_id={last_id}")

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
                    _save_last_id(last_id)
                except Exception as e:
                    # Don't advance last_id: this request will be retried next cycle.
                    log(f"design_request #{ev_id} deferred ({e})")
                    break
        except Exception as e:  # noqa: BLE001 - the loop must never die
            log(f"loop error ({e})")
        time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    main()
