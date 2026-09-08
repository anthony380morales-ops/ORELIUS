"""
Phase 5 tests — LUCIUS control surface + notification adapter.

The status/pause/resume/approval/handoff flows run against an in-memory aiosqlite
engine in the default simulation mode, so nothing real is ever dispatched. Owner
alerts (LUCIUS notify) are written to shared memory but never gated.

Run with pytest, or directly:  python backend/tests/test_control.py
"""
import asyncio

from sqlalchemy.pool import StaticPool
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from app.database import Base
from app.orchestration.mission import validate_mission, MissionStatus
from app.orchestration.mission_queue import mission_queue
from app.orchestration.control import control_surface, resolve_scope
from app.orchestration.adapters import lucius_adapter
from app.orchestration.flags import flags


# ------------------------------------------------------------------ pure: scopes
def test_resolve_scope_maps_voice_words():
    assert resolve_scope("everything") == "SYSTEM_PAUSE"
    assert resolve_scope("messaging") == "MESSAGING_PAUSE"
    assert resolve_scope("creative") == "HIGGBOT_PAUSE"
    assert resolve_scope("social") == "ATHENA_PAUSE"
    assert resolve_scope("NXG") == "NXG_PAUSE"           # case-insensitive
    assert resolve_scope("nonsense") is None


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
    import app.models.orchestration        # noqa: F401 — register orchestration tables
    import app.models.shared_memory        # noqa: F401 — register shared-memory table
    engine = create_async_engine(
        "sqlite+aiosqlite://", echo=False,
        poolclass=StaticPool, connect_args={"check_same_thread": False},
    )
    _ENGINES.append(engine)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)()


async def _approved_mission(db, objective="content_publish", brand="NXG",
                            platform="facebook", topic="t"):
    p = validate_mission({"brand": brand, "platform": platform, "objective": objective,
                          "topic": {"title": topic}, "compliance": {"status": "approved"}})
    await mission_queue.enqueue(db, p)
    return p


# ------------------------------------------------------------------ status
def test_status_snapshot_shape():
    async def go():
        db = await _fresh_session()
        snap = await control_surface.status(db)
        assert snap["mode"] == "simulation"                 # safe default
        assert snap["any_paused"] is False
        assert "queue" in snap and "athena" in snap["executors"]
        assert snap["pending_approvals"] == 0 and snap["pending_handoffs"] == 0
    _run(go())


# ------------------------------------------------------------------ pause/resume
def test_pause_and_resume_by_scope():
    async def go():
        db = await _fresh_session()
        out = await control_surface.pause(db, "messaging")
        assert out["ok"] and out["flag"] == "MESSAGING_PAUSE"
        assert await flags.get(db, "MESSAGING_PAUSE") is True
        snap = await control_surface.status(db)
        assert snap["any_paused"] is True
        # resume
        out2 = await control_surface.resume(db, "messaging")
        assert out2["ok"] and await flags.get(db, "MESSAGING_PAUSE") is False
    _run(go())


def test_pause_unknown_scope_is_rejected():
    async def go():
        db = await _fresh_session()
        out = await control_surface.pause(db, "banana")
        assert out["ok"] is False and out["reason"] == "unknown_scope"
    _run(go())


# ------------------------------------------------------------------ approvals
def test_pending_approvals_and_approve():
    async def go():
        db = await _fresh_session()
        # a blocked (compliance pending) mission shows up as a pending approval
        p = validate_mission({"brand": "NXG", "platform": "facebook",
                              "objective": "content_publish", "topic": {"title": "x"}})
        row = await mission_queue.enqueue(db, p)
        assert row.status == MissionStatus.BLOCKED.value
        approvals = await control_surface.pending_approvals(db)
        assert len(approvals) == 1 and approvals[0]["mission_id"] == p.mission_id
        # approve → leaves the queue, becomes runnable
        assert await control_surface.approve(db, p.mission_id) is True
        assert len(await control_surface.pending_approvals(db)) == 0
    _run(go())


# ------------------------------------------------------------------ handoffs
def test_handoff_queue_and_resolve():
    async def go():
        db = await _fresh_session()
        # an escalated mission is a pending handoff
        p = await _approved_mission(db, objective="qualified_conversation",
                                    platform="instagram", brand="IBC")
        await mission_queue.escalate(db, p.mission_id, reason="high intent lead")
        handoffs = await control_surface.pending_handoffs(db)
        assert len(handoffs) == 1 and handoffs[0]["mission_id"] == p.mission_id
        # owner takes it → resolved/completed, leaves the queue
        assert await control_surface.resolve_handoff(db, p.mission_id, note="called them") is True
        assert len(await control_surface.pending_handoffs(db)) == 0
        row = await mission_queue.get(db, p.mission_id)
        assert row.status == MissionStatus.COMPLETED.value
    _run(go())


def test_explicit_human_handoff_objective_is_listed():
    async def go():
        db = await _fresh_session()
        p = await _approved_mission(db, objective="human_handoff", topic="hot lead")
        handoffs = await control_surface.pending_handoffs(db)
        assert any(h["mission_id"] == p.mission_id for h in handoffs)
    _run(go())


# ------------------------------------------------------------------ LUCIUS alerts
def test_lucius_notify_is_never_gated():
    async def go():
        db = await _fresh_session()
        # even with the whole system paused, an owner alert still goes out
        await flags.set(db, "SYSTEM_PAUSE", True)
        out = await lucius_adapter.request_approval(db, "NXG-2026-ABCD", reason="needs review")
        assert out["ok"] is True and out["urgency"] == "high"
        # it landed on the shared-memory bus for LUCIUS to voice
        from app.core.shared_memory import shared_memory
        events = await shared_memory.recall(db, limit=10)
        assert any(e["kind"] == "approval_request" for e in events)
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
    print(f"\n{passed}/{len(fns)} control-surface tests passed.")


if __name__ == "__main__":
    _run_all()
