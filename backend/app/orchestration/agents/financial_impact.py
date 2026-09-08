"""
Financial Impact agent (directive §6, registry id `financial_impact`).

Takes verified EconomicSignals and translates each into a brand-scoped
life-insurance / Infinite Banking ANGLE with an audience hint and an opportunity
score — the "stack against life insurance" step, made typed and rankable.

Pure and deterministic (no model call, no network): it reuses the already-cited
framing carried on each signal and scores relevance with a transparent heuristic,
so it is cheap and fully unit-testable. Every angle is flagged for compliance
review — financial content is education, never individualized advice (directive §31).
"""
from __future__ import annotations

from typing import List

from pydantic import BaseModel, Field

from ..mission import Brand
from .economic_intelligence import EconomicSignal

# Terms that make an economic signal especially relevant to protect-and-grow /
# Infinite Banking / life-insurance messaging. Presence raises the opportunity score.
_RELEVANCE_TERMS = (
    "rate", "interest", "inflation", "yield", "debt", "deficit", "bank", "savings",
    "recession", "market", "fed", "treasury", "bond", "tax", "retirement", "dollar",
)


def _score(signal: EconomicSignal) -> float:
    """Transparent 0–1 relevance score: base confidence nudged by term hits."""
    text = f"{signal.headline} {signal.framing}".lower()
    hits = sum(1 for t in _RELEVANCE_TERMS if t in text)
    score = 0.55 * signal.confidence + min(0.45, 0.09 * hits)
    return round(min(1.0, score), 3)


def _angle_for(signal: EconomicSignal, brand: Brand) -> str:
    if brand == Brand.IBC:
        lens = "why it strengthens the case for Infinite Banking and protect-and-grow"
    else:
        lens = "what it means for protecting your family with the right life coverage"
    return f"{signal.headline} — {lens}."


def _audience_for(brand: Brand) -> str:
    return "professionals_entrepreneurs" if brand == Brand.IBC else "california_families"


class ImpactAngle(BaseModel):
    signal_id: str
    brand: Brand
    angle: str
    audience_hint: str
    opportunity_score: float = Field(0.0, ge=0.0, le=1.0)
    # Financial content is education, not individualized advice — always reviewed.
    needs_compliance_review: bool = True


class FinancialImpactAgent:
    def assess(self, signals: List[EconomicSignal], brand: Brand) -> List[ImpactAngle]:
        """Map signals → ranked, brand-scoped impact angles (highest score first)."""
        angles = [
            ImpactAngle(
                signal_id=s.id, brand=brand,
                angle=_angle_for(s, brand),
                audience_hint=_audience_for(brand),
                opportunity_score=_score(s),
            )
            for s in signals
        ]
        angles.sort(key=lambda a: a.opportunity_score, reverse=True)
        return angles


financial_impact = FinancialImpactAgent()
