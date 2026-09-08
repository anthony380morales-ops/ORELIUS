"""
Audience Intelligence agent (directive §6, registry id `audience_intelligence`).

Answers WHO to reach for each brand, and what they actually care about. For NXG it
REUSES real signal — the quiz "critical savings point" concerns on live leads
(`nxg_intel.recent_leads`) — so targeting reflects the concerns real prospects are
walking in with, not a guess. For IBC it uses the defined brand audience.

Brands never merge (directive §22). No private data is scraped or exposed — only
the aggregate concern themes already collected through the owner's own funnel.
Pure helpers are separated so the mapping unit-tests with no DB.
"""
from __future__ import annotations

from collections import Counter
from typing import Dict, List, Optional

from pydantic import BaseModel, Field

from sqlalchemy.ext.asyncio import AsyncSession

from ...utils.logger import logger
from ..mission import Brand, MissionPacket

# IBC's audience is defined by the brand, not a lead funnel.
_IBC_SEGMENT = "professionals_entrepreneurs"
_IBC_CONCERNS = ["cash flow control", "tax efficiency", "protect and grow wealth",
                 "being your own banker"]
_NXG_SEGMENT = "california_families"
_NXG_DEFAULT_CONCERNS = ["protecting the family", "affordable coverage", "living benefits"]


class AudienceInsight(BaseModel):
    brand: Brand
    segment: str
    top_concerns: List[str] = Field(default_factory=list)
    confidence: float = Field(0.0, ge=0.0, le=1.0)
    source: str = "brand_profile"     # "nxg_leads" when derived from real lead data
    sample_size: int = 0


def top_concerns_from_leads(leads: List[Dict], k: int = 3) -> List[str]:
    """Pure: rank the most common quiz concerns across recent leads."""
    concerns = [str(l.get("concern")).strip() for l in leads
                if str(l.get("concern") or "").strip()
                and str(l.get("concern")).strip().lower() not in ("n/a", "none")]
    if not concerns:
        return []
    return [c for c, _ in Counter(concerns).most_common(k)]


def apply_audience(mission: MissionPacket, insight: AudienceInsight) -> MissionPacket:
    """Pure: sharpen a mission's audience with the insight's dominant concern."""
    if insight.top_concerns:
        mission.audience.segment = insight.top_concerns[0]
    # keep the higher-confidence signal
    mission.audience.confidence = max(mission.audience.confidence, insight.confidence)
    return mission


class AudienceIntelligenceAgent:
    async def profile(self, db: AsyncSession, brand: Brand) -> AudienceInsight:
        """Build an audience insight for a brand. NXG reuses live lead concerns;
        never raises — falls back to the brand profile when data is unavailable."""
        if brand == Brand.IBC:
            return AudienceInsight(brand=brand, segment=_IBC_SEGMENT,
                                   top_concerns=_IBC_CONCERNS, confidence=0.6,
                                   source="brand_profile")
        # NXG — try real lead concerns first.
        try:
            from ...core.nxg_intel import nxg_intel
            res = await nxg_intel.recent_leads(db, limit=25)
        except Exception as e:  # noqa: BLE001 - audience must never crash a scan
            logger.warning(f"audience profile (NXG leads) failed: {e}")
            res = {"ok": False}

        if res.get("ok"):
            leads = res.get("leads") or []
            concerns = top_concerns_from_leads(leads)
            if concerns:
                n = len(leads)
                return AudienceInsight(
                    brand=brand, segment=_NXG_SEGMENT, top_concerns=concerns,
                    confidence=round(min(0.9, 0.4 + 0.03 * n), 3),
                    source="nxg_leads", sample_size=n,
                )
        return AudienceInsight(brand=brand, segment=_NXG_SEGMENT,
                               top_concerns=_NXG_DEFAULT_CONCERNS, confidence=0.45,
                               source="brand_profile")


audience_intelligence = AudienceIntelligenceAgent()
