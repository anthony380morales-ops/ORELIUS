"""
Compliance gate (directive §31, §62) — the mandatory checkpoint between a proposed
mission and an executor. Wraps the compliance/risk agent with the durable queue so
a verdict actually moves the mission:

  APPROVED    → the held mission is released to QUEUED, its packet stamped approved
  NEEDS_HUMAN → the mission is ESCALATED (lands in the human handoff queue)
  BLOCKED     → the mission stays BLOCKED, with the reasons recorded

Nothing here dispatches; it only decides whether a mission MAY proceed. The verdict
is recorded on the mission row for postmortem-grade provenance.
"""
from __future__ import annotations

from typing import Dict, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from ..utils.logger import logger
from .mission import validate_mission, ComplianceStatus
from .mission_queue import mission_queue
from .agents.compliance_risk import compliance_risk, ComplianceVerdict


class ComplianceEngine:
    async def review_mission_row(self, db: AsyncSession, mission_id: str) -> Dict:
        """Review a stored mission and move it per the verdict."""
        row = await mission_queue.get(db, mission_id)
        if not row:
            return {"ok": False, "reason": "mission_not_found"}

        try:
            packet = validate_mission(row.packet or {})
        except Exception as e:  # noqa: BLE001 - an unparseable packet is not approvable
            logger.warning(f"compliance: unparseable packet {mission_id}: {e}")
            verdict = ComplianceVerdict(status=ComplianceStatus.NEEDS_HUMAN,
                                        reasons=[f"unparseable_packet:{e}"])
            await mission_queue.escalate(db, mission_id, reason="unparseable_packet")
            return {"ok": True, "verdict": verdict.model_dump(mode="json"),
                    "moved_to": "ESCALATED"}

        verdict = compliance_risk.review_mission(packet)
        # Record the verdict on the row for provenance.
        result = dict(row.result or {})
        result["compliance"] = verdict.model_dump(mode="json")
        row.result = result

        if verdict.status == ComplianceStatus.APPROVED:
            # stamp the packet and release the held mission
            packet.compliance.status = ComplianceStatus.APPROVED
            packet.compliance.review_id = verdict.review_id
            row.packet = packet.model_dump(mode="json")
            moved = "QUEUED" if await mission_queue.approve(db, mission_id) else row.status
        elif verdict.status == ComplianceStatus.NEEDS_HUMAN:
            await mission_queue.escalate(db, mission_id, reason=";".join(verdict.reasons))
            moved = "ESCALATED"
        else:  # BLOCKED
            row.error = ("; ".join(verdict.reasons))[:512]
            moved = row.status  # stays BLOCKED
        await db.flush()
        logger.info(f"compliance {mission_id}: {verdict.status.value} -> {moved}")
        return {"ok": True, "verdict": verdict.model_dump(mode="json"), "moved_to": moved}

    def review_packet(self, packet_dict: Dict) -> Dict:
        """Stateless review of an ad-hoc packet dict (no persistence)."""
        packet = validate_mission(packet_dict)
        return compliance_risk.review_mission(packet).model_dump(mode="json")

    def review_message(self, text: str) -> Dict:
        """Stateless review of an autonomous message."""
        return compliance_risk.review_message(text).model_dump(mode="json")


compliance_engine = ComplianceEngine()
