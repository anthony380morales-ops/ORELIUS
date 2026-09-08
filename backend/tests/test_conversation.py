"""
Phase 8 tests — conversation state machine + strategist + prospect memory + engine.

Pure state-machine and strategist logic run with no DB. The engine flow runs
against in-memory SQLite. The strategist NEVER calls a model here (deterministic
template path), and the absolute "--" rule is asserted directly.

Run with pytest, or directly:  python backend/tests/test_conversation.py
"""
import asyncio

from sqlalchemy.pool import StaticPool
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from app.database import Base
from app.orchestration.mission import ConversationStage
from app.orchestration.conversation import (
    classify_signal, next_stage, recommend_action, requires_human,
    can_transition, TERMINAL_STAGES,
)
from app.orchestration.agents.conversation_strategist import conversation_strategist
from app.orchestration.conversation_engine import conversation_engine
from app.orchestration.prospects import prospect_memory


# ------------------------------------------------------------------ state machine
def test_classify_signal():
    assert classify_signal("please stop messaging me") == "stop"
    assert classify_signal("how much does it cost?") == "high_intent"
    assert classify_signal("this is too expensive") == "objection"
    assert classify_signal("tell me more about this") == "interest"
    assert classify_signal("what does that mean?") == "question"
    assert classify_signal("ok") == "neutral"
    assert classify_signal("") == "empty"


def test_requires_human_on_high_intent_and_advice():
    assert requires_human("high_intent", "how much?") is True
    assert requires_human("question", "which policy is right for me?") is True   # licensed advice
    assert requires_human("question", "what time is it?") is False


def test_next_stage_progresses_and_stops():
    assert next_stage(ConversationStage.NEW, "interest") == ConversationStage.ENGAGED
    assert next_stage(ConversationStage.OPEN, "question") == ConversationStage.DISCOVERY
    assert next_stage(ConversationStage.ENGAGED, "stop") == ConversationStage.DO_NOT_CONTACT
    # terminal never advances
    assert next_stage(ConversationStage.DO_NOT_CONTACT, "interest") == ConversationStage.DO_NOT_CONTACT
    # objection routes to nurture
    assert next_stage(ConversationStage.DISCOVERY, "objection") == ConversationStage.NURTURE


def test_can_transition_and_optout_always_allowed():
    assert can_transition(ConversationStage.OPEN, ConversationStage.DISCOVERY) is True
    assert can_transition(ConversationStage.NEW, ConversationStage.QUALIFIED) is False
    assert can_transition(ConversationStage.OPEN, ConversationStage.DO_NOT_CONTACT) is True


def test_recommend_action():
    assert recommend_action(ConversationStage.OPEN, "neutral") == "ask_discovery_question"
    assert recommend_action(ConversationStage.NEW, "high_intent") == "route_to_human"
    assert recommend_action(ConversationStage.OPEN, "stop") == "honor_opt_out"


# ------------------------------------------------------------- strategist (async, no model)
def _run(coro):
    return asyncio.run(coro)


def test_strategist_drafts_are_policy_safe_and_never_double_dash():
    async def go():
        for sig_msg in ["tell me more", "what does that mean?", "this is too expensive", "ok sounds good"]:
            d = await conversation_strategist.decide(
                prospect_id="p1", current_stage="open", inbound_message=sig_msg)
            assert d.draft_message is not None
            assert "--" not in d.draft_message          # ABSOLUTE rule
            assert d.message_ok is True                  # passes the full policy
            assert d.sent is False                       # never sends
    _run(go())


def test_strategist_routes_high_intent_to_human_no_message():
    async def go():
        d = await conversation_strategist.decide(
            prospect_id="p2", current_stage="discovery", inbound_message="how much is it? I'm ready")
        assert d.needs_human is True
        assert d.action == "route_to_human"
        assert d.draft_message is None                   # never auto-advise
    _run(go())


def test_strategist_honors_optout():
    async def go():
        d = await conversation_strategist.decide(
            prospect_id="p3", current_stage="engaged", inbound_message="stop, not interested")
        assert d.next_stage == ConversationStage.DO_NOT_CONTACT.value
        assert d.draft_message is None
    _run(go())


def test_strategist_enforces_even_a_bad_drafter():
    async def go():
        # a drafter that returns a policy-violating message with the forbidden seq
        async def bad_drafter(system, prompt):
            return "Act now -- limited time only!! this is your last chance"
        d = await conversation_strategist.decide(
            prospect_id="p4", current_stage="open", inbound_message="tell me more",
            drafter=bad_drafter)
        assert "--" not in (d.draft_message or "")       # backstop cleaned it
        assert d.message_ok is True                       # fell back to a clean template
    _run(go())


# ------------------------------------------------------------------ engine (async DB)
_ENGINES: list = []


def _run_db(coro):
    async def _wrapped():
        try:
            await coro
        finally:
            for eng in _ENGINES:
                await eng.dispose()
            _ENGINES.clear()
    return asyncio.run(_wrapped())


async def _fresh_session() -> AsyncSession:
    import app.models.orchestration        # noqa: F401
    import app.models.shared_memory        # noqa: F401
    engine = create_async_engine(
        "sqlite+aiosqlite://", echo=False,
        poolclass=StaticPool, connect_args={"check_same_thread": False},
    )
    _ENGINES.append(engine)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)()


def test_engine_persists_and_advances_stage():
    async def go():
        db = await _fresh_session()
        out = await conversation_engine.handle_inbound(
            db, prospect_id="lead-1", brand="NXG", platform="facebook",
            message="tell me more about this", concern="retirement income")
        assert out["ok"] and out["draft_message"] and "--" not in out["draft_message"]
        row = await prospect_memory.get(db, "lead-1")
        assert row.stage == ConversationStage.ENGAGED.value     # NEW + interest → engaged
        # both the inbound and the agent draft are in bounded history
        roles = [t["role"] for t in row.turns]
        assert "prospect" in roles and "agent_draft" in roles
    _run_db(go())


def test_engine_optout_then_suppresses():
    async def go():
        db = await _fresh_session()
        await conversation_engine.handle_inbound(
            db, prospect_id="lead-2", brand="IBC", platform="instagram",
            message="please stop")
        row = await prospect_memory.get(db, "lead-2")
        assert row.do_not_contact is True
        # a later inbound is suppressed, no draft
        out2 = await conversation_engine.handle_inbound(
            db, prospect_id="lead-2", brand="IBC", platform="instagram",
            message="actually tell me more")
        assert out2["action"] == "suppressed" and out2["draft_message"] is None
    _run_db(go())


def test_engine_high_intent_alerts_lucius():
    async def go():
        db = await _fresh_session()
        out = await conversation_engine.handle_inbound(
            db, prospect_id="lead-3", brand="NXG", platform="facebook",
            message="how much does it cost? ready to sign up")
        assert out["needs_human"] is True and out["draft_message"] is None
        # a handoff alert landed on the shared-memory bus for LUCIUS
        from app.core.shared_memory import shared_memory
        events = await shared_memory.recall(db, limit=10)
        assert any(e["kind"] == "handoff_alert" for e in events)
    _run_db(go())


def _run_all():
    import inspect
    fns = [v for k, v in sorted(globals().items())
           if k.startswith("test_") and inspect.isfunction(v)]
    passed = 0
    for fn in fns:
        fn()
        passed += 1
        print(f"  ok  {fn.__name__}")
    print(f"\n{passed}/{len(fns)} conversation tests passed.")


if __name__ == "__main__":
    _run_all()
