"""
Phase 1 orchestration tests — pure, no DB/network/model calls.

Run with pytest, or directly:  python backend/tests/test_orchestration.py
"""
from app.orchestration.mission import (
    MissionPacket, Brand, Platform, Objective, ComplianceStatus, MissionStatus,
    validate_mission, TouchpointAction,
)
from app.orchestration.messaging_policy import (
    contains_forbidden_dashes, sanitize_message, validate_autonomous_message, enforce,
)
from app.orchestration.agent_registry import agent_registry


# ------------------------------------------------------------------ mission packet
def test_mission_minimal_valid():
    m = validate_mission({"brand": "NXG", "platform": "facebook",
                          "objective": "qualified_conversation"})
    assert m.brand == Brand.NXG
    assert m.platform == Platform.FACEBOOK
    assert m.mission_id.startswith("NXG-")
    assert m.expires_at is not None                     # default expiry applied
    assert not m.is_ready_for_executor()                # compliance pending → blocked


def test_mission_ready_only_when_compliance_approved():
    m = validate_mission({
        "brand": "IBC", "platform": "instagram", "objective": "content_publish",
        "compliance": {"status": "approved", "review_id": "rv1"},
        "actions": ["content_distribution"], "touchpoint_budget": 10,
    })
    assert m.is_ready_for_executor()
    assert TouchpointAction.CONTENT_DISTRIBUTION in m.actions


def test_mission_rejects_bad_enum():
    try:
        validate_mission({"brand": "ACME", "platform": "facebook", "objective": "x"})
    except Exception:
        return
    raise AssertionError("malformed mission should have raised")


def test_mission_status_enum_complete():
    for s in ("CREATED", "QUEUED", "RUNNING", "BLOCKED", "COMPLETED", "ESCALATED", "EXPIRED"):
        assert MissionStatus(s)


# ---------------------------------------------------------------- messaging policy
def test_double_dash_is_forbidden():
    bad = "Hey there, quick thought -- your retirement timeline matters."
    assert contains_forbidden_dashes(bad)
    v = validate_autonomous_message(bad)
    assert v["needs_regen"] is True
    assert "contains_double_dash" in v["issues"]
    # backstop: enforce() must never return "--"
    safe, _ = enforce(bad)
    assert "--" not in safe
    assert safe == "Hey there, quick thought, your retirement timeline matters."


def test_em_dash_is_allowed():
    ok = "Congrats on the new place — that's a big step."
    assert not contains_forbidden_dashes(ok)
    assert validate_autonomous_message(ok)["ok"] is True


def test_sanitize_various_dash_runs():
    assert "--" not in sanitize_message("a -- b")
    assert "--" not in sanitize_message("a---b")
    assert "--" not in sanitize_message("wrap-up -- next")


def test_canned_and_urgency_flagged():
    v = validate_autonomous_message("Just checking in! Act now, limited time only!!")
    assert v["ok"] is False
    assert any(i.startswith("canned_sales_phrase") for i in v["issues"])
    assert any(i.startswith("manufactured_urgency") for i in v["issues"])
    assert v["needs_regen"] is True                      # urgency is a hard trigger


def test_too_many_questions_flagged():
    v = validate_autonomous_message("What's your goal? When? Why? How much?")
    assert "too_many_questions" in v["issues"]


def test_natural_message_passes():
    v = validate_autonomous_message("that's a good point. what got you thinking about it?")
    assert v["ok"] is True and v["needs_regen"] is False


# ---------------------------------------------------------------- agent registry
def test_registry_has_standard_roster():
    ids = {a.id for a in agent_registry.all()}
    for required in ("economic_intelligence", "compliance_risk", "allocation",
                     "conversation_strategist", "content_strategist"):
        assert required in ids


def test_registry_select_prefers_implemented():
    spec = agent_registry.select("economic_research")
    assert spec is not None and spec.id == "economic_intelligence"
    assert spec.implemented is True


def _run_all():
    import inspect
    fns = [v for k, v in sorted(globals().items())
           if k.startswith("test_") and inspect.isfunction(v)]
    passed = 0
    for fn in fns:
        fn()
        passed += 1
        print(f"  ok  {fn.__name__}")
    print(f"\n{passed}/{len(fns)} orchestration tests passed.")


if __name__ == "__main__":
    _run_all()
