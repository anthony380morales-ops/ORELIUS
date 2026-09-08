"""
Intelligence planner (directive §8) — turns specialist intelligence into typed,
validated MissionPackets. This is the bridge from Phase 6 intelligence to the
Phase 2 queue and the Phase 3/4 executors.

Simulation-first and human-in-the-loop: a scan PROPOSES content missions but does
not act. Every proposed mission starts with compliance PENDING, so even if enqueued
it is held (BLOCKED) until the compliance/owner gate clears it — nothing reaches an
executor off the back of an automated scan alone.
"""
from __future__ import annotations

from typing import Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from ..utils.logger import logger
from .mission import (
    MissionPacket, Brand, Platform, Objective, Priority,
    Topic, Creative, Compliance, ComplianceStatus, Audience,
)
from .agents import economic_intelligence, financial_impact
from .agents.economic_intelligence import EconomicSignal
from .agents.financial_impact import ImpactAngle
from .mission_queue import mission_queue

# Each brand's home platform (baselines from config; directive §22 keeps them apart).
_BRAND_PLATFORM = {Brand.NXG: Platform.FACEBOOK, Brand.IBC: Platform.INSTAGRAM}


def _priority_for(score: float) -> Priority:
    if score >= 0.8:
        return Priority.HIGH
    if score >= 0.55:
        return Priority.MEDIUM
    return Priority.LOW


def build_content_missions(
    signals: List[EconomicSignal],
    angles: List[ImpactAngle],
    brand: Brand,
    platform: Optional[Platform] = None,
) -> List[MissionPacket]:
    """Pure: turn ranked impact angles into content MissionPackets (compliance
    PENDING → held until approved). Signals are matched to angles by id."""
    platform = platform or _BRAND_PLATFORM.get(brand, Platform.INSTAGRAM)
    by_id = {s.id: s for s in signals}
    missions: List[MissionPacket] = []
    for angle in angles:
        sig = by_id.get(angle.signal_id)
        if not sig:
            continue
        missions.append(MissionPacket(
            brand=brand,
            platform=platform,
            objective=Objective.CONTENT_PUBLISH,
            audience=Audience(type=angle.audience_hint, confidence=angle.opportunity_score),
            topic=Topic(title=sig.headline, source_ids=[sig.id], confidence=sig.confidence),
            creative=Creative(required=True),
            compliance=Compliance(status=ComplianceStatus.PENDING),
            priority=_priority_for(angle.opportunity_score),
            brief={"angle": angle.angle, "framing": sig.framing,
                   "opportunity_score": angle.opportunity_score},
        ))
    return missions


class IntelligencePlanner:
    async def scan(self, db: AsyncSession, brand: Brand,
                   platform: Optional[Platform] = None,
                   enqueue: bool = False, limit: int = 5) -> Dict:
        """Run economic-intelligence → financial-impact → content missions.

        Returns the signals, ranked angles, and proposed missions. With
        enqueue=True the proposals are queued (still BLOCKED on compliance)."""
        signals = await economic_intelligence.gather(db)
        angles = financial_impact.assess(signals, brand)[:max(1, limit)]
        missions = build_content_missions(signals, angles, brand, platform)

        enqueued: List[str] = []
        if enqueue:
            for mp in missions:
                try:
                    row = await mission_queue.enqueue(db, mp, executor="athena")
                    enqueued.append(row.mission_id)
                except Exception as e:  # noqa: BLE001
                    logger.warning(f"planner enqueue failed for {mp.mission_id}: {e}")

        return {
            "brand": brand.value,
            "signals": [s.model_dump(mode="json") for s in signals],
            "angles": [a.model_dump(mode="json") for a in angles],
            "missions": [m.model_dump(mode="json") for m in missions],
            "enqueued": enqueued,
            "note": ("proposals queued (held on compliance)" if enqueue
                     else "proposals only — nothing queued"),
        }


intelligence_planner = IntelligencePlanner()
