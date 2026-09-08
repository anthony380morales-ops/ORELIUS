"""
Phase 2 (mission queue) + Phase 3 (ATHENA adapter) tests.

Pure helpers run with no DB. The async queue + adapter flows run against an
in-memory aiosqlite engine so they exercise real SQLAlchemy without touching
Postgres or the network.

Run with pytest, or directly:  python backend/tests/test_mission_queue.py
"""
import asyncio

from sqlalchemy.pool import StaticPool
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from app.database import Base
from app.orchestration.mission import validate_mission, MissionStatus
from app.orchestration.mission_queue import (
    mission_queue, priority_rank, backoff_seconds, dedup_key_for,
)
from app.orchestration.adapters import athena_adapter
from app.orchestration.adapters.athena_adapter import translate


# ------------------------------------------------------------------ pure helpers
def test_priority_rank_ordering():
    assert priority_rank("urgent") < priority_rank("high") < priority_rank("medium") < priority_rank("low")
    assert priority_rank(None) == priority_rank("medium")    # default
    assert priority_rank("bogus") == 2                       # unknown → medium


def test_backoff_is_exponential_and_capped():
    assert backoff_seconds(1) == 30
    assert backoff_seconds(2) == 60
    assert backoff_seconds(3) == 120
    assert backoff_seconds(0) == 30                          # clamped to attempt 1
    assert backoff_seconds(99) == 3600                       # capped


def test_dedup_key_stable_and_intent_specific():
    p = validate_mission({"brand": "NXG", "platform": "facebook",
                          "objective": "content_publish"})
    k1 = dedup_key_for(p)
    k2 = dedup_key_for(p)
    assert k1 == k2 and len(k1) == 32                        # deterministic
    q = validate_mission({"brand": "IBC", "platform": "facebook",
                          "objective": "content_publish"})
    assert dedup_key_for(q) != k1                            # different brand → different key


# ------------------------------------------------------------------ adapter (pure)
def test_translate_content_publish_is_instagram_post():
    p = validate_mission({"brand": "NXG", "platform": "instagram",
                          "objective": "content_publish",
                          "topic": {"title": "IUL basics"}})
    job = translate(p)
    assert job["kind"] == "instagram_post" and job["action"] == "once"
    assert "IUL basics" in job["request"]


def test_translate_engagement_has_no_direct_endpoint():
    p = validate_mission({"brand": "NXG", "platform": "instagram",
                          "objective": "engagement"})
    job = translate(p)
    assert job["kind"] is None                               # → messaging phase, not forced


# ------------------------------------------------------------------ async harness
_ENGINES: list = []


def _run(coro):
    async def _wrapped():
        try:
            await coro
        finally:
            # Dispose every engine opened during the test so aiosqlite's worker
            # threads are joined and the interpreter exits cleanly.
            for eng in _ENGINES:
                await eng.dispose()
            _ENGINES.clear()
    return asyncio.run(_wrapped())


async def _fresh_session() -> AsyncSession:
    """A brand-new in-memory DB with the orchestration tables created."""
    import app.models.orchestration  # noqa: F401 — register tables on Base
    # StaticPool reuses ONE connection so the in-memory DB (and its tables) persist
    # across the session's operations; disposal at end joins aiosqlite's thread.
    engine = create_async_engine(
        "sqlite+aiosqlite://", echo=False,
        poolclass=StaticPool, connect_args={"check_same_thread": False},
    )
    _ENGINES.append(engine)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    return maker()


def test_enqueue_blocks_until_compliance_approved():
    async def go():
        db = await _fresh_session()
        p = validate_mission({"brand": "NXG", "platform": "facebook",
                              "objective": "content_publish"})
        row = await mission_queue.enqueue(db, p)
        assert row.status == MissionStatus.BLOCKED.value     # compliance pending
        # approve → becomes runnable
        assert await mission_queue.approve(db, p.mission_id) is True
        row2 = await mission_queue.get(db, p.mission_id)
        assert row2.status == MissionStatus.QUEUED.value
    _run(go())


def test_enqueue_approved_goes_straight_to_queued():
    async def go():
        db = await _fresh_session()
        p = validate_mission({"brand": "NXG", "platform": "instagram",
                              "objective": "content_publish",
                              "compliance": {"status": "approved"}})
        row = await mission_queue.enqueue(db, p)
        assert row.status == MissionStatus.QUEUED.value
    _run(go())


