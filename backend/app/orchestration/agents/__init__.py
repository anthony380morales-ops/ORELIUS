"""Specialist intelligence subagents (directive §6). ORELIUS synthesizes their
typed output into MissionPackets — they never instruct executors directly.

Phase 6: economic_intelligence + financial_impact. More agents (audience, social
opportunity, conversation strategist, content strategist, compliance/risk,
performance, allocation, mission evaluator) land in their phases."""
from .economic_intelligence import (  # noqa: F401
    economic_intelligence, EconomicIntelligenceAgent, EconomicSignal, signals_from_package,
)
from .financial_impact import (  # noqa: F401
    financial_impact, FinancialImpactAgent, ImpactAngle,
)
