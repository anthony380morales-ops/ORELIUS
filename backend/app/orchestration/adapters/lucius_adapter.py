"""
ORELIUS → LUCIUS notification adapter (directive §5, §47).

LUCIUS is the owner's voice/realtime interface. The other direction — LUCIUS
commanding the ecosystem — is the control surface (`orchestration/control.py`).
This adapter is the OUTBOUND owner-alert path: ORELIUS pushes things the owner
must hear (a mission needs approval, a hot lead needs a human, a daily brief) into
the shared-memory bus, which already mirrors to LUCIUS when configured
(`shared_memory._mirror_to_lucius`). No new network route is opened (directive §41).

Owner alerts are internal comms, never a social/outbound action, so they are NEVER
gated by the social kill switches — the owner must always be reachable, even while
the whole social system is paused.
"""
from __future__ import annotations

from typing import Dict, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from ...utils.logger import logger
from ...core.shared_memory import shared_memory
from ..flags import flags, SocialMode

URGENCIES = ("low", "normal", "high", "critical")


class LuciusAdapter:
    async def capabilities(self) -> Dict:
        return {"executor": "lucius", "role": "owner_interface",
                "channels": ["notify", "approval_request", "handoff_alert", "brief"]}

    async def health(self, db: AsyncSession) -> Dict:
        """LUCIUS is reachable if a recent heartbeat/activity is mirrored into
        shared memory. Reported regardless of run mode (owner comms are internal)."""
        try:
            events = await shared_memory.recall(db, limit=25)
        except Exception as e:  # noqa: BLE001
            logger.debug(f"lucius health recall failed: {e}")
            events = []
        healthy = any(e.get("actor") == "LUCIUS" for e in events)
        return {"ok": healthy, "executor": "lucius",
                "state": "online" if healthy else "no_recent_heartbeat"}

    async def notify(self, db: AsyncSession, title: str, body: str = "",
                     urgency: str = "normal", kind: str = "lucius_notify",
                     meta: Optional[Dict] = None) -> Dict:
        """Push an owner alert onto the shared-memory bus (auto-mirrored to LUCIUS).

        Always writes — owner comms are never gated by the social kill switches."""
        urgency = urgency if urgency in URGENCIES else "normal"
        payload = {"urgency": urgency, **(meta or {})}
        content = f"{title.strip()}" + (f" — {body.strip()}" if body.strip() else "")
        try:
            event = await shared_memory.remember(
                db, content=content[:4000], kind=kind, actor="ORELIUS", meta=payload,
            )
            logger.info(f"LUCIUS alert queued #{event.get('id')} ({kind}, {urgency})")
            return {"ok": True, "event_id": event.get("id"), "urgency": urgency}
        except Exception as e:  # noqa: BLE001 - an alert must never crash the caller
            logger.error(f"LUCIUS notify failed: {e}")
            return {"ok": False, "error": str(e)}

    async def request_approval(self, db: AsyncSession, mission_id: str,
                               reason: str = "") -> Dict:
        return await self.notify(
            db, title=f"Approval needed for mission {mission_id}",
            body=reason, urgency="high", kind="approval_request",
            meta={"mission_id": mission_id},
        )

    async def announce_handoff(self, db: AsyncSession, mission_id: str,
                               detail: str = "", urgency: str = "high") -> Dict:
        return await self.notify(
            db, title=f"Human handoff: mission {mission_id}",
            body=detail, urgency=urgency, kind="handoff_alert",
            meta={"mission_id": mission_id},
        )


lucius_adapter = LuciusAdapter()