def test_dedup_returns_same_active_mission():
    async def go():
        db = await _fresh_session()
        base = {"brand": "NXG", "platform": "facebook", "objective": "content_publish",
                "compliance": {"status": "approved"}}
        p1 = validate_mission(dict(base))
        p2 = validate_mission(dict(base))
        r1 = await mission_queue.enqueue(db, p1)
        r2 = await mission_queue.enqueue(db, p2)
        assert r1.mission_id == r2.mission_id                # dedup hit, not a 2nd row
        assert (await mission_queue.stats(db))["total"] == 1
    _run(go())


def test_claim_orders_by_priority():
    async def go():
        db = await _fresh_session()
        low = validate_mission({"brand": "NXG", "platform": "facebook",
                                "objective": "content_publish", "priority": "low",
                                "topic": {"title": "low"},
                                "compliance": {"status": "approved"}})
        urgent = validate_mission({"brand": "NXG", "platform": "facebook",
                                   "objective": "content_publish", "priority": "urgent",
                                   "topic": {"title": "urgent"},
                                   "compliance": {"status": "approved"}})
        await mission_queue.enqueue(db, low)
        await mission_queue.enqueue(db, urgent)
        claimed = await mission_queue.claim_next(db)
        assert claimed.mission_id == urgent.mission_id       # urgent wins
        assert claimed.status == MissionStatus.RUNNING.value
    _run(go())


def test_fail_requeues_with_backoff_then_dead_letters():
    async def go():
        db = await _fresh_session()
        p = validate_mission({"brand": "NXG", "platform": "facebook",
                              "objective": "content_publish",
                              "compliance": {"status": "approved"}})
        await mission_queue.enqueue(db, p)
        assert await mission_queue.fail(db, p.mission_id, "boom") == "requeued"
        row = await mission_queue.get(db, p.mission_id)
        assert row.status == MissionStatus.QUEUED.value
        assert row.next_attempt_at is not None               # backoff gate set
        assert await mission_queue.fail(db, p.mission_id, "boom") == "requeued"
        assert await mission_queue.fail(db, p.mission_id, "boom") == "dead_letter"
        row = await mission_queue.get(db, p.mission_id)
        assert row.status == MissionStatus.FAILED.value      # dead-letter after max
        assert row.attempts == 3
    _run(go())


def test_complete_and_cancel_and_retry():
    async def go():
        db = await _fresh_session()
        p = validate_mission({"brand": "NXG", "platform": "facebook",
                              "objective": "content_publish",
                              "compliance": {"status": "approved"}})
        await mission_queue.enqueue(db, p)
        await mission_queue.complete(db, p.mission_id, {"ok": True}, cost_usd=0.01)
        row = await mission_queue.get(db, p.mission_id)
        assert row.status == MissionStatus.COMPLETED.value and row.cost_usd == 0.01
        # completed is terminal → cancel is a no-op
        assert await mission_queue.cancel(db, p.mission_id) is False
        # a failed mission can be retried back to QUEUED
        q = validate_mission({"brand": "NXG", "platform": "facebook",
                              "objective": "engagement",
                              "compliance": {"status": "approved"}})
        await mission_queue.enqueue(db, q)
        await mission_queue.fail(db, q.mission_id, "x", retryable=False)
        assert (await mission_queue.get(db, q.mission_id)).status == MissionStatus.FAILED.value
        assert await mission_queue.retry(db, q.mission_id) is True
        assert (await mission_queue.get(db, q.mission_id)).status == MissionStatus.QUEUED.value
    _run(go())


def test_submit_mission_is_simulated_by_default():
    async def go():
        db = await _fresh_session()
        p = validate_mission({"brand": "NXG", "platform": "instagram",
                              "objective": "content_publish",
                              "topic": {"title": "IUL basics"},
                              "compliance": {"status": "approved"}})
        out = await athena_adapter.submit_mission(db, p)
        assert out["ok"] is True and out["simulated"] is True    # default mode = simulation
        assert out["would_dispatch"]["kind"] == "instagram_post"  # computed, not dispatched
    _run(go())


def test_submit_mission_blocked_without_compliance():
    async def go():
        db = await _fresh_session()
        p = validate_mission({"brand": "NXG", "platform": "instagram",
                              "objective": "content_publish"})
        out = await athena_adapter.submit_mission(db, p)
        assert out["ok"] is False and out["reason"] == "compliance_not_approved"
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
    print(f"\n{passed}/{len(fns)} mission-queue/adapter tests passed.")


if __name__ == "__main__":
    _run_all()
