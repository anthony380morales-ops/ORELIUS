"""
Mission Packet protocol — the typed contract every ecosystem action flows through.

ORELIUS is the executive brain. Its specialist subagents never send free-text
instructions straight to ATHENA/HIGGBOT; ORELIUS synthesizes their output into a
validated MissionPacket. A malformed mission never reaches an executor.

This module is pure and dependency-light (Pydantic only) so it can be unit-tested
with no database, network, or model calls.

Ref: master directive §8 (mission packet), §9 (queue states), §61 (versioning).
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone, timedelta
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator


# --------------------------------------------------------------------------- enums
class Brand(str, Enum):
    """The two brands never share a voice (directive §22)."""
    NXG = "NXG"                      # NXG Life Group — California consumers/business
    IBC = "IBC"                      # Infinite Blueprint Collective — pros/entrepreneurs


class Platform(str, Enum):
    INSTAGRAM = "instagram"
    FACEBOOK = "facebook"
    INTERNAL = "internal"            # research / analysis missions with no platform


class Objective(str, Enum):
    QUALIFIED_CONVERSATION = "qualified_conversation"
    MEANINGFUL_CONVERSATION = "meaningful_conversation"
    CONTENT_PUBLISH = "content_publish"
    ENGAGEMENT = "engagement"
    RESEARCH = "research"
    NURTURE = "nurture"
    HUMAN_HANDOFF = "human_handoff"


class Priority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


class MissionStatus(str, Enum):
    """Durable lifecycle states (directive §9)."""
    CREATED = "CREATED"
    VALIDATING = "VALIDATING"
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    WAITING = "WAITING"
    BLOCKED = "BLOCKED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    ESCALATED = "ESCALATED"
    CANCELLED = "CANCELLED"
    EXPIRED = "EXPIRED"


class TouchpointAction(str, Enum):
    """Only meaningful actions count as touchpoints (directive §17)."""
    CONTENT_ENGAGEMENT = "content_engagement"
    MEANINGFUL_COMMENT = "meaningful_comment"
    REPLY = "reply"
    INBOUND_DM = "inbound_dm"
    PERMITTED_DM = "permitted_dm"
    STORY_INTERACTION = "story_interaction"
    COMMENT_TO_DM = "comment_to_dm"
    FOLLOWUP = "followup"
    COMMUNITY_PARTICIPATION = "community_participation"
    PROSPECT_SIGNAL = "prospect_signal"
    COLLABORATION = "collaboration"
    CONTENT_DISTRIBUTION = "content_distribution"
    QUALIFICATION = "qualification"
    HUMAN_HANDOFF = "human_handoff"
    MONITOR = "monitor"
    ENGAGE = "engage"
    QUALIFY = "qualify"


class ConversationStage(str, Enum):
    """Persistent conversation states (directive §19)."""
    NEW = "new"
    OBSERVED = "observed"
    ENGAGED = "engaged"
    OPEN = "open"
    DISCOVERY = "discovery"
    CLASSIFIED = "classified"
    PERMISSION = "permission"
    QUALIFIED = "qualified"
    ROUTED = "routed"
    HUMAN_HANDOFF = "human_handoff"
    OUTCOME = "outcome"
    NURTURE = "nurture"
    DO_NOT_CONTACT = "do_not_contact"
    UNQUALIFIED = "unqualified"
    BLOCKED = "blocked"


class ComplianceStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    BLOCKED = "blocked"
    NEEDS_HUMAN = "needs_human"


# --------------------------------------------------------------------- sub-models
class Audience(BaseModel):
    type: str
    segment: Optional[str] = None
    confidence: float = Field(0.0, ge=0.0, le=1.0)


class Topic(BaseModel):
    title: str
    source_ids: List[str] = Field(default_factory=list)
    confidence: float = Field(0.0, ge=0.0, le=1.0)


class ConversationStrategy(BaseModel):
    stage: ConversationStage = ConversationStage.OPEN
    objective: Optional[str] = None


class CTA(BaseModel):
    destination: Optional[str] = None
    permission_required: bool = True


class Creative(BaseModel):
    required: bool = False
    higgbot_quality: str = "prod"   # draft | prod | hero


class Compliance(BaseModel):
    status: ComplianceStatus = ComplianceStatus.PENDING
    review_id: Optional[str] = None


class HumanHandoff(BaseModel):
    allowed: bool = True
    required_for: List[str] = Field(
        default_factory=lambda: ["high_intent", "product_specific_advice", "licensed_activity"]
    )


class Versions(BaseModel):
    """Postmortem-grade provenance (directive §61)."""
    system: str = "orelius-orch-1.0"
    agent: Optional[str] = None
    strategy: Optional[str] = None
    prompt: Optional[str] = None
    compliance_policy: str = "compliance-1.0"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _mission_id() -> str:
    return f"NXG-{_now():%Y}-{uuid.uuid4().hex[:8].upper()}"


# ------------------------------------------------------------------- the packet
class MissionPacket(BaseModel):
    """The one artifact ORELIUS hands to an executor. Validated, versioned, typed."""

    mission_id: str = Field(default_factory=_mission_id)
    created_at: datetime = Field(default_factory=_now)
    expires_at: Optional[datetime] = None

    source: str = "orelius"
    brand: Brand
    platform: Platform
    objective: Objective

    audience: Audience = Field(default_factory=lambda: Audience(type="unknown"))
    topic: Optional[Topic] = None

    actions: List[TouchpointAction] = Field(default_factory=list)
    touchpoint_budget: int = Field(0, ge=0)

    conversation_strategy: Optional[ConversationStrategy] = None
    cta: Optional[CTA] = None
    creative: Creative = Field(default_factory=Creative)
    compliance: Compliance = Field(default_factory=Compliance)
    human_handoff: HumanHandoff = Field(default_factory=HumanHandoff)

    priority: Priority = Priority.MEDIUM
    versions: Versions = Field(default_factory=Versions)

    # Free-form structured brief for the executor (never the sole instruction — the
    # typed fields above are authoritative). Kept small.
    brief: Optional[dict] = None

    @field_validator("expires_at", mode="before")
    @classmethod
    def _default_expiry(cls, v):
        return v  # set by helper below; kept nullable so partial packets validate

    def with_default_expiry(self, hours: int = 24) -> "MissionPacket":
        if self.expires_at is None:
            self.expires_at = self.created_at + timedelta(hours=hours)
        return self

    def is_ready_for_executor(self) -> bool:
        """A mission may only leave ORELIUS once compliance has cleared it."""
        return self.compliance.status == ComplianceStatus.APPROVED

    def is_expired(self, at: Optional[datetime] = None) -> bool:
        if self.expires_at is None:
            return False
        return (at or _now()) >= self.expires_at


def validate_mission(data: dict) -> MissionPacket:
    """Parse + validate an inbound dict into a MissionPacket (raises on malformed)."""
    return MissionPacket.model_validate(data).with_default_expiry()
