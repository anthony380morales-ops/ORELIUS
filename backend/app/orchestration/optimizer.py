"""
Adaptive optimization governor (directive §12).

Tunes ONLY whitelisted, bounded orchestration parameters and routing choices from
the performance signal. It NEVER edits source code, and the messaging humanization
rules, the compliance rules, and the kill switches are NOT tunable — they are not in
the allowlist, and a defense-in-depth namespace guard rejects them outright.

Every change is bounded (min/max + a per-cycle max step), auditable (OptimizationLog),
and reversible. Large steps are escalated to a human instead of applied. A North-Star
gate lets a later cycle detect a change that hurt the metric and roll it back.
"""
from __future__ import annotations

from typing import Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..utils.logger import logger
from .analytics import analytics

# The ONLY parameters that may be tuned. Anything not here cannot be changed.
TUNABLES: Dict[str, Dict] = {
    "allocation.exploration": {
        "type": "float", "min": 0.05, "max": 0.40, "default": 0.15, "max_step": 0.10,
        "desc": "Exploration floor in the touchpoint allocator (explore vs exploit).",
    },
    "mission.max_attempts": {
        "type": "int", "min": 1, "max": 5, "default": 3, "max_step": 1,
        "desc": "Retry attempts before a mission dead-letters.",
    },
    "creative.default_quality": {
        "type": "choice", "choices": ["draft", "prod", "hero"], "default": "prod",
        "desc": "Default HIGGBOT quality tier when a mission does not specify one.",
    },
}

# Defense in depth: even if a key were added by mistake, these namespaces are never
# tunable through this governor.
_FORBIDDEN = ("messaging", "compliance", "policy", "flag", "kill", "dash", "pause",
              "secret", "token", "key")

# Minimum touchpoints before the recommender trusts the signal enough to exploit.
_MIN_SIGNAL = 200
_REGRESSION_TOLERANCE = 0.0    # any drop vs metric_before triggers a rollback


def is_tunable(key: str) -> bool:
    if key not in TUNABLES:
        return False
    return not any(bad in key.lower() for bad in _FORBIDDEN)


def _spec(key: str) -> Dict:
    return TUNABLES[key]


def clamp(key: str, value):
    """Coerce + clamp a value to its spec. Raises for a non-tunable key."""
    if not is_tunable(key):
        raise ValueError(f"not a tunable parameter: {key}")
    spec = _spec(key)
    t = spec["type"]
    if t == "choice":
        return value if value in spec["choices"] else spec["default"]
    try:
        num = float(value)
    except (TypeError, ValueError):
        return spec["default"]
    num = max(spec["min"], min(spec["max"], num))
    return int(round(num)) if t == "int" else round(num, 4)


