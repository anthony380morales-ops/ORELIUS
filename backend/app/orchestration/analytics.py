"""
Performance feedback + analytics (directive §18 outcome-driven, §42 observability;
registry ids `performance_analyst` + `mission_evaluator`).

Records what actually happened — meaningful touchpoints and whether they produced
qualified conversations — and rolls it up into:
  • the North-Star ratio (qualified conversations per 1,000 meaningful touchpoints),
  • a per-action performance signal that the allocation engine (Phase 10) consumes
    to bend the daily budget toward what works,
  • per-mission evaluations fed back for learning.

This is the feedback half of the loop: intelligence → missions → compliance →
allocation → ACTION → (here) outcomes → back into allocation.
"""
from __future__ import annotations

from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from ..utils.logger import logger

OUTCOMES = ("none", "meaningful", "qualified")


def _pt_day(now_utc: Optional[datetime] = None) -> str:
    now = now_utc or datetime.now(timezone.utc)
    return (now - timedelta(hours=8)).strftime("%Y-%m-%d")


def qualified_per_1k(qualified: int, touchpoints: int) -> float:
    if touchpoints <= 0:
        return 0.0
    return round(1000.0 * qualified / touchpoints, 3)


class Analytics:
    async def record_touchpoint(self, db: AsyncSession, brand: str, action: str,
                                outcome: str = "meaningful", platform: str = "",
                                prospect_id: Optional[str] = None,
                                mission_id: Optional[str] = None,
                                cost_usd: float = 0.0) -> Dict:
        """Append one touchpoint event. Never raises — telemetry must not break flow."""
        from ..models.orchestration import TouchpointEvent
        outcome = outcome if outcome in OUTCOMES else "meaningful"
        try:
            row = TouchpointEvent(
                day=_pt_day(), brand=brand, platform=platform or None, action=action,
                outcome=outcome, prospect_id=prospect_id, mission_id=mission_id,
                cost_usd=float(cost_usd or 0.0),
            )
            db.add(row)
            await db.flush()
            return {"ok": True, "id": row.id}
        except Exception as e:  # noqa: BLE001
            logger.warning(f"record_touchpoint failed: {e}")
            return {"ok": False, "error": str(e)}

    async def rollup(self, db: AsyncSession, brand: Optional[str] = None,
                     day: Optional[str] = None) -> Dict:
        """Aggregate touchpoints → North-Star ratio + per-action breakdown."""
        from ..models.orchestration import TouchpointEvent
        q = select(TouchpointEvent.action, TouchpointEvent.outcome, func.count(),
                   func.coalesce(func.sum(TouchpointEvent.cost_usd), 0.0)) \
            .group_by(TouchpointEvent.action, TouchpointEvent.outcome)
        if brand:
            q = q.where(TouchpointEvent.brand == brand)
        if day:
            q = q.where(TouchpointEvent.day == day)
        rows = (await db.execute(q)).all()

        by_action: Dict[str, Dict] = {}
        total = meaningful = qualified = 0
        cost = 0.0
        for action, outcome, count, c in rows:
            a = by_action.setdefault(action, {"touchpoints": 0, "meaningful": 0,
                                              "qualified": 0, "cost_usd": 0.0})
            a["touchpoints"] += count
            a["cost_usd"] = round(a["cost_usd"] + float(c or 0.0), 4)
            total += count
            cost += float(c or 0.0)
            if outcome == "qualified":
                a["qualified"] += count
                a["meaningful"] += count      # qualified is also meaningful
                qualified += count
                meaningful += count
            elif outcome == "meaningful":
                a["meaningful"] += count
                meaningful += count
        for a in by_action.values():
            a["qualified_per_1k"] = qualified_per_1k(a["qualified"], a["touchpoints"])
        return {
            "brand": brand or "all", "day": day or "all",
            "touchpoints": total, "meaningful": meaningful, "qualified": qualified,
            "qualified_per_1k": qualified_per_1k(qualified, total),
            "cost_usd": round(cost, 4),
            "by_action": by_action,
        }

    async def performance_weights(self, db: AsyncSession, brand: str) -> Optional[Dict[str, float]]:
        """Per-action performance score for the allocator: Laplace-smoothed qualified
        rate. Returns None when there is no data yet (allocator uses the baseline)."""
        roll = await self.rollup(db, brand=brand)
        by_action = roll.get("by_action") or {}
        if not by_action or roll["touchpoints"] == 0:
            return None
        # (qualified + 1) / (touchpoints + 2) — unseen actions never score exactly 0.
        return {a: round((d["qualified"] + 1.0) / (d["touchpoints"] + 2.0), 5)
                for a, d in by_action.items()}

    async def performance_provider(self, db: AsyncSession) -> Dict[str, Dict[str, float]]:
        """{brand: {action: score}} for every brand that has data — the dict the
        allocation route turns into a sync perf_provider closure."""
        from ..models.orchestration import TouchpointEvent
        brands = (await db.execute(
            select(TouchpointEvent.brand).distinct()
        )).scalars().all()
        out: Dict[str, Dict[str, float]] = {}
        for b in brands:
            w = await self.performance_weights(db, b)
            if w:
                out[b] = w
        return out

    async def evaluate_mission(self, db: AsyncSession, mission_id: str,
                               qualified: int = 0, touchpoints: int = 0,
                               note: str = "") -> Dict:
        """Score a completed mission and record the evaluation on its row (§7
        mission_evaluator)."""
        from .mission_queue import mission_queue
        row = await mission_queue.get(db, mission_id)
        if not row:
            return {"ok": False, "reason": "mission_not_found"}
        evaluation = {
            "qualified": int(qualified), "touchpoints": int(touchpoints),
            "qualified_per_1k": qualified_per_1k(int(qualified), int(touchpoints)),
            "note": (note or "")[:512],
            "evaluated_at": datetime.now(timezone.utc).isoformat(),
        }
        result = dict(row.result or {})
        result["evaluation"] = evaluation
        row.result = result
        await db.flush()
        return {"ok": True, "mission_id": mission_id, "evaluation": evaluation}


analytics = Analytics()
