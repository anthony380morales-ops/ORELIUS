"""
ORELIUS → ATHENA adapter (directive §13).

ATHENA is the social-operations executor. It runs on the owner's machine
(localhost), so cloud-hosted ORELIUS reaches it through the existing shared-memory
bridge (a `design_request` event a local daemon drives into ATHENA's job API) —
this adapter REUSES that path (directive §41: no duplication), it does not open a
new network route to ATHENA.

Simulation-first (directive §44): in simulation / dry-run, or whenever a kill switch
gates outbound action, the adapter computes and returns the exact job it *would*
dispatch without writing anything real. Only `live` mode with outbound allowed
performs a real dispatch.
"""
from __future__ import annotations

from typing import Dict, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from ...utils.logger import logger
from ...core import athena as athena_core
from ...core.shared_memory import shared_memory
from ..mission import MissionPacket, Objective, Platform
from ..flags import flags, SocialMode

ATHENA_CAPABILITIES = [
    "instagram_post",   # research + create + publish/schedule a real IG post
    "design",           # generate a design asset (routes to higgbot)
    "website",          # build a landing page / site
    "research",         # trends-only research
    "publish",
    "schedule",
    "social_analytics",
]


def translate(packet: MissionPacket) -> Dict:
    """Map a MissionPacket to an ATHENA job {kind, action, request} or kind=None.

    kind=None means ATHENA has no direct endpoint for this objective yet (e.g. live
    conversation/engagement), so it becomes a queued opportunity for the messaging
    phase rather than a forced/bypassed action.
    """
    obj = packet.objective
    if obj == Objective.CONTENT_PUBLISH:
        kind, action = "instagram_post", "once"
    elif obj == Objective.RESEARCH:
        kind, action = "instagram_post", "research"
    elif packet.creative and packet.creative.required:
        kind, action = "design", None
    elif packet.platform == Platform.INTERNAL:
        kind, action = None, None
    else:
        kind, action = None, None   # engagement / conversation → messaging phase

    topic = packet.topic.title if packet.topic else ""
    cta = packet.cta.destination if (packet.cta and packet.cta.destination) else ""
    request = (
        f"[{packet.brand.value} · {packet.platform.value}] objective="
        f"{obj.value}; audience={packet.audience.type}"
        + (f"/{packet.audience.segment}" if packet.audience.segment else "")
        + (f"; topic={topic}" if topic else "")
        + (f"; cta={cta}" if cta else "")
    )
    if packet.brief:
        request += f"\n\nBrief: {packet.brief}"
    return {"kind": kind, "action": action, "request": request}


class AthenaAdapter:
    async def capabilities(self) -> Dict:
        return {"executor": "athena", "capabilities": ATHENA_CAPABILITIES}

    async def health(self, db: AsyncSession) -> Dict:
        """ATHENA health via its shared-memory heartbeat (it's localhost-only)."""
        mode = await flags.mode(db)
        if mode != SocialMode.LIVE:
            return {"ok": True, "executor": "athena", "mode": mode.value,
                    "state": "simulated"}
        # Live: look for a recent ATHENA heartbeat mirrored into shared memory.
        try:
            events = await shared_memory.recall(db, limit=25)
        except Exception as e:  # noqa: BLE001
            logger.debug(f"athena health recall failed: {e}")
            events = []
        healthy = any(
            (e.get("kind") == "athena_activity") or (e.get("actor") == "ATHENA")
            for e in events
        )
        return {"ok": healthy, "executor": "athena", "mode": mode.value,
                "state": "online" if healthy else "no_recent_heartbeat"}

    async def submit_mission(self, db: AsyncSession, packet: MissionPacket) -> Dict:
        """Translate + dispatch (live) or return the proposed job (simulation/dry)."""
        if not packet.is_ready_for_executor():
            return {"ok": False, "reason": "compliance_not_approved",
                    "mission_id": packet.mission_id}

        job = translate(packet)
        mode = await flags.mode(db)
        outbound_ok = await flags.outbound_allowed(db, packet.brand.value)

        # Simulation / dry-run / gated → never dispatch for real.
        if mode != SocialMode.LIVE or not outbound_ok:
            return {
                "ok": True, "simulated": True, "mode": mode.value,
                "mission_id": packet.mission_id,
                "would_dispatch": job,
                "note": "simulation/dry-run or outbound gated — nothing dispatched",
            }

        # Live: ATHENA has a direct endpoint for this kind → dispatch via the bridge.
        if job["kind"]:
            event = await athena_core.enqueue_design_request(
                db, request=job["request"], kind=job["kind"], action=job["action"],
            )
            return {"ok": True, "simulated": False, "mode": mode.value,
                    "mission_id": packet.mission_id,
                    "dispatched": {"event_id": event.get("id"), **job}}

        # Live but no direct ATHENA endpoint → record as an opportunity, don't force.
        return {"ok": True, "simulated": False, "mode": mode.value,
                "mission_id": packet.mission_id, "dispatched": None,
                "note": "no direct ATHENA endpoint for this objective; queued as "
                        "opportunity for the messaging phase"}


athena_adapter = AthenaAdapter()
