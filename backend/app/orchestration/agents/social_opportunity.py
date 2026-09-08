"""
Social Opportunity agent (directive §6, registry id `social_opportunity`).

Answers WHERE the meaningful openings are for each brand — but strictly within the
rules (directive §17 meaningful touchpoints, §31/§62 compliance-as-code): no
scraping, no fake engagement, no private data, official APIs only.

Simulation-first (directive §44): with no connected platform API (the default),
this agent does NOT invent real posts, threads, or people to target. It returns a
compliant SLATE of permitted touchpoint TYPES, sized against the brand's touchpoint
baseline, each flagged `requires_live_api` so the allocation engine (Phase 10) and
the live activation (Phase 15) know real discovery is still gated. Deterministic
and DB-free, so it unit-tests cleanly.
"""
from __future__ import annotations

from typing import List

from pydantic import BaseModel, Field

from ...config import settings
from ..mission import Brand, Platform, TouchpointAction

_BRAND_PLATFORM = {Brand.NXG: Platform.FACEBOOK, Brand.IBC: Platform.INSTAGRAM}

# Permitted mix of meaningful touchpoint types and their share of the baseline.
# Every one is a legitimate, consented, or public-and-invited interaction — never
# unsolicited mass DMs or manufactured engagement.
_OPPORTUNITY_MIX = [
    (TouchpointAction.CONTENT_DISTRIBUTION, 0.30, "Publish + distribute brand content to owned audience"),
    (TouchpointAction.MEANINGFUL_COMMENT, 0.25, "Add genuine value on relevant public conversations"),
    (TouchpointAction.REPLY, 0.15, "Reply to comments and mentions on our own content"),
    (TouchpointAction.STORY_INTERACTION, 0.15, "Respond to story replies and reactions"),
    (TouchpointAction.COMMUNITY_PARTICIPATION, 0.10, "Participate in relevant communities we belong to"),
    (TouchpointAction.COMMENT_TO_DM, 0.05, "Move an invited, consented conversation to DM"),
]


class SocialOpportunity(BaseModel):
    brand: Brand
    platform: Platform
    action: TouchpointAction
    rationale: str
    est_touchpoints: int = Field(0, ge=0)
    requires_live_api: bool = True     # real targets need a connected platform API


def _baseline_for(brand: Brand) -> int:
    if brand == Brand.IBC:
        return int(getattr(settings, "ibc_touchpoint_baseline", 600))
    return int(getattr(settings, "nxg_touchpoint_baseline", 430))


def opportunity_slate(brand: Brand) -> List[SocialOpportunity]:
    """Pure: the compliant, baseline-sized slate of touchpoint types for a brand."""
    platform = _BRAND_PLATFORM.get(brand, Platform.INSTAGRAM)
    baseline = _baseline_for(brand)
    return [
        SocialOpportunity(
            brand=brand, platform=platform, action=action,
            rationale=rationale, est_touchpoints=int(round(baseline * share)),
        )
        for action, share, rationale in _OPPORTUNITY_MIX
    ]


class SocialOpportunityAgent:
    async def discover(self, db=None, brand: Brand = Brand.NXG) -> List[SocialOpportunity]:
        """Return the permitted opportunity slate for a brand.

        Simulation default: structured opportunity TYPES only — never scraped or
        fabricated live targets. Live target discovery is gated to connected
        platform APIs (Phase 15)."""
        return opportunity_slate(brand)


social_opportunity = SocialOpportunityAgent()
