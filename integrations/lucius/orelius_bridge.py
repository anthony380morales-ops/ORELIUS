"""
orelius_bridge.py  —  LUCIUS -> ORELIUS shared-memory bridge.

Drop this file into the LUCIUS project root (next to agent.py / tools.py).
It pushes what LUCIUS does into ORELIUS's shared memory and pulls ORELIUS's
recent activity back, so the two share one brain.

Setup (LUCIUS .env):
    ORELIUS_URL=https://orelius.onrender.com
    ORELIUS_SHARED_SECRET=OreliusLucius2026     # must match ORELIUS's secret

Everything here is best-effort and never raises — if ORELIUS is unreachable,
LUCIUS keeps working and the event is simply skipped.
"""
from __future__ import annotations

import asyncio
import os
import time

# Load LUCIUS's .env so this works no matter the import order (and in bare tests).
try:
    from pathlib import Path
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent / ".env")
    load_dotenv()
except Exception:
    pass

import requests

# Read live each call so a late-loaded .env is always respected.
def _url() -> str:
    return os.getenv("ORELIUS_URL", "https://orelius.onrender.com").rstrip("/")


def _secret() -> str:
    return os.getenv("ORELIUS_SHARED_SECRET", "")


def _headers() -> dict:
    return {"X-Shared-Secret": _secret(), "Content-Type": "application/json"}


# Convenience constant (populated after .env load above) for quick health checks.
ORELIUS_SHARED_SECRET = _secret()

# Generous write timeout so a cold (free-tier) ORELIUS has time to wake.
_WRITE_TIMEOUT = 20
_READ_TIMEOUT = 12


def _enabled() -> bool:
    return bool(_secret())


# ---------------------------------------------------------------- writes
def remember_sync(content: str, kind: str = "action", meta: dict | None = None) -> None:
    """Record a LUCIUS event into ORELIUS shared memory (blocking; use in a thread)."""
    if not _enabled() or not content:
        return
    payload = {"content": str(content), "kind": kind, "actor": "LUCIUS", "meta": meta or {}}
    for attempt in range(2):  # one retry helps survive a cold-start wake
        try:
            r = requests.post(
                f"{_url()}/api/memory",
                json=payload,
                headers=_headers(),
                timeout=_WRITE_TIMEOUT,
            )
            if r.status_code < 400:
                return
        except Exception:
            pass
        if attempt == 0:
            time.sleep(2)


async def remember(content: str, kind: str = "action", meta: dict | None = None) -> None:
    """Async wrapper — safe to await from LUCIUS tools without blocking the voice loop."""
    await asyncio.to_thread(remember_sync, content, kind, meta)


# ---------------------------------------------------------------- reads
def recall_sync(limit: int = 8) -> list[dict]:
    if not _enabled():
        return []
    try:
        r = requests.get(
            f"{_url()}/api/memory",
            params={"limit": limit},
            headers=_headers(),
            timeout=_READ_TIMEOUT,
        )
        if r.status_code == 200:
            return r.json().get("events", []) or []
    except Exception:
        pass
    return []


def recall_text_sync(limit: int = 8) -> str:
    """Compact text block of ORELIUS's recent shared memory, for LUCIUS's context."""
    events = recall_sync(limit)
    if not events:
        return ""
    lines = [f"- [{e.get('actor')}/{e.get('kind')}] {e.get('content')}" for e in events]
    return "ORELIUS shared memory (recent activity):\n" + "\n".join(lines)


async def recall_text(limit: int = 8) -> str:
    return await asyncio.to_thread(recall_text_sync, limit)
