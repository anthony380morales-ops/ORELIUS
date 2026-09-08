"""
Phase 10 tests — touchpoint allocation engine.

Apportionment, weight blending, and the North-Star ratio are pure. The day planner
runs against in-memory SQLite so kill-switch handling and snapshotting are exercised.

Run with pytest, or directly:  python backend/tests/test_allocation.py
"""
import asyncio

from sqlalchemy.pool import StaticPool
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from app.database import Base
from app.orchestration.mission import Brand
from app.orchestration.allocation import (
    apportion, blend_weights, qualified_per_1k, allocation_engine,
)
from app.orchestration.flags import flags
from app.config import settings


# ------------------------------------------------------------------ pure: apportion
def test_apportion_sums_exactly():
    out = apportion(1050, {"a": 1, "b": 1, "c": 1})
    assert sum(out.values()) == 1050              # exact, no rounding drift
    assert max(out.values()) - min(out.values()) <= 1   # evenly split


def test_apportion_proportional():
    out = apportion(100, {"big": 3, "small": 1})
    assert out["big"] == 75 and out["small"] == 25
    assert sum(out.values()) == 100


def test_apportion_zero_and_empty_weights():
    assert apportion(0, {"a": 1}) == {"a": 0}
    assert apportion(100, {"a": 0, "b": 0}) == {"a": 0, "b": 0}


# ------------------------------------------------------------------ pure: blend
def test_blend_without_perf_is_baseline():
    baseline = {"x": 3, "y": 1}
    w = blend_weights(baseline, None)
    assert round(w["x"], 3) == 0.75 and round(w["y"], 3) == 0.25


def test_blend_with_perf_favors_winner_but_keeps_floor():
    baseline = {"x": 1, "y": 1, "z": 1}
    perf = {"x": 1.0, "y": 0.0, "z": 0.0}      # x is the clear performer
    w = blend_weights(baseline, perf, exploration=0.15)
    assert w["x"] > w["y"] and w["x"] > w["z"]  # winner gets more
    assert w["y"] > 0 and w["z"] > 0            # exploration floor — nothing starves
    assert abs(sum(w.values()) - 1.0) < 1e-9


def test_qualified_per_1k():
    assert qualified_per_1k(5, 1000) == 5.0
    assert qualified_per_1k(3, 600) == 5.0
    assert qualified_per_1k(1, 0) == 0.0        # no divide-by-zero


# ------------------------------------------------------------------ async harness
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


# ------------------------------------------------------------------ day planner
def test_plan_day_splits_across_brands_to_target():
    async def go():
        db = await _fresh_session()
        plan = await allocation_engine.plan_day(db, total=1000)
        assert plan["planned_total"] == 1000                       # exact
        assert set(plan["plan"].keys()) == {"NXG", "IBC"}
        # each brand's action allocations sum to its brand total
        for b, actions in plan["plan"].items():
            assert sum(actions.values()) == plan["brand_totals"][b]
        # IBC baseline (600) > NXG (430) → IBC gets the larger share
        assert plan["brand_totals"]["IBC"] > plan["brand_totals"]["NXG"]
    _run(go())


def test_plan_day_zeroes_paused_brand():
    async def go():
        db = await _fresh_session()
        await flags.set(db, "NXG_PAUSE", True)
        plan = await allocation_engine.plan_day(db, total=1000)
        assert plan["brand_totals"]["NXG"] == 0
        assert sum(plan["plan"]["NXG"].values()) == 0
        assert plan["brand_totals"]["IBC"] == 1000                 # all to active brand
    _run(go())


def test_plan_day_system_pause_zeroes_all():
    async def go():
        db = await _fresh_session()
        await flags.set(db, "SYSTEM_PAUSE", True)
        plan = await allocation_engine.plan_day(db, total=1000)
        assert plan["planned_total"] == 0
        assert "paused" in plan["note"]
        assert plan["mode"] == "simulation"                        # system pause forces sim
    _run(go())


def test_plan_uses_performance_provider():
    async def go():
        db = await _fresh_session()
        # steer everything toward content_distribution for both brands
        def perf(brand):
            return {"content_distribution": 1.0}
        plan = await allocation_engine.plan_day(db, total=1000, perf_provider=perf)
        for b, actions in plan["plan"].items():
            top = max(actions, key=actions.get)
            assert top == "content_distribution"                   # winner leads
            assert plan["inputs"][b]["used_performance"] is True
    _run(go())


def test_plan_and_store_then_latest():
    async def go():
        db = await _fresh_session()
        stored = await allocation_engine.plan_and_store(db, total=500)
        assert stored["snapshot_id"] is not None
        latest = await allocation_engine.latest(db)
        assert latest and latest["total"] == stored["planned_total"] == 500
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
    print(f"\n{passed}/{len(fns)} allocation tests passed.")


if __name__ == "__main__":
    _run_all()
