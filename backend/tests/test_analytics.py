"""
Phase 11 tests — performance feedback + analytics, and the closed loop into allocation.

Runs against in-memory SQLite. Proves rollup produces the North-Star ratio, the
per-action performance signal is well-formed, recorded outcomes actually bend the
allocation split, and the conversation engine emits touchpoints.

Run with pytest, or directly:  python backend/tests/test_analytics.py
"""
import asyncio

from sqlalchemy.pool import StaticPool
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from app.database import Base
from app.orchestration.analytics import analytics, qualified_per_1k
from app.orchestration.allocation import allocation_engine
from app.orchestration.conversation_engine import conversation_engine


# ------------------------------------------------------------------ pure
def test_qualified_per_1k():
    assert qualified_per_1k(5, 1000) == 5.0
    assert qualified_per_1k(0, 0) == 0.0


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
    import app.models.shared_memory  # noqa: F401
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


# ------------------------------------------------------------------ rollup
def test_rollup_computes_north_star():
    async def go():
        db = await _fresh_session()
        await _seed(db, "NXG", "reply", "qualified", 3)
        await _seed(db, "NXG", "reply", "meaningful", 7)
        await _seed(db, "NXG", "meaningful_comment", "none", 5)
        roll = await analytics.rollup(db, brand="NXG")
        assert roll["touchpoints"] == 15
        assert roll["qualified"] == 3
        assert roll["meaningful"] == 10          # 3 qualified + 7 meaningful
        assert roll["qualified_per_1k"] == qualified_per_1k(3, 15)
        assert roll["by_action"]["reply"]["qualified"] == 3
    _run(go())


def test_rollup_empty_is_zero():
    async def go():
        db = await _fresh_session()
        roll = await analytics.rollup(db)
        assert roll["touchpoints"] == 0 and roll["qualified_per_1k"] == 0.0
    _run(go())


# ------------------------------------------------------------------ performance signal
def test_performance_weights_none_without_data():
    async def go():
        db = await _fresh_session()
        assert await analytics.performance_weights(db, "NXG") is None
    _run(go())


def test_performance_weights_rank_by_qualified_rate():
    async def go():
        db = await _fresh_session()
        # reply qualifies often; meaningful_comment rarely
        await _seed(db, "NXG", "reply", "qualified", 8)
        await _seed(db, "NXG", "reply", "meaningful", 2)
        await _seed(db, "NXG", "meaningful_comment", "none", 10)
        w = await analytics.performance_weights(db, "NXG")
        assert w["reply"] > w["meaningful_comment"]      # winner scores higher
        assert w["meaningful_comment"] > 0               # smoothed, never exactly 0
    _run(go())


# ------------------------------------------------------------------ closed loop
def test_recorded_outcomes_bend_allocation():
    async def go():
        db = await _fresh_session()
        # NXG's content_distribution qualifies strongly; nothing else recorded
        await _seed(db, "NXG", "content_distribution", "qualified", 20)
        weights = await analytics.performance_provider(db)
        assert "NXG" in weights
        perf = lambda b: weights.get(b.value)            # noqa: E731
        plan = await allocation_engine.plan_day(db, total=1000, perf_provider=perf)
        nxg = plan["plan"]["NXG"]
        # content_distribution should now lead NXG's action split
        assert max(nxg, key=nxg.get) == "content_distribution"
        assert plan["inputs"]["NXG"]["used_performance"] is True
    _run(go())


# ------------------------------------------------------------------ engine emits touchpoints
def test_conversation_engine_emits_touchpoint():
    async def go():
        db = await _fresh_session()
        out = await conversation_engine.handle_inbound(
            db, prospect_id="c1", brand="NXG", platform="facebook",
            message="tell me more about this")
        assert out["touchpoint_outcome"] == "meaningful"
        roll = await analytics.rollup(db, brand="NXG")
        assert roll["touchpoints"] == 1 and roll["by_action"]["reply"]["meaningful"] == 1
    _run(go())


def test_conversation_high_intent_records_qualified():
    async def go():
        db = await _fresh_session()
        out = await conversation_engine.handle_inbound(
            db, prospect_id="c2", brand="IBC", platform="instagram",
            message="how much? ready to get started")
        assert out["touchpoint_outcome"] == "qualified"
        roll = await analytics.rollup(db, brand="IBC")
        assert roll["qualified"] == 1
    _run(go())


# ------------------------------------------------------------------ mission evaluation
def test_evaluate_mission_records_on_row():
    async def go():
        db = await _fresh_session()
        from app.orchestration.mission import validate_mission
        from app.orchestration.mission_queue import mission_queue
        p = validate_mission({"brand": "NXG", "platform": "facebook",
                              "objective": "content_publish", "topic": {"title": "t"},
                              "compliance": {"status": "approved"}})
        await mission_queue.enqueue(db, p)
        out = await analytics.evaluate_mission(db, p.mission_id, qualified=2, touchpoints=400)
        assert out["ok"] and out["evaluation"]["qualified_per_1k"] == qualified_per_1k(2, 400)
        row = await mission_queue.get(db, p.mission_id)
        assert row.result["evaluation"]["qualified"] == 2
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
    print(f"\n{passed}/{len(fns)} analytics tests passed.")


if __name__ == "__main__":
    _run_all()
