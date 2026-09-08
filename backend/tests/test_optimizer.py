"""
Phase 12 tests — adaptive optimization governor.

Proves the safety properties: only whitelisted params are tunable, values are
clamped, big steps escalate instead of applying, changes are reversible, a tuned
param actually reaches the allocator, and the North-Star gate rolls back a change
that hurt the metric.

Run with pytest, or directly:  python backend/tests/test_optimizer.py
"""
import asyncio

from sqlalchemy.pool import StaticPool
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from app.database import Base
from app.orchestration.optimizer import optimizer, is_tunable, clamp, TUNABLES
from app.orchestration.allocation import allocation_engine
from app.orchestration.analytics import analytics


# ------------------------------------------------------------------ pure guards
def test_only_whitelisted_are_tunable():
    assert is_tunable("allocation.exploration") is True
    assert is_tunable("mission.max_attempts") is True
    # forbidden / unknown keys are never tunable
    assert is_tunable("messaging.forbidden_sequence") is False
    assert is_tunable("compliance.rules") is False
    assert is_tunable("flags.system_pause") is False
    assert is_tunable("anything.else") is False


def test_clamp_bounds_and_choices():
    assert clamp("allocation.exploration", 99) == 0.40      # clamped to max
    assert clamp("allocation.exploration", 0.0) == 0.05     # clamped to min
    assert clamp("mission.max_attempts", 2.6) == 3          # int rounding
    assert clamp("creative.default_quality", "bogus") == "prod"   # invalid choice → default
    assert clamp("creative.default_quality", "hero") == "hero"


def test_clamp_rejects_non_tunable():
    try:
        clamp("messaging.dash_rule", 1)
    except ValueError:
        return
    raise AssertionError("clamp must reject a non-tunable key")


# ------------------------------------------------------------------ harness
_ENGINES: list = []


def _run(coro):
    async def _wrapped():
        try:
            await coro
        finally:
            for eng in _ENGINES:
                await eng.dispose()
            _ENGINES.clear()
    return asyncio.run(_wrapped())


async def _fresh_session() -> AsyncSession:
    import app.models.orchestration  # noqa: F401
    engine = create_async_engine(
        "sqlite+aiosqlite://", echo=False,
        poolclass=StaticPool, connect_args={"check_same_thread": False},
    )
    _ENGINES.append(engine)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)()


async def _seed(db, brand, action, outcome, n):
    for _ in range(n):
        await analytics.record_touchpoint(db, brand=brand, action=action, outcome=outcome)


# ------------------------------------------------------------------ params
def test_default_then_apply_and_get():
    async def go():
        db = await _fresh_session()
        assert await optimizer.get_param(db, "allocation.exploration") == 0.15   # default
        out = await optimizer.propose(db, "allocation.exploration", 0.20, reason="test")
        assert out["applied"] is True and out["new"] == 0.20
        assert await optimizer.get_param(db, "allocation.exploration") == 0.20
    _run(go())


def test_reject_non_tunable_propose():
    async def go():
        db = await _fresh_session()
        out = await optimizer.propose(db, "messaging.dash", "x")
        assert out["ok"] is False and out["reason"] == "not_tunable"
    _run(go())


def test_big_step_escalates_not_applies():
    async def go():
        db = await _fresh_session()
        # default 0.15, max_step 0.10 → jumping to 0.40 is a 0.25 step → escalate
        out = await optimizer.propose(db, "allocation.exploration", 0.40, reason="jump")
        assert out["applied"] is False and out["escalated"] is True
        # value unchanged
        assert await optimizer.get_param(db, "allocation.exploration") == 0.15
    _run(go())


def test_revert_restores_previous():
    async def go():
        db = await _fresh_session()
        await optimizer.propose(db, "allocation.exploration", 0.20, reason="up")
        rev = await optimizer.revert(db, "allocation.exploration")
        assert rev["ok"] and rev["reverted_to"] == 0.15
        assert await optimizer.get_param(db, "allocation.exploration") == 0.15
    _run(go())


# ------------------------------------------------------------------ live effect
def test_tuned_exploration_reaches_allocator():
    async def go():
        db = await _fresh_session()
        await optimizer.propose(db, "allocation.exploration", 0.25, reason="more explore")
        plan = await allocation_engine.plan_day(db, total=1000)
        assert plan["exploration"] == 0.25          # the governor's value is in effect
    _run(go())


# ------------------------------------------------------------------ recommend
def test_recommend_explores_early_exploits_late():
    async def go():
        db = await _fresh_session()
        # no data → early stage → recommend MORE exploration
        recs = await optimizer.recommend(db)
        assert recs and recs[0]["proposed"] > recs[0]["current"]
        # lots of data → recommend LESS exploration (exploit)
        await _seed(db, "NXG", "reply", "qualified", 250)
        recs2 = await optimizer.recommend(db)
        assert recs2 and recs2[0]["proposed"] < recs2[0]["current"]
    _run(go())


# ------------------------------------------------------------------ North-Star gate
def test_gate_rolls_back_a_regression():
    async def go():
        db = await _fresh_session()
        # establish a healthy metric, then apply a change at that high metric
        await _seed(db, "NXG", "reply", "qualified", 10)     # qpk = 1000
        await optimizer.propose(db, "allocation.exploration", 0.20, reason="try")
        # now the metric collapses (lots of non-qualifying touchpoints)
        await _seed(db, "NXG", "reply", "none", 990)          # qpk drops sharply
        actions = await optimizer.evaluate_and_rollback(db)
        assert any(a["key"] == "allocation.exploration" and a["action"] == "reverted"
                   for a in actions)
        assert await optimizer.get_param(db, "allocation.exploration") == 0.15  # rolled back
    _run(go())


def test_auto_tune_cycle_runs():
    async def go():
        db = await _fresh_session()
        out = await optimizer.auto_tune(db, apply=True)
        assert "recommendations" in out and "rolled_back" in out
        # early stage recommendation applied → exploration increased
        assert await optimizer.get_param(db, "allocation.exploration") >= 0.15
    _run(go())


def _run_all():
    import inspect
    fns = [v for k, v in sorted(globals().items())
           if k.startswith("test_") and inspect.isfunction(v)]
    passed = 0
    for fn in fns:
        fn()
        passed += 1
        print(f"  ok  {fn.__name__}")
    print(f"\n{passed}/{len(fns)} optimizer tests passed.")


if __name__ == "__main__":
    _run_all()
