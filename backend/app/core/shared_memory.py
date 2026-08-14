"""
O.R.E.L.I.U.S. <-> LUCIUS Shared Memory
------------------------------------------------
ORELIUS and LUCIUS are companions with a shared brain: anything LUCIUS does,
ORELIUS knows, and vice-versa.

Simplest reliable method (chosen per the Master's instruction):
  * A single shared JSON event log both systems read from and append to.
  * LUCIUS points at the same file (or the same path on a shared volume) and
    writes events with actor="LUCIUS"; ORELIUS writes actor="ORELIUS".
  * Optional best-effort HTTP mirror to a LUCIUS endpoint if one is configured,
    so the two stay in sync even across machines — but the file is the source of
    truth and everything works with zero extra infrastructure.

Each memory event is a small record:
  { "ts": <epoch>, "actor": "ORELIUS"|"LUCIUS", "kind": "...", "content": "...", "meta": {...} }
"""
from __future__ import annotations

import json
import os
import threading
import time
from typing import Dict, List, Optional

import httpx

from ..config import settings
from ..utils.logger import logger


class SharedMemory:
    """File-backed shared event log with an optional LUCIUS HTTP mirror."""

    def __init__(self):
        self.path = settings.shared_memory_path
        self.max_items = settings.shared_memory_max_items
        self._lock = threading.Lock()
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        if not os.path.exists(self.path):
            self._write_all([])

    # --- low-level file io ----------------------------------------------
    def _read_all(self) -> List[Dict]:
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data if isinstance(data, list) else data.get("events", [])
        except (FileNotFoundError, json.JSONDecodeError):
            return []

    def _write_all(self, events: List[Dict]) -> None:
        try:
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump(events[-self.max_items :], f, indent=2)
        except OSError as e:
            logger.warning(f"SharedMemory write failed: {e}")

    # --- public api ------------------------------------------------------
    def remember(
        self,
        content: str,
        kind: str = "note",
        actor: str = "ORELIUS",
        meta: Optional[Dict] = None,
    ) -> Dict:
        """Append an event to the shared log (and mirror to LUCIUS if configured)."""
        event = {
            "ts": time.time(),
            "actor": actor,
            "kind": kind,
            "content": content.strip()[:2000],
            "meta": meta or {},
        }
        with self._lock:
            events = self._read_all()
            events.append(event)
            self._write_all(events)
        # best-effort remote mirror; never blocks the conversation on failure
        self._mirror_to_lucius(event)
        return event

    def recall(self, limit: int = 6, actor: Optional[str] = None) -> List[Dict]:
        """Return the most recent shared events, newest last."""
        with self._lock:
            events = self._read_all()
        if actor:
            events = [e for e in events if e.get("actor") == actor]
        return events[-limit:]

    def build_context(self, limit: Optional[int] = None) -> str:
        """Compact text block of recent shared memory to inject into the persona.

        Kept intentionally short (a handful of items) so it costs almost no tokens.
        """
        limit = limit or settings.shared_memory_context_items
        events = self.recall(limit=limit)
        if not events:
            return ""
        lines = []
        for e in events:
            actor = e.get("actor", "?")
            kind = e.get("kind", "note")
            content = e.get("content", "")
            lines.append(f"- [{actor}/{kind}] {content}")
        return (
            "\n\n# SHARED MEMORY (LUCIUS <-> ORELIUS)\n"
            "Recent activity from you and your companion LUCIUS. Treat it as shared knowledge:\n"
            + "\n".join(lines)
        )

    def _mirror_to_lucius(self, event: Dict) -> None:
        if not settings.lucius_api_url:
            return
        try:
            headers = {"Content-Type": "application/json"}
            if settings.lucius_api_key:
                headers["Authorization"] = f"Bearer {settings.lucius_api_key}"
            if settings.lucius_shared_secret:
                headers["X-Shared-Secret"] = settings.lucius_shared_secret
            # short timeout, fire-and-forget; failures are logged, never raised
            with httpx.Client(timeout=3.0) as client:
                client.post(
                    settings.lucius_api_url.rstrip("/") + "/memory",
                    json=event,
                    headers=headers,
                )
        except Exception as e:  # noqa: BLE001 - mirror must never break chat
            logger.debug(f"LUCIUS mirror skipped ({e})")

    def pull_from_lucius(self, limit: int = 20) -> int:
        """Optionally pull recent LUCIUS events into the shared log (two-way sync).

        Returns the number of new events ingested. No-op if LUCIUS isn't configured.
        """
        if not settings.lucius_api_url:
            return 0
        try:
            headers = {}
            if settings.lucius_api_key:
                headers["Authorization"] = f"Bearer {settings.lucius_api_key}"
            with httpx.Client(timeout=3.0) as client:
                resp = client.get(
                    settings.lucius_api_url.rstrip("/") + "/memory",
                    params={"limit": limit},
                    headers=headers,
                )
                resp.raise_for_status()
                remote = resp.json()
            remote_events = remote if isinstance(remote, list) else remote.get("events", [])
            with self._lock:
                events = self._read_all()
                known = {(e.get("ts"), e.get("content")) for e in events}
                new = [
                    e for e in remote_events if (e.get("ts"), e.get("content")) not in known
                ]
                if new:
                    events.extend(new)
                    events.sort(key=lambda e: e.get("ts", 0))
                    self._write_all(events)
            return len(new)
        except Exception as e:  # noqa: BLE001
            logger.debug(f"LUCIUS pull skipped ({e})")
            return 0


# Global shared-memory instance
shared_memory = SharedMemory()
