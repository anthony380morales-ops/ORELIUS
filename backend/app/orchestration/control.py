"""
Ecosystem control surface (directive §5, §46, §47) — what LUCIUS drives by voice.

LUCIUS is the owner's interface, NOT the orchestration brain (Phase 0). It observes
and commands the ecosystem through this thin surface: one consolidated status
snapshot, voice-friendly pause/resume by scope, the compliance approval queue, and
the human-handoff queue. Every real decision still lives in ORELIUS's mission
system; this layer only reads it and flips durable flags.

Owner-facing operations here are internal (never a social/outbound action), so they
are never gated by the social kill switches — the owner must always be able to see
status and stop the system.
"""
from __future__ import annotations

from typing import Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..utils.logger import logger
from .mission import MissionStatus, Objective
from .mission_queue import mission_queue, ACTIVE_STATES, TERMINAL_STATES
from .flags import flags, PAUSE_FLAGS
from .adapters import athena_adapter, higgbot_adapter

# Voice-friendly scope words → the durable kill switch they map to.
SCOPE_TO_FLAG: Dict[str, str] = {
    "all": "SYSTEM_PAUSE", "system": "SYSTEM_PAUSE", "everything": "SYSTEM_PAUSE",
    "messaging": "MESSAGING_PAUSE", "messages": "MESSAGING_PAUSE", "dms": "MESSAGING_PAUSE",
    "publishing": "PUBLISHING_PAUSE", "posts": "PUBLISHING_PAUSE", "posting": "PUBLISHING_PAUSE",
    "outbound": "OUTBOUND_PAUSE",
    "nxg": "NXG_PAUSE",
    "ibc": "IBC_PAUSE",
    "higgbot": "HIGGBOT_PAUSE", "creative": "HIGGBOT_PAUSE", "design": "HIGGBOT_PAUSE",
    "athena": "ATHENA_PAUSE", "social": "ATHENA_PAUSE",
}


def resolve_scope(scope: str) -> Optional[str]:
    """Map a spoken scope word to a kill-switch name (or None if unknown)."""
    return SCOPE_TO_FLAG.get((scope or "").strip().lower())


def _mission_brief(row) -> Dict:
    return {
        "mission_id": row.mission_id, "status": row.status,
        "brand": row.brand, "platform": row.platform, "objective": row.objective,
        "priority": row.priority, "error": row.error,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


class ControlSurface:
    async def status(self, db: AsyncSession) -> Dict:
        """One consolidated snapshot for LUCIUS to read back to the owner."""
        snap = await flags.snapshot(db)              # mode + all kill switches
        stats = await mission_queue.stats(db)
        approvals = await self.pending_approvals(db)
        handoffs = await self.pending_handoffs(db)
        return {
            "mode": snap.get("mode"),
            "paused": {f: snap.get(f) for f in PAUSE_FLAGS},
            "any_paused": any(snap.get(f) for f in PAUSE_FLAGS),
            "queue": stats,
            "pending_approvals": len(approvals),
            "pending_handoffs": len(handoffs),
            "executors": {
                "athena": await athena_adapter.health(db),
                "higgbot": await higgbot_adapter.health(db),
            },
        }

    async def pause(self, db: AsyncSession, scope: str, actor: str = "LUCIUS") -> Dict:
        flag = resolve_scope(scope)
        if not flag:
            return {"ok": False, "reason": "unknown_scope", "scope": scope}
        await flags.set(db, flag, True)
        logger.info(f"{actor} paused scope '{scope}' -> {flag}")
        return {"ok": True, "scope": scope, "flag": flag, "paused": True,
                "snapshot": await flags.snapshot(db)}

    async def resume(self, db: AsyncSession, scope: str, actor: str = "LUCIUS") -> Dict:
        flag = resolve_scope(scope)
        if not flag:
            return {"ok": False, "reason": "unknown_scope", "scope": scope}
        await flags.set(db, flag, False)
        logger.info(f"{actor} resumed scope '{scope}' -> {flag}")
        return {"ok": True, "scope": scope, "flag": flag, "paused": False,
                "snapshot": await flags.snapshot(db)}

    # ------------------------------------------------------------- approvals
    async def pending_approvals(self, db: AsyncSession) -> List[Dict]:
        """Missions held by the compliance gate, awaiting owner approval."""
        from ..models.orchestration import Mission
        rows = (await db.execute(
            select(Mission).where(Mission.status == MissionStatus.BLOCKED.value)
            .order_by(Mission.created_at.asc())
        )).scalars().all()
        return [_mission_brief(r) for r in rows]

    async def approve(self, db: AsyncSession, mission_id: str) -> bool:
        return await mission_queue.approve(db, mission_id)

    # ------------------------------------------------------------- handoffs
    async def pending_handoffs(self, db: AsyncSession) -> List[Dict]:
        """Work needing a human: escalated missions + explicit human-handoff missions
        that have not yet reached a terminal state."""
        from ..models.orchestration import Mission
        rows = (await db.execute(
            select(Mission)
            .where(
                (Mission.status == MissionStatus.ESCALATED.value)
                | (
                    (Mission.objective == Objective.HUMAN_HANDOFF.value)
                    & (Mission.status.in_(list(ACTIVE_STATES)))
                )
            )
            .order_by(Mission.created_at.asc())
        )).scalars().all()
        return [_mission_brief(r) for r in rows]

    async def resolve_handoff(self, db: AsyncSession, mission_id: str,
                              note: str = "") -> bool:
        """Owner took the handoff → close it as completed with a note."""
        row = await mission_queue.get(db, mission_id)
        if not row or row.status in TERMINAL_STATES:
            return False
        await mission_queue.complete(db, mission_id,
                                     {"handoff": "resolved_by_human", "note": note[:512]})
        return True


control_surface = ControlSurface()
