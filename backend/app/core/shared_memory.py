"""
O.R.E.L.I.U.S. <-> LUCIUS Shared Memory (durable hub)
------------------------------------------------------
ORELIUS is the shared-memory hub. Every event either system records is a row in
the Postgres `shared_memory` table:
  * ORELIUS writes its exchanges/actions directly (it owns the database).
  * LUCIUS reads and writes via the secured /api/memory endpoint.

ORELIUS injects the most recent shared events into its persona each turn, so
"anything LUCIUS does, ORELIUS knows, and vice-versa." An optional best-effort
push to a LUCIUS webhook is supported when LUCIUS_API_URL is configured.
"""
from __future__ import annotations

import time
from typing import Dict, List, Optional

import httpx
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..models.shared_memory import SharedMemoryEvent
from ..utils.logger import logger


class SharedMemory:
    """Durable, database-backed shared memory between ORELIUS and LUCIUS."""

    def __init__(self):
        self.max_items = settings.shared_memory_max_items

    async def remember(
        self,
        db: AsyncSession,
        content: str,
        kind: str = "note",
        actor: str = "ORELIUS",
        meta: Optional[Dict] = None,
    ) -> Dict:
        """Append an event to the shared log (and optionally push to LUCIUS)."""
        event = SharedMemoryEvent(
            ts=time.time(),
            actor=(actor or "ORELIUS")[:64],
            kind=(kind or "note")[:64],
            content=content.strip()[:4000],
            meta=meta or {},
        )
        db.add(event)
        await db.flush()  # assign id

        # keep only the newest max_items rows
        keep_ids = select(SharedMemoryEvent.id).order_by(
            SharedMemoryEvent.ts.desc()
        ).limit(self.max_items)
        await db.execute(delete(SharedMemoryEvent).where(SharedMemoryEvent.id.notin_(keep_ids)))

        result = event.as_dict()
        await self._mirror_to_lucius(result)
        return result

    async def recall(
        self,
        db: AsyncSession,
        limit: int = 6,
        actor: Optional[str] = None,
    ) -> List[Dict]:
        """Return the most recent shared events, newest last."""
        q = select(SharedMemoryEvent)
        if actor:
            q = q.where(SharedMemoryEvent.actor == actor)
        q = q.order_by(SharedMemoryEvent.ts.desc()).limit(max(1, min(limit, 100)))
        rows = (await db.execute(q)).scalars().all()
        return [r.as_dict() for r in reversed(rows)]

    async def build_context(self, db: AsyncSession, limit: Optional[int] = None) -> str:
        """Compact text block of recent shared memory to inject into the persona."""
        limit = limit or settings.shared_memory_context_items
        try:
            events = await self.recall(db, limit=limit)
        except Exception as e:  # noqa: BLE001 - never block a reply on memory
            logger.debug(f"shared memory recall skipped: {e}")
            return ""
        if not events:
            return ""
        lines = [f"- [{e['actor']}/{e['kind']}] {e['content']}" for e in events]
        return (
            "\n\n# SHARED MEMORY (LUCIUS <-> ORELIUS)\n"
            "Recent activity from you and your companion LUCIUS. Treat it as shared "
            "knowledge:\n" + "\n".join(lines)
        )

    async def _mirror_to_lucius(self, event: Dict) -> None:
        """Optional best-effort push to a LUCIUS webhook (no-op unless configured)."""
        if not settings.lucius_api_url:
            return
        try:
            headers = {"Content-Type": "application/json"}
            if settings.lucius_api_key:
                headers["Authorization"] = f"Bearer {settings.lucius_api_key}"
            if settings.lucius_shared_secret:
                headers["X-Shared-Secret"] = settings.lucius_shared_secret
            async with httpx.AsyncClient(timeout=3.0) as client:
                await client.post(
                    settings.lucius_api_url.rstrip("/") + "/memory",
                    json=event,
                    headers=headers,
                )
        except Exception as e:  # noqa: BLE001 - mirror must never break chat
            logger.debug(f"LUCIUS mirror skipped ({e})")


# Global shared-memory instance
shared_memory = SharedMemory()
