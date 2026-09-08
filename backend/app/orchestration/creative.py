"""
Creative contract — the typed brief ORELIUS hands down the creative path
(directive §13 typed contracts, §22 brand separation, §41 no duplication).

Creative path:  ORELIUS → content mission → ATHENA → HIGGBOT → asset → ATHENA QA → publish

ORELIUS does not talk to HIGGBOT directly. When a MissionPacket needs an asset
(`creative.required`), ORELIUS synthesizes a `CreativeBrief` — a small, typed,
brand-scoped spec — which the HIGGBOT adapter turns into a `design.*` job that
travels through ATHENA's existing design bridge. HIGGBOT's own provider-agnostic
router then picks the cheapest capable provider, escalating only within the
tier's budget cap.

This module is pure (Pydantic + config only): no DB, no network, no model calls,
so brief-building and the tier→budget mapping unit-test on their own.
"""
from __future__ import annotations

from enum import Enum
from typing import Dict, List, Optional

from pydantic import BaseModel, Field

from ..config import settings
from .mission import MissionPacket, Brand, Objective


class AssetKind(str, Enum):
    """What HIGGBOT is asked to produce (maps to its design.* surface)."""
    IMAGE = "image"          # single social image / graphic
    REEL = "reel"            # short vertical video (the hot-topic pipeline default)
    VIDEO = "video"          # generic video
    CAROUSEL = "carousel"    # multi-slide image set
    STORY = "story"          # vertical story frame
    LOGO = "logo"
    POSTER = "poster"
    THUMBNAIL = "thumbnail"


class QualityTier(str, Enum):
    """Cost/finish tier — sets the HIGGBOT budget cap and router escalation ceiling."""
    DRAFT = "draft"          # cheapest; placeholder-friendly
    PROD = "prod"            # publish-ready (default)
    HERO = "hero"            # flagship / award-grade


# Which ATHENA design-engine `task` best fits each asset kind (hint only; HIGGBOT
# decides the actual provider). Keys align with athena.ATHENA_DESIGN_TASKS.
_ASSET_TO_ATHENA_TASK: Dict[AssetKind, str] = {
    AssetKind.IMAGE: "social",
    AssetKind.REEL: "story",
    AssetKind.VIDEO: "motion",
    AssetKind.CAROUSEL: "social",
    AssetKind.STORY: "story",
    AssetKind.LOGO: "logo",
    AssetKind.POSTER: "poster",
    AssetKind.THUMBNAIL: "social",
}

# Default aspect ratio per asset kind.
_ASSET_ASPECT: Dict[AssetKind, str] = {
    AssetKind.IMAGE: "4:5",
    AssetKind.REEL: "9:16",
    AssetKind.VIDEO: "9:16",
    AssetKind.CAROUSEL: "4:5",
    AssetKind.STORY: "9:16",
    AssetKind.LOGO: "1:1",
    AssetKind.POSTER: "4:5",
    AssetKind.THUMBNAIL: "16:9",
}


def tier_budget_usd(tier: QualityTier) -> float:
    """Per-asset budget ceiling for a quality tier (USD). Real spend is metered
    inside HIGGBOT; this is the cap a brief may never exceed."""
    return {
        QualityTier.DRAFT: settings.creative_budget_draft_usd,
        QualityTier.PROD: settings.creative_budget_prod_usd,
        QualityTier.HERO: settings.creative_budget_hero_usd,
    }.get(tier, settings.creative_budget_prod_usd)


def _coerce_tier(raw: Optional[str]) -> QualityTier:
    try:
        return QualityTier((raw or "prod").strip().lower())
    except ValueError:
        return QualityTier.PROD


