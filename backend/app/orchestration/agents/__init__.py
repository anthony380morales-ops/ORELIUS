"""Specialist intelligence subagents (directive §6). ORELIUS synthesizes their
typed output into MissionPackets — they never instruct executors directly.

Phase 6: economic_intelligence + financial_impact. Phase 7: audience_intelligence
+ social_opportunity. More agents (conversation strategist, content strategist,
compliance/risk, performance, allocation, mission evaluator) land in their phases."""
from .economic_intelligence import (  # noqa: F401
    economic_intelligence, EconomicIntelligenceAgent, EconomicSignal, signals_from_package,
)
from .financial_impact import (  # noqa: F401
    financial_impact, FinancialImpactAgent, ImpactAngle,
)
from .audience_intelligence import (  # noqa: F401
    audience_intelligence, AudienceIntelligenceAgent, AudienceInsight,
    apply_audience, top_concerns_from_leads,
)
from .social_opportunity import (  # noqa: F401
    social_opportunity, SocialOpportunityAgent, SocialOpportunity, opportunity_slate,
)
