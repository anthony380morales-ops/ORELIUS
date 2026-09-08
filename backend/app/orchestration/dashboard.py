"""
North-Star dashboard (directive §5, §18) — one consolidated, read-only snapshot of
the whole ecosystem, centered on the North Star: qualified conversations per 1,000
meaningful touchpoints.

Pure aggregation: it composes what the specialist modules already expose (control
surface, analytics, allocation, optimizer, mission queue, agent registry, executor
health) into a single payload any surface — the phone app, LUCIUS, an artifact —
can render. Every sub-read is guarded so one slow/absent source never blanks the
whole board.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict

from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..utils.logger import logger
from .control import control_surface
from .analytics import analytics
from .allocation import allocation_engine
from .optimizer import optimizer
from .agent_registry import agent_registry
from .adapters import lucius_adapter
from .mission import Brand


async def _safe(coro, default, label: str):
    try:
        return await coro
    except Exception as e:  # noqa: BLE001 - one bad source must not blank the board
        logger.debug(f"dashboard sub-read '{label}' failed: {e}")
        return default


class Dashboard:
    async def snapshot(self, db: AsyncSession) -> Dict:
        status = await _safe(control_surface.status(db), {}, "control_status")
        roll = await _safe(analytics.rollup(db), {}, "rollup")

        # Per-brand North-Star breakdown.
        brands: Dict[str, Dict] = {}
        for b in (Brand.NXG, Brand.IBC):
            r = await _safe(analytics.rollup(db, brand=b.value), {}, f"rollup_{b.value}")
            brands[b.value] = {
                "touchpoints": r.get("touchpoints", 0),
                "qualified": r.get("qualified", 0),
                "qualified_per_1k": r.get("qualified_per_1k", 0.0),
            }

        allocation = await _safe(allocation_engine.latest(db), None, "allocation_latest")
        if not allocation:
            # no stored snapshot yet → show today's computed plan summary
            plan = await _safe(allocation_engine.plan_day(db), {}, "allocation_plan")
            allocation = {"day": plan.get("day"), "total": plan.get("planned_total", 0),
                          "mode": plan.get("mode"), "plan": plan.get("plan", {}),
                          "exploration": plan.get("exploration"), "computed": True}

        params = await _safe(optimizer.all_params(db), {}, "optimizer_params")
        recs = await _safe(optimizer.recommend(db), [], "optimizer_recommend")
        lucius = await _safe(lucius_adapter.health(db), {}, "lucius_health")

        agents = agent_registry.all()
        implemented = sum(1 for a in agents if a.implemented)

        target = int(getattr(settings, "social_daily_touchpoint_target", 1050))
        touchpoints = roll.get("touchpoints", 0)

        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "mode": status.get("mode"),
            "north_star": {
                "metric": "qualified_conversations_per_1000_meaningful_touchpoints",
                "value": roll.get("qualified_per_1k", 0.0),
                "touchpoints": touchpoints,
                "meaningful": roll.get("meaningful", 0),
                "qualified": roll.get("qualified", 0),
                "daily_touchpoint_target": target,
                "target_progress": round(min(1.0, touchpoints / target), 3) if target else 0.0,
                "by_brand": brands,
            },
            "flags": status.get("paused", {}),
            "any_paused": status.get("any_paused", False),
            "queue": status.get("queue", {}),
            "pending": {
                "approvals": status.get("pending_approvals", 0),
                "handoffs": status.get("pending_handoffs", 0),
            },
            "allocation": allocation,
            "performance_by_action": roll.get("by_action", {}),
            "optimizer": {"params": params, "recommendations": len(recs)},
            "executors": {
                "athena": (status.get("executors") or {}).get("athena", {}),
                "higgbot": (status.get("executors") or {}).get("higgbot", {}),
                "lucius": lucius,
            },
            "agents": {"implemented": implemented, "total": len(agents)},
        }


dashboard = Dashboard()
