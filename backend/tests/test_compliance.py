"""
Phase 9 tests — compliance/risk agent + the durable compliance gate.

Agent review logic is pure. The gate flow runs against in-memory SQLite and proves
a verdict actually MOVES a mission (release / escalate / stay blocked).

Run with pytest, or directly:  python backend/tests/test_compliance.py
"""
import asyncio

from sqlalchemy.pool import StaticPool
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from app.database import Base
from app.orchestration.mission import validate_mission, ComplianceStatus, MissionStatus
from app.orchestration.mission_queue import mission_queue
from app.orchestration.agents.compliance_risk import compliance_risk, scan_prohibited, scan_advice
from app.orchestration.compliance import compliance_engine


# ------------------------------------------------------------------ pure scanners
def test_scan_prohibited_catches_claims():
    assert scan_prohibited("This gives guaranteed returns every year")
    assert scan_prohibited("It is totally risk free")
    assert scan_prohibited("double your money fast")
    assert scan_prohibited("A steady educational overview of interest rates") == []


def test_scan_advice_catches_individualized():
    assert scan_advice("you should buy this whole life policy")
    assert scan_advice("the right policy for you is term")
    assert scan_advice("here is how interest rates work") == []


# ------------------------------------------------------------------ message review
def test_review_message_blocks_prohibited_and_double_dash():
    v1 = compliance_risk.review_message("guaranteed returns, no risk at all")
    assert v1.status == ComplianceStatus.BLOCKED
    v2 = compliance_risk.review_message("great point -- here is the thing")   # "--" hard rule
    assert v2.status == ComplianceStatus.BLOCKED


def test_review_message_needs_human_on_advice():
    v = compliance_risk.review_message("honestly you should buy this policy today")
    assert v.status == ComplianceStatus.NEEDS_HUMAN


def test_review_message_approves_clean():
    v = compliance_risk.review_message("that's a good question. what matters most to you right now?")
    assert v.status == ComplianceStatus.APPROVED and v.approved


# ------------------------------------------------------------------ mission review
def test_review_mission_approves_clean_education():
    p = validate_mission({"brand": "IBC", "platform": "instagram",
                          "objective": "content_publish",
                          "topic": {"title": "How interest rates affect your savings"}})
    assert compliance_risk.review_mission(p).status == ComplianceStatus.APPROVED


def test_review_mission_blocks_prohibited_claim():
    p = validate_mission({"brand": "NXG", "platform": "facebook",
                          "objective": "content_publish",
                          "topic": {"title": "This plan gives guaranteed returns"}})
    v = compliance_risk.review_mission(p)
    assert v.status == ComplianceStatus.BLOCKED and any("prohibited_claim" in r for r in v.reasons)


def test_review_mission_blocks_incomplete_publish():
    p = validate_mission({"brand": "NXG", "platform": "facebook",
                          "objective": "content_publish"})   # no topic
    v = compliance_risk.review_mission(p)
    assert v.status == ComplianceStatus.BLOCKED


def test_review_mission_human_handoff_needs_human():
    p = validate_mission({"brand": "NXG", "platform": "facebook", "objective": "human_handoff"})
    assert compliance_risk.review_mission(p).status == ComplianceStatus.NEEDS_HUMAN


# ------------------------------------------------------------------ gate (async DB)
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


async def _enqueue(db, packet_dict):
    p = validate_mission(packet_dict)
    row = await mission_queue.enqueue(db, p)   # PENDING compliance → BLOCKED
    return p, row


def test_gate_releases_clean_mission():
    async def go():
        db = await _fresh_session()
        p, row = await _enqueue(db, {"brand": "IBC", "platform": "instagram",
                                     "objective": "content_publish",
                                     "topic": {"title": "Understanding IUL basics"}})
        assert row.status == MissionStatus.BLOCKED.value
        out = await compliance_engine.review_mission_row(db, p.mission_id)
        assert out["verdict"]["status"] == "approved" and out["moved_to"] == "QUEUED"
        row2 = await mission_queue.get(db, p.mission_id)
        assert row2.status == MissionStatus.QUEUED.value
        # the packet is stamped approved for provenance
        assert row2.packet["compliance"]["status"] == "approved"
        assert row2.result["compliance"]["review_id"]
    _run(go())


def test_gate_escalates_needs_human():
    async def go():
        db = await _fresh_session()
        p, _ = await _enqueue(db, {"brand": "NXG", "platform": "facebook",
                                   "objective": "human_handoff"})
        out = await compliance_engine.review_mission_row(db, p.mission_id)
        assert out["verdict"]["status"] == "needs_human" and out["moved_to"] == "ESCALATED"
        row = await mission_queue.get(db, p.mission_id)
        assert row.status == MissionStatus.ESCALATED.value
    _run(go())


def test_gate_keeps_prohibited_blocked():
    async def go():
        db = await _fresh_session()
        p, _ = await _enqueue(db, {"brand": "NXG", "platform": "facebook",
                                   "objective": "content_publish",
                                   "topic": {"title": "risk free guaranteed returns"}})
        out = await compliance_engine.review_mission_row(db, p.mission_id)
        assert out["verdict"]["status"] == "blocked" and out["moved_to"] == "BLOCKED"
        row = await mission_queue.get(db, p.mission_id)
        assert row.status == MissionStatus.BLOCKED.value and row.error
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
    print(f"\n{passed}/{len(fns)} compliance tests passed.")


if __name__ == "__main__":
    _run_all()
