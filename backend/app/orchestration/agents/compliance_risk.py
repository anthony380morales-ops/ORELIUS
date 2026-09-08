"""
Compliance / Risk agent (directive §31 compliance-as-code, §62; registry id
`compliance_risk`). THE mandatory reviewer — nothing reaches an executor without a
verdict, and the standing rule is: when in doubt, block or escalate, never
silently approve.

Deterministic and transparent so every verdict is explainable and unit-testable:
  • review_message — an autonomous message: reuses messaging_policy (the "--" rule,
    urgency, canned phrases) and adds prohibited-claim + individualized-advice
    detection. Hard violations BLOCK; advice/licensed language needs a human.
  • review_mission — a MissionPacket: completeness, prohibited claims in the
    topic/brief, and objective risk. Educational content that passes clears;
    a human-handoff objective or anything ambiguous goes to a person.

Both brands are held to the same rule: education, NOT individualized financial
advice; never promise returns or invent figures.
"""
from __future__ import annotations

import re
import uuid
from typing import List, Tuple

from pydantic import BaseModel, Field

from ..mission import MissionPacket, Objective, ComplianceStatus
from ..messaging_policy import validate_autonomous_message, POLICY_VERSION

COMPLIANCE_POLICY_VERSION = "compliance-1.0"

# Claims that must never appear — promises of return, risk-free framing, hype.
_PROHIBITED = re.compile(
    r"\b(guaranteed?\s+returns?|guaranteed\s+\d|risk[\s-]?free|no\s+risk|"
    r"get\s+rich|double\s+your\s+money|triple\s+your\s+money|beat\s+the\s+market|"
    r"assured\s+returns?|can'?t\s+lose|zero\s+risk|100%\s+safe|tax[\s-]?free\s+guaranteed)\b",
    re.I,
)

# Language that turns education into individualized, licensed advice.
_INDIVIDUALIZED_ADVICE = re.compile(
    r"\b(you\s+should\s+buy|i\s+recommend\s+you|the\s+right\s+policy\s+for\s+you|"
    r"you\s+need\s+to\s+purchase|buy\s+this\s+policy|you\s+qualify\s+for|"
    r"your\s+best\s+option\s+is)\b",
    re.I,
)


def scan_prohibited(text: str) -> List[str]:
    """Return the prohibited-claim phrases found in text (empty if clean)."""
    return [m.group(0).strip() for m in _PROHIBITED.finditer(text or "")]


def scan_advice(text: str) -> List[str]:
    return [m.group(0).strip() for m in _INDIVIDUALIZED_ADVICE.finditer(text or "")]


class ComplianceVerdict(BaseModel):
    status: ComplianceStatus
    reasons: List[str] = Field(default_factory=list)
    flags: List[str] = Field(default_factory=list)
    review_id: str = Field(default_factory=lambda: "rv-" + uuid.uuid4().hex[:10])
    policy_version: str = COMPLIANCE_POLICY_VERSION

    @property
    def approved(self) -> bool:
        return self.status == ComplianceStatus.APPROVED


class ComplianceRiskAgent:
    def review_message(self, text: str) -> ComplianceVerdict:
        """Review one autonomous message. Hard policy breaks or prohibited claims
        BLOCK; individualized-advice language needs a human; else approved."""
        reasons: List[str] = []
        policy = validate_autonomous_message(text or "")
        prohibited = scan_prohibited(text)
        advice = scan_advice(text)

        if prohibited:
            reasons.append("prohibited_claim:" + ",".join(prohibited))
        # the "--" rule and manufactured urgency are hard blocks
        hard_policy = [i for i in policy["issues"]
                       if i == "contains_double_dash" or i.startswith("manufactured_urgency")]
        if hard_policy:
            reasons.append("messaging_policy:" + ",".join(hard_policy))

        if reasons:
            return ComplianceVerdict(status=ComplianceStatus.BLOCKED, reasons=reasons,
                                     flags=policy["issues"])
        if advice:
            return ComplianceVerdict(status=ComplianceStatus.NEEDS_HUMAN,
                                     reasons=["individualized_advice:" + ",".join(advice)],
                                     flags=policy["issues"])
        # soft policy issues (a single canned phrase, too many questions) → flag,
        # not block; the strategist should still prefer a regenerate.
        if not policy["ok"]:
            return ComplianceVerdict(status=ComplianceStatus.APPROVED,
                                     reasons=["soft_policy_flags"], flags=policy["issues"])
        return ComplianceVerdict(status=ComplianceStatus.APPROVED)

    def review_mission(self, packet: MissionPacket) -> ComplianceVerdict:
        """Review a MissionPacket. Conservative: incomplete or claim-bearing → BLOCK;
        human-handoff or ambiguous objective → NEEDS_HUMAN; clean education → APPROVE."""
        reasons: List[str] = []
        brief_text = ""
        if packet.brief:
            try:
                brief_text = " ".join(str(v) for v in packet.brief.values())
            except Exception:  # noqa: BLE001
                brief_text = str(packet.brief)
        topic_text = packet.topic.title if packet.topic else ""
        blob = f"{topic_text} {brief_text}"

        prohibited = scan_prohibited(blob)
        if prohibited:
            reasons.append("prohibited_claim:" + ",".join(prohibited))
        advice = scan_advice(blob)

        # Human-handoff missions are, by definition, a person's job.
        if packet.objective == Objective.HUMAN_HANDOFF:
            return ComplianceVerdict(status=ComplianceStatus.NEEDS_HUMAN,
                                     reasons=["objective_requires_human"])

        # Content/research completeness.
        if packet.objective == Objective.CONTENT_PUBLISH and not topic_text.strip():
            reasons.append("incomplete:content_publish_without_topic")

        if reasons:
            return ComplianceVerdict(status=ComplianceStatus.BLOCKED, reasons=reasons)
        if advice:
            return ComplianceVerdict(status=ComplianceStatus.NEEDS_HUMAN,
                                     reasons=["individualized_advice:" + ",".join(advice)])
        return ComplianceVerdict(status=ComplianceStatus.APPROVED)


compliance_risk = ComplianceRiskAgent()
