"""
Touchpoint allocation engine (directive §17, §18) — distributes the daily
touchpoint budget across brands and meaningful action types toward the North Star:
MAXIMIZE QUALIFIED CONVERSATIONS PER 1,000 MEANINGFUL TOUCHPOINTS.

Adaptive and outcome-driven: shares start from the brand baselines + the compliant
opportunity mix, then bend toward whatever is actually producing qualified
conversations. An exploration floor guarantees nothing starves, so the engine keeps
learning instead of collapsing onto one channel. Targets, never rigid quotas.

Pure math (apportionment, weight blending, the North-Star ratio) is separated so it
unit-tests with no DB. Kill switches are honored: a paused brand — or a global
pause — is allocated zero.
"""
from __future__ import annotations

import math
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..utils.logger import logger
from .mission import Brand
from .flags import flags, SocialMode
from .agents.social_opportunity import opportunity_slate

_ALL_BRANDS = [Brand.NXG, Brand.IBC]


# --------------------------------------------------------------------- pure math
def apportion(total: int, weights: Dict[str, float]) -> Dict[str, int]:
    """Largest-remainder apportionment: integer counts that sum EXACTLY to total,
    proportional to non-negative weights."""
    total = max(0, int(total))
    w = {k: max(0.0, float(v)) for k, v in weights.items()}
    s = sum(w.values())
    if total == 0 or s <= 0:
        return {k: 0 for k in w}
    raw = {k: total * v / s for k, v in w.items()}
    floor = {k: int(math.floor(x)) for k, x in raw.items()}
    remainder = total - sum(floor.values())
    order = sorted(w.keys(), key=lambda k: raw[k] - floor[k], reverse=True)
    for k in order[:remainder]:
        floor[k] += 1
    return floor


def _normalize(d: Dict[str, float]) -> Dict[str, float]:
    s = sum(max(0.0, v) for v in d.values())
    if s <= 0:
        n = len(d) or 1
        return {k: 1.0 / n for k in d}
    return {k: max(0.0, v) / s for k, v in d.items()}


def blend_weights(baseline: Dict[str, float], perf: Optional[Dict[str, float]] = None,
                  exploration: float = 0.15) -> Dict[str, float]:
    """Blend baseline shares with an outcome-driven performance signal.

    With no performance data yet, returns the baseline. With performance, weight is
    (1-exploration)·perf_share + exploration·uniform, so a strong performer earns
    more share while every option keeps a nonzero exploration floor."""
    if not baseline:
        return {}
    if not perf:
        return _normalize(baseline)
    exploration = min(0.9, max(0.0, exploration))
    perf_n = _normalize({k: perf.get(k, 0.0) for k in baseline})
    n = len(baseline)
    uniform = 1.0 / n
    return _normalize({k: (1 - exploration) * perf_n[k] + exploration * uniform
                       for k in baseline})


def qualified_per_1k(qualified: int, touchpoints: int) -> float:
    """The North-Star ratio: qualified conversations per 1,000 meaningful touchpoints."""
    if touchpoints <= 0:
        return 0.0
    return round(1000.0 * qualified / touchpoints, 3)


def _pt_day(now_utc: Optional[datetime] = None) -> str:
    now = now_utc or datetime.now(timezone.utc)
    return (now - timedelta(hours=8)).strftime("%Y-%m-%d")   # PT (approx, no DST)


def _brand_baseline(brand: Brand) -> int:
    return int(getattr(settings, "ibc_touchpoint_baseline", 600) if brand == Brand.IBC
               else getattr(settings, "nxg_touchpoint_baseline", 430))


# ------------------------------------------------------------------- the engine
class AllocationEngine:
    async def _active_brand_weights(self, db: AsyncSession) -> Dict[str, float]:
        """Baseline brand weights with paused brands zeroed out."""
        system_paused = await flags.get(db, "SYSTEM_PAUSE")
        outbound_paused = await flags.get(db, "OUTBOUND_PAUSE")
        weights: Dict[str, float] = {}
        for b in _ALL_BRANDS:
            paused = (system_paused or outbound_paused
                      or await flags.get(db, f"{b.value}_PAUSE"))
            weights[b.value] = 0.0 if paused else float(_brand_baseline(b))
        return weights

    async def plan_day(self, db: AsyncSession, total: Optional[int] = None,
                       perf_provider=None) -> Dict:
        """Compute the day's allocation: brand split, then action split per brand.

        `perf_provider(brand) -> {action: score}` is the outcome signal (Phase 11);
        when omitted the compliant opportunity mix is the baseline weighting."""
        total = int(total if total is not None else
                    getattr(settings, "social_daily_touchpoint_target", 1050))
        mode = await flags.mode(db)

        # The exploration floor is adaptively tuned (Phase 12), within safe bounds.
        try:
            from .optimizer import optimizer
            exploration = await optimizer.get_param(db, "allocation.exploration")
        except Exception as e:  # noqa: BLE001 - never let tuning break planning
            logger.debug(f"exploration param read fell back to default: {e}")
            exploration = 0.15

        brand_weights = await self._active_brand_weights(db)
        brand_totals = apportion(total, brand_weights)

        plan: Dict[str, Dict[str, int]] = {}
        inputs: Dict[str, Dict] = {}
        for b in _ALL_BRANDS:
            bt = brand_totals.get(b.value, 0)
            slate = opportunity_slate(b)
            baseline = {o.action.value: float(o.est_touchpoints) for o in slate}
            perf = None
            if perf_provider is not None:
                try:
                    perf = perf_provider(b)
                except Exception as e:  # noqa: BLE001
                    logger.debug(f"perf provider failed for {b.value}: {e}")
                    perf = None
            weights = blend_weights(baseline, perf, exploration=exploration)
            plan[b.value] = apportion(bt, weights) if bt > 0 else {k: 0 for k in baseline}
            inputs[b.value] = {"brand_total": bt, "weights": weights,
                               "used_performance": bool(perf)}

        planned_total = sum(sum(a.values()) for a in plan.values())
        return {
            "day": _pt_day(), "mode": mode.value, "target": total,
            "planned_total": planned_total, "exploration": exploration,
            "brand_totals": brand_totals, "plan": plan, "inputs": inputs,
            "note": ("system paused — zero allocation" if planned_total == 0
                     else "allocation plan (targets, not quotas)"),
        }

    async def plan_and_store(self, db: AsyncSession, total: Optional[int] = None,
                             perf_provider=None) -> Dict:
        from ..models.orchestration import AllocationSnapshot
        result = await self.plan_day(db, total=total, perf_provider=perf_provider)
        row = AllocationSnapshot(
            day=result["day"], total=result["planned_total"], mode=result["mode"],
            plan=result["plan"], inputs=result["inputs"],
        )
        db.add(row)
        await db.flush()
        result["snapshot_id"] = row.id
        return result

    async def latest(self, db: AsyncSession) -> Optional[Dict]:
        from ..models.orchestration import AllocationSnapshot
        row = (await db.execute(
            select(AllocationSnapshot).order_by(AllocationSnapshot.created_at.desc()).limit(1)
        )).scalars().first()
        if not row:
            return None
        return {"snapshot_id": row.id, "day": row.day, "total": row.total,
                "mode": row.mode, "plan": row.plan, "inputs": row.inputs,
                "created_at": row.created_at.isoformat() if row.created_at else None}


allocation_engine = AllocationEngine()
