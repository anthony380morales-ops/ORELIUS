"""
Economic Intelligence agent (directive §6, registry id `economic_intelligence`).

The first specialist subagent. It does NOT re-fetch or re-analyze the economy —
that pipeline already exists and stays authoritative (directive §41 no duplication):
  finance_intel  → cited, verified economic data + web-searched news
  hot_topic      → compresses it into the N hottest VERIFIED facts + framing

This agent REUSES that compiled package and lifts it into a typed contract —
`EconomicSignal`s — that the mission planner and the financial-impact agent can
reason over. Verified-only: it never invents figures; every signal traces back to
the compiled, cited intelligence.
"""
from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Dict, List, Optional

from pydantic import BaseModel, Field

from sqlalchemy.ext.asyncio import AsyncSession

from ...utils.logger import logger


class EconomicSignal(BaseModel):
    """One verified economic fact, plain-language, traceable to compiled intel."""
    id: str
    headline: str
    category: str = "economic"
    confidence: float = Field(0.7, ge=0.0, le=1.0)
    framing: str = ""          # shared caption/post-idea context from the compile step
    as_of: str = ""


def _signal_id(headline: str, idx: int) -> str:
    h = hashlib.sha256(headline.encode()).hexdigest()[:8]
    return f"sig-{idx}-{h}"


def signals_from_package(package: Dict) -> List[EconomicSignal]:
    """Pure: map a compiled hot-topic package ({facts, caption, post_idea, ...}) to
    typed EconomicSignals. Framing (caption + post idea) is shared context, carried
    on every signal so the impact agent reuses the same verified framing."""
    facts = [str(f).strip() for f in (package.get("facts") or []) if str(f).strip()]
    caption = str(package.get("caption", "")).strip()
    post_idea = str(package.get("post_idea", "")).strip()
    framing = " ".join(x for x in (caption, post_idea) if x)
    as_of = str(package.get("created_at") or datetime.now(timezone.utc).isoformat())
    return [
        EconomicSignal(id=_signal_id(fact, i), headline=fact, framing=framing, as_of=as_of)
        for i, fact in enumerate(facts)
    ]


class EconomicIntelligenceAgent:
    async def gather(self, db: AsyncSession) -> List[EconomicSignal]:
        """Reuse the existing compiled-intel pipeline and lift it to signals.

        Returns [] (never raises) when there is no fresh, verified intelligence —
        the planner then simply proposes nothing this cycle."""
        try:
            from ...core.hot_topic import hot_topic_reels
            result = await hot_topic_reels.compile_package(db)
        except Exception as e:  # noqa: BLE001 - intelligence must never crash a scan
            logger.warning(f"economic intelligence gather failed: {e}")
            return []
        if not result.get("ok"):
            logger.info(f"economic intelligence: no package ({result.get('reason')})")
            return []
        return signals_from_package(result.get("package") or {})


economic_intelligence = EconomicIntelligenceAgent()
