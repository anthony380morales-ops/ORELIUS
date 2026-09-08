"""
Phase 13 tests — North-Star dashboard aggregation.

Runs against in-memory SQLite. Proves the snapshot composes the whole ecosystem
into one payload centered on the North Star, reflects live activity, and degrades
gracefully on an empty system.

Run with pytest, or directly:  python backend/tests/test_dashboard.py
"""
import asyncio

from sqlalchemy.pool import StaticPool
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from app.database import Base
from app.orchestration.dashboard import dashboard
from app.orchestration.analytics import analytics
from app.orchestration.flags import flags
from app.orchestration.mission import validate_mission
from app.orchestration.mission_queue import mission_queue


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


def test_snapshot_shape_on_empty_system():
    async def go():
        db = await _fresh_session()
        snap = await dashboard.snapshot(db)
        # all top-level sections present even with no data
        for key in ("north_star", "flags", "queue", "pending", "allocation",
                    "performance_by_action", "optimizer", "executors", "agents"):
            assert key in snap, key
        ns = snap["north_star"]
        assert ns["value"] == 0.0 and ns["touchpoints"] == 0
        assert ns["metric"].startswith("qualified_conversations_per_1000")
        assert snap["mode"] == "simulation"
        # a fresh (computed) allocation plan is shown when no snapshot is stored
        assert snap["allocation"].get("computed") is True
        # agent coverage is reported
        assert snap["agents"]["implemented"] >= 8 and snap["agents"]["total"] >= 10
    _run(go())


def test_snapshot_reflects_activity():
    async def go():
        db = await _fresh_session()
        # seed touchpoints: 3 qualified of 15 total for NXG
        for _ in range(3):
            await analytics.record_touchpoint(db, brand="NXG", action="reply", outcome="qualified")
        for _ in range(12):
            await analytics.record_touchpoint(db, brand="NXG", action="reply", outcome="meaningful")
        # a blocked mission → one pending approval
        p = validate_mission({"brand": "NXG", "platform": "facebook",
                              "objective": "content_publish", "topic": {"title": "t"}})
        await mission_queue.enqueue(db, p)

        snap = await dashboard.snapshot(db)
        assert snap["north_star"]["touchpoints"] == 15
        assert snap["north_star"]["qualified"] == 3
        assert snap["north_star"]["value"] == 200.0            # 3/15 * 1000
        assert snap["north_star"]["by_brand"]["NXG"]["qualified"] == 3
        assert snap["pending"]["approvals"] == 1
        assert "reply" in snap["performance_by_action"]
    _run(go())


def test_snapshot_shows_paused_flags():
    async def go():
        db = await _fresh_session()
        await flags.set(db, "MESSAGING_PAUSE", True)
        snap = await dashboard.snapshot(db)
        assert snap["any_paused"] is True
        assert snap["flags"]["MESSAGING_PAUSE"] is True
    _run(go())


def test_snapshot_target_progress():
    async def go():
        db = await _fresh_session()
        snap = await dashboard.snapshot(db)
        ns = snap["north_star"]
        assert ns["daily_touchpoint_target"] >= 1000
        assert 0.0 <= ns["target_progress"] <= 1.0
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
    print(f"\n{passed}/{len(fns)} dashboard tests passed.")


if __name__ == "__main__":
    _run_all()