class CreativeBrief(BaseModel):
    """The one creative artifact ORELIUS hands to the HIGGBOT adapter. Typed,
    brand-scoped, budget-capped. Never a free-text instruction on its own."""

    mission_id: str
    brand: Brand
    asset_kind: AssetKind = AssetKind.REEL
    quality: QualityTier = QualityTier.PROD
    count: int = Field(1, ge=1, le=10)
    aspect_ratio: str = "9:16"

    # Visual/creative direction — concrete and self-contained for HIGGBOT.
    prompt: str
    style_notes: str = ""
    brand_voice: str = ""
    references: List[str] = Field(default_factory=list)

    # Guardrails HIGGBOT/ATHENA must respect.
    budget_usd: float = Field(0.0, ge=0.0)
    compliance_notes: str = (
        "Education, not individualized financial advice. Never promise returns "
        "or invent figures."
    )

    def max_spend(self) -> float:
        """Effective spend ceiling for the whole brief (per-asset cap × count)."""
        return round(self.budget_usd * self.count, 4)


def build_brief(packet: MissionPacket) -> CreativeBrief:
    """Synthesize a CreativeBrief from a MissionPacket's creative + topic + brand.

    Brand voice stays separated (directive §22): the ibluezcluezflow/IBC voice is
    only applied to IBC creative; NXG keeps its own scope. The concrete reel
    format/roadmap still lives with ATHENA — this brief carries direction, not a
    substitute for ATHENA's stored content roadmap.
    """
    tier = _coerce_tier(packet.creative.higgbot_quality if packet.creative else None)

    # Choose an asset kind: reels are the hot-topic default; a plain publish with
    # no creative flag would not reach here.
    asset_kind = AssetKind.REEL

    topic_title = packet.topic.title if packet.topic else ""
    brief_extra = ""
    if packet.brief:
        # brief is a small structured dict; fold any 'creative'/'visual' hint in.
        for k in ("creative", "visual", "direction", "prompt"):
            v = packet.brief.get(k) if isinstance(packet.brief, dict) else None
            if v:
                brief_extra = str(v)
                break

    prompt = topic_title or brief_extra or f"{packet.brand.value} social creative"
    if brief_extra and brief_extra != prompt:
        prompt = f"{prompt} — {brief_extra}"

    brand_voice = settings.ibluezcluezflow_guidelines if packet.brand == Brand.IBC else ""

    return CreativeBrief(
        mission_id=packet.mission_id,
        brand=packet.brand,
        asset_kind=asset_kind,
        quality=tier,
        count=1,
        aspect_ratio=_ASSET_ASPECT.get(asset_kind, "9:16"),
        prompt=prompt,
        style_notes="",
        brand_voice=brand_voice,
        references=[],
        budget_usd=tier_budget_usd(tier),
    )


def to_higgbot_job(brief: CreativeBrief) -> Dict:
    """Render a CreativeBrief into a HIGGBOT-shaped design job that ATHENA can
    forward (kind='design' on ATHENA's bridge). Provider is intentionally left
    unset — HIGGBOT's router chooses the cheapest capable one within budget."""
    task = _ASSET_TO_ATHENA_TASK.get(brief.asset_kind, "social")
    request_lines = [
        f"[{brief.brand.value} · creative] {brief.asset_kind.value} × {brief.count} "
        f"({brief.aspect_ratio}, tier={brief.quality.value})",
        f"Prompt: {brief.prompt}",
    ]
    if brief.style_notes:
        request_lines.append(f"Style: {brief.style_notes}")
    if brief.brand_voice:
        request_lines.append(f"Brand voice: {brief.brand_voice}")
    if brief.references:
        request_lines.append(f"References: {', '.join(brief.references)}")
    request_lines.append(f"Compliance: {brief.compliance_notes}")
    request_lines.append(
        f"Budget: <= ${brief.max_spend():.2f} total "
        f"(<= ${brief.budget_usd:.2f}/asset); router picks cheapest capable provider."
    )
    return {
        "kind": "design",                 # ATHENA bridge endpoint
        "task": task,                     # design-engine hint
        "asset_kind": brief.asset_kind.value,
        "quality": brief.quality.value,
        "count": brief.count,
        "aspect_ratio": brief.aspect_ratio,
        "budget_usd": brief.budget_usd,
        "max_spend_usd": brief.max_spend(),
        "request": "\n".join(request_lines),
    }
