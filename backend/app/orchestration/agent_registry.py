"""
Agent registry — ORELIUS selects specialist subagents through declarations rather
than hardcoding every workflow (directive §7, §10).

Phase 1 registers the specialist roster as typed DECLARATIONS (capability / risk /
cost / enabled / fallback). The actual agent implementations are added in later
phases; the registry is the stable lookup surface they plug into.
"""
from __future__ import annotations

from enum import Enum
from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class RiskClass(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class CostClass(str, Enum):
    NONE = "none"          # deterministic code, no model call
    LOW = "low"            # cheap classifier model
    MEDIUM = "medium"
    HIGH = "high"          # frontier synthesis


class LatencyClass(str, Enum):
    FAST = "fast"
    MEDIUM = "medium"
    SLOW = "slow"


class AgentSpec(BaseModel):
    id: str
    version: str = "1.0"
    description: str = ""
    capabilities: List[str] = Field(default_factory=list)
    risk: RiskClass = RiskClass.MEDIUM
    cost: CostClass = CostClass.LOW
    latency: LatencyClass = LatencyClass.MEDIUM
    required_tools: List[str] = Field(default_factory=list)
    enabled: bool = True
    owner: str = "orelius"
    fallback: Optional[str] = None       # id of a fallback agent, if any
    implemented: bool = False            # True once a runnable implementation exists


class AgentRegistry:
    """In-memory registry of specialist agents, seeded with the standard roster."""

    def __init__(self):
        self._agents: Dict[str, AgentSpec] = {}
        for spec in _default_roster():
            self.register(spec)

    def register(self, spec: AgentSpec) -> None:
        self._agents[spec.id] = spec

    def get(self, agent_id: str) -> Optional[AgentSpec]:
        return self._agents.get(agent_id)

    def all(self) -> List[AgentSpec]:
        return list(self._agents.values())

    def enabled(self) -> List[AgentSpec]:
        return [a for a in self._agents.values() if a.enabled]

    def by_capability(self, capability: str) -> List[AgentSpec]:
        return [a for a in self._agents.values()
                if a.enabled and capability in a.capabilities]

    def select(self, capability: str) -> Optional[AgentSpec]:
        """Pick the enabled, implemented agent for a capability (cheapest first),
        falling back to a declared-but-unimplemented one so callers can see intent."""
        candidates = self.by_capability(capability)
        if not candidates:
            return None
        order = {CostClass.NONE: 0, CostClass.LOW: 1, CostClass.MEDIUM: 2, CostClass.HIGH: 3}
        candidates.sort(key=lambda a: (not a.implemented, order.get(a.cost, 9)))
        return candidates[0]


def _default_roster() -> List[AgentSpec]:
    """The standard specialist roster (directive §7). Declared now, implemented per phase."""
    return [
        AgentSpec(
            id="economic_intelligence", description="Identify relevant, sourced economic developments.",
            capabilities=["economic_research", "source_verification"],
            risk=RiskClass.MEDIUM, cost=CostClass.LOW, latency=LatencyClass.SLOW,
            required_tools=["web_search", "finance_intel"], implemented=True,
        ),
        AgentSpec(
            id="financial_impact", description="Turn economic events into plain-English implications.",
            capabilities=["impact_analysis", "fact_vs_interpretation"],
            risk=RiskClass.MEDIUM, cost=CostClass.LOW, fallback="economic_intelligence",
            implemented=True,
        ),
        AgentSpec(
            id="audience_intelligence", description="Classify opportunities into audiences with confidence.",
            capabilities=["audience_classification"], risk=RiskClass.LOW, cost=CostClass.LOW,
        ),
        AgentSpec(
            id="social_opportunity", description="Find legitimately actionable social opportunities.",
            capabilities=["opportunity_detection"], risk=RiskClass.MEDIUM, cost=CostClass.LOW,
        ),
        AgentSpec(
            id="conversation_strategist", description="Decide next best action for a conversation.",
            capabilities=["conversation_strategy", "next_action"], risk=RiskClass.HIGH, cost=CostClass.MEDIUM,
        ),
        AgentSpec(
            id="content_strategist", description="Transform intelligence into content missions.",
            capabilities=["content_strategy", "mission_synthesis"], risk=RiskClass.MEDIUM, cost=CostClass.MEDIUM,
        ),
        AgentSpec(
            id="compliance_risk", description="Mandatory reviewer. When in doubt, block/escalate.",
            capabilities=["compliance_review"], risk=RiskClass.HIGH, cost=CostClass.LOW,
        ),
        AgentSpec(
            id="performance_analyst", description="Normalize touchpoint/conversation/content metrics.",
            capabilities=["performance_analysis"], risk=RiskClass.LOW, cost=CostClass.NONE,
        ),
        AgentSpec(
            id="allocation", description="Dynamically reallocate the daily touchpoint budget by outcome.",
            capabilities=["allocation"], risk=RiskClass.MEDIUM, cost=CostClass.NONE,
        ),
        AgentSpec(
            id="mission_evaluator", description="Score completed missions; feed learning back to ORELIUS.",
            capabilities=["mission_evaluation"], risk=RiskClass.LOW, cost=CostClass.LOW,
        ),
    ]


# Global registry instance.
agent_registry = AgentRegistry()
