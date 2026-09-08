"""
ORELIUS → (ATHENA) → HIGGBOT creative adapter (directive §13, §41 no duplication).

HIGGBOT is the owner's own provider-agnostic design engine (NOT Higgsfield the
vendor). It exposes `design.*` MCP tools and is driven by ATHENA, never by ORELIUS
directly. So this adapter does NOT open a network route to HIGGBOT: it builds a
HIGGBOT-shaped creative job from a CreativeBrief and, in live mode, hands it to
ATHENA's existing `design_request` bridge — ATHENA then drives HIGGBOT and reports
the asset back through shared memory (creative path: ORELIUS → ATHENA → HIGGBOT →
asset → ATHENA QA → publish).

Simulation-first (directive §44): in simulation / dry-run, or whenever HIGGBOT_PAUSE
(or a broader kill switch) gates outbound action, the adapter returns the exact job
it *would* dispatch plus a $0 placeholder asset — mirroring HIGGBOT's own built-in
simulation mode — without writing anything real.
"""
from __future__ import annotations

from typing import Dict, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from ...utils.logger import logger
from ...core import athena as athena_core
from ...core.shared_memory import shared_memory
from ..mission import MissionPacket
from ..creative import CreativeBrief, build_brief, to_higgbot_job
from ..flags import flags, SocialMode

HIGGBOT_CAPABILITIES = [
    "design.image",
    "design.reel",
    "design.video",
    "design.carousel",
    "design.story",
    "design.logo",
    "design.poster",
    "design.thumbnail",
]


def _placeholder_asset(job: Dict) -> Dict:
    """A $0 stand-in asset, matching HIGGBOT's own simulation output shape."""
    return {
        "provider": "simulation",
        "asset_kind": job.get("asset_kind"),
        "count": job.get("count", 1),
        "aspect_ratio": job.get("aspect_ratio"),
        "cost_usd": 0.0,
        "uri": f"sim://higgbot/{job.get('asset_kind', 'asset')}/placeholder",
        "status": "placeholder",
    }


class HiggbotAdapter:
    async def capabilities(self) -> Dict:
        return {"executor": "higgbot", "via": "athena", "capabilities": HIGGBOT_CAPABILITIES}

    async def health(self, db: AsyncSession) -> Dict:
        """HIGGBOT runs behind ATHENA; report simulated unless live + a heartbeat
        is visible in shared memory."""
        mode = await flags.mode(db)
        paused = await flags.get(db, "HIGGBOT_PAUSE")
        if mode != SocialMode.LIVE:
            return {"ok": True, "executor": "higgbot", "via": "athena",
                    "mode": mode.value, "paused": paused, "state": "simulated"}
        try:
            events = await shared_memory.recall(db, limit=25)
        except Exception as e:  # noqa: BLE001
            logger.debug(f"higgbot health recall failed: {e}")
            events = []
        healthy = any(
            (e.get("kind") in ("design_result", "higgbot_activity"))
            or (e.get("actor") in ("HIGGBOT", "ATHENA"))
            for e in events
        )
        return {"ok": healthy and not paused, "executor": "higgbot", "via": "athena",
                "mode": mode.value, "paused": paused,
                "state": "online" if healthy else "no_recent_heartbeat"}

    def translate(self, brief: CreativeBrief) -> Dict:
        """CreativeBrief → HIGGBOT-shaped design job (routed via ATHENA)."""
        return to_higgbot_job(brief)

    async def submit_brief(self, db: AsyncSession, brief: CreativeBrief) -> Dict:
        """Dispatch a creative brief (live) or return the proposed job + placeholder."""
        job = self.translate(brief)
        mode = await flags.mode(db)
        paused = await flags.get(db, "HIGGBOT_PAUSE")
        outbound_ok = await flags.outbound_allowed(db, brief.brand.value)

        # Simulation / dry-run / paused / gated → never dispatch for real.
        if mode != SocialMode.LIVE or paused or not outbound_ok:
            reason = ("higgbot_paused" if paused else
                      "simulation/dry-run or outbound gated")
            return {
                "ok": True, "simulated": True, "mode": mode.value,
                "mission_id": brief.mission_id,
                "would_dispatch": job,
                "placeholder_asset": _placeholder_asset(job),
                "note": f"{reason} — nothing dispatched",
            }

        # Live: hand the design job to ATHENA's bridge; ATHENA drives HIGGBOT.
        event = await athena_core.enqueue_design_request(
            db, request=job["request"], kind="design", task=job.get("task"),
        )
        return {"ok": True, "simulated": False, "mode": mode.value,
                "mission_id": brief.mission_id,
                "dispatched": {"event_id": event.get("id"), **job}}

    async def submit_mission(self, db: AsyncSession, packet: MissionPacket) -> Dict:
        """Mission-level entry: build the brief from the packet, then submit it.

        Enforces the same compliance gate as every executor path — a creative
        mission may only be produced once compliance has cleared it."""
        if not packet.is_ready_for_executor():
            return {"ok": False, "reason": "compliance_not_approved",
                    "mission_id": packet.mission_id}
        brief = build_brief(packet)
        result = await self.submit_brief(db, brief)
        result["brief"] = brief.model_dump(mode="json")
        return result


higgbot_adapter = HiggbotAdapter()