class Optimizer:
    async def get_param(self, db: AsyncSession, key: str):
        if not is_tunable(key):
            raise ValueError(f"not a tunable parameter: {key}")
        from ..models.orchestration import TunedParam
        row = (await db.execute(
            select(TunedParam).where(TunedParam.key == key)
        )).scalars().first()
        if row and isinstance(row.value, dict) and "v" in row.value:
            return clamp(key, row.value["v"])
        return _spec(key)["default"]

    async def all_params(self, db: AsyncSession) -> Dict:
        return {k: await self.get_param(db, k) for k in TUNABLES}

    async def _log(self, db, key, old, new, status, reason, actor, metric_before):
        from ..models.orchestration import OptimizationLog
        row = OptimizationLog(key=key, old_value={"v": old}, new_value={"v": new},
                              status=status, reason=(reason or "")[:512], actor=actor,
                              metric_before=metric_before)
        db.add(row)
        await db.flush()
        return row

    async def _write(self, db, key, value):
        from ..models.orchestration import TunedParam
        row = (await db.execute(
            select(TunedParam).where(TunedParam.key == key)
        )).scalars().first()
        if row:
            row.value = {"v": value}
        else:
            db.add(TunedParam(key=key, value={"v": value}))
        await db.flush()

    async def propose(self, db: AsyncSession, key: str, value, reason: str = "",
                      actor: str = "optimizer") -> Dict:
        """Validate + bound a change. A step within max_step is applied; a larger
        step is escalated (recorded, not applied) for a human to approve."""
        if not is_tunable(key):
            return {"ok": False, "reason": "not_tunable", "key": key}
        current = await self.get_param(db, key)
        target = clamp(key, value)
        spec = _spec(key)
        metric = (await analytics.rollup(db))["qualified_per_1k"]

        # Numeric step guard (choices are inherently bounded by their set).
        if spec["type"] in ("float", "int"):
            step = abs(float(target) - float(current))
            if step > spec.get("max_step", float("inf")) + 1e-9:
                await self._log(db, key, current, target, "escalated", reason, actor, metric)
                return {"ok": True, "applied": False, "escalated": True, "key": key,
                        "current": current, "proposed": target,
                        "reason": "step_exceeds_max — escalated for human approval"}

        if target == current:
            return {"ok": True, "applied": False, "key": key, "current": current,
                    "note": "no change"}

        await self._write(db, key, target)
        await self._log(db, key, current, target, "applied", reason, actor, metric)
        logger.info(f"optimizer applied {key}: {current} -> {target} ({reason})")
        return {"ok": True, "applied": True, "key": key, "old": current, "new": target}

    async def revert(self, db: AsyncSession, key: str, actor: str = "optimizer") -> Dict:
        """Roll a parameter back to the previous value from its last applied change."""
        from ..models.orchestration import OptimizationLog
        last = (await db.execute(
            select(OptimizationLog).where(OptimizationLog.key == key)
            .where(OptimizationLog.status == "applied")
            .order_by(OptimizationLog.created_at.desc()).limit(1)
        )).scalars().first()
        if not last or not last.old_value:
            return {"ok": False, "reason": "nothing_to_revert", "key": key}
        old = last.old_value.get("v")
        current = await self.get_param(db, key)
        await self._write(db, key, clamp(key, old))
        await self._log(db, key, current, old, "reverted", "manual/auto revert", actor, None)
        return {"ok": True, "key": key, "reverted_to": old, "from": current}

    async def recommend(self, db: AsyncSession) -> List[Dict]:
        """Deterministic explore→exploit schedule from the live North-Star data.

        Early (little data) → explore more; once the signal is trustworthy → exploit
        more by lowering the exploration floor. Returns proposals, applies nothing."""
        roll = await analytics.rollup(db)
        total = roll["touchpoints"]
        recs: List[Dict] = []
        expl = await self.get_param(db, "allocation.exploration")
        if total < 50:
            target = clamp("allocation.exploration", expl + 0.05)
            if target > expl:
                recs.append({"key": "allocation.exploration", "current": expl,
                             "proposed": target,
                             "reason": f"early stage ({total} touchpoints) — explore more"})
        elif total >= _MIN_SIGNAL and expl > 0.10:
            target = clamp("allocation.exploration", expl - 0.05)
            recs.append({"key": "allocation.exploration", "current": expl,
                         "proposed": target,
                         "reason": f"strong signal ({total} touchpoints, "
                                   f"{roll['qualified_per_1k']}/1k) — exploit more"})
        return recs

    async def evaluate_and_rollback(self, db: AsyncSession) -> List[Dict]:
        """North-Star gate: for each parameter's last applied change, compare the
        current metric to metric_before; if it regressed, roll the change back."""
        from ..models.orchestration import OptimizationLog
        current_metric = (await analytics.rollup(db))["qualified_per_1k"]
        actions: List[Dict] = []
        for key in TUNABLES:
            last = (await db.execute(
                select(OptimizationLog).where(OptimizationLog.key == key)
                .where(OptimizationLog.status == "applied")
                .order_by(OptimizationLog.created_at.desc()).limit(1)
            )).scalars().first()
            if not last or last.metric_before is None:
                continue
            last.metric_after = current_metric
            if current_metric < last.metric_before - _REGRESSION_TOLERANCE:
                rev = await self.revert(db, key)
                if rev.get("ok"):
                    actions.append({"key": key, "action": "reverted",
                                    "before": last.metric_before, "after": current_metric})
        await db.flush()
        return actions

    async def auto_tune(self, db: AsyncSession, apply: bool = False) -> Dict:
        """One optimization cycle: gate (rollback regressions) → recommend →
        optionally apply the safe, within-bound recommendations."""
        rolled_back = await self.evaluate_and_rollback(db)
        recs = await self.recommend(db)
        applied: List[Dict] = []
        if apply:
            for r in recs:
                out = await self.propose(db, r["key"], r["proposed"],
                                         reason=r["reason"], actor="auto_tune")
                applied.append(out)
        return {"rolled_back": rolled_back, "recommendations": recs,
                "applied": applied if apply else []}


optimizer = Optimizer()
