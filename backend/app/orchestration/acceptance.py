"""
End-to-end simulation acceptance harness (directive §69).

Drives the WHOLE loop in simulation with a synthetic, credential-free intelligence
seed — no network, no model call, no real dispatch — and asserts every safety
invariant holds before any live provider exists:

  intelligence seed → impact angles → audience → content missions (held on
  compliance) → compliance gate → queue claim → executor adapters (simulated) →
  conversation turns (policy-safe, no "--") → outcomes → allocation (kill-switch
  aware) → optimizer → dashboard.

Returns a structured checklist so it can be a CI gate, an ops button, and a test.
Nothing here performs a real outbound action; a check explicitly proves that.
"""
from __future__ import annotations

from typing import Dict, List

from sqlalchemy.ext.asyncio import AsyncSession

from ..utils.logger import logger
from .mission import validate_mission, MissionStatus, ComplianceStatus, Brand
from .mission_queue import mission_queue
from .agents.economic_intelligence import signals_from_package
from .agents.financial_impact import financial_impact
from .agents.audience_intelligence import audience_intelligence
from .planner import build_content_missions
from .compliance import compliance_engine
from .adapters import athena_adapter, higgbot_adapter
from .conversation_engine import conversation_engine
from .analytics import analytics
from .allocation import allocation_engine
from .optimizer import optimizer
from .dashboard import dashboard
from .flags import flags
from .messaging_policy import contains_forbidden_dashes

# A synthetic compiled-intel package (what hot_topic would produce), so the whole
# run is deterministic and needs no credentials.
_SEED_PACKAGE = {
    "facts": [
        "Interest rates held steady while inflation eased toward 3 percent",
        "US household savings rates ticked up this quarter",
        "Bond yields stayed elevated versus last year",
    ],
    "caption": "Here is what the economy signals about protecting and growing your money.",
    "post_idea": "Explain in plain language why rates matter for life insurance and savings.",
    "created_at": "2026-09-08T00:00:00Z",
}


class AcceptanceHarness:
    async def run(self, db: AsyncSession) -> Dict:
        checks: List[Dict] = []

        def check(name: str, ok: bool, detail: str = ""):
            checks.append({"name": name, "ok": bool(ok), "detail": detail})

        # 0) Simulation is the default posture.
        mode = await flags.mode(db)
        check("mode_is_simulation", mode.value == "simulation", f"mode={mode.value}")

        # 1) Intelligence seed → signals → impact angles.
        signals = signals_from_package(_SEED_PACKAGE)
        angles = financial_impact.assess(signals, Brand.IBC)
        check("intelligence_produces_signals", len(signals) == 3, f"{len(signals)} signals")
        check("impact_ranks_angles", len(angles) == 3 and
              angles[0].opportunity_score >= angles[-1].opportunity_score,
              "angles ranked by score")

        # 2) Audience + content missions (held on compliance).
        insight = await audience_intelligence.profile(db, Brand.IBC)
        missions = build_content_missions(signals, angles, Brand.IBC, audience=insight)
        held = all(m.compliance.status == ComplianceStatus.PENDING for m in missions)
        check("missions_start_held_on_compliance", held and len(missions) == 3,
              f"{len(missions)} missions, all PENDING")

        # 3) Enqueue → BLOCKED, then compliance gate releases the clean ones.
        first = missions[0]
        await mission_queue.enqueue(db, first, executor="athena")
        # snapshot the status string now — the ORM row is mutated in place by the gate
        status_before = (await mission_queue.get(db, first.mission_id)).status
        gate = await compliance_engine.review_mission_row(db, first.mission_id)
        status_after = (await mission_queue.get(db, first.mission_id)).status
        check("compliance_gate_releases_clean",
              status_before == MissionStatus.BLOCKED.value
              and gate["verdict"]["status"] == "approved"
              and status_after == MissionStatus.QUEUED.value,
              f"{status_before} -> {status_after}")

        # 4) A prohibited-claim mission is BLOCKED by the gate.
        bad = validate_mission({"brand": "NXG", "platform": "facebook",
                                "objective": "content_publish",
                                "topic": {"title": "guaranteed returns, risk free"}})
        await mission_queue.enqueue(db, bad, executor="athena")
        bad_gate = await compliance_engine.review_mission_row(db, bad.mission_id)
        check("compliance_blocks_prohibited_claim",
              bad_gate["verdict"]["status"] == "blocked",
              f"verdict={bad_gate['verdict']['status']}")

        # 5) Queue claim → RUNNING.
        claimed = await mission_queue.claim_next(db, executor="athena")
        check("queue_claims_approved_mission",
              claimed is not None and claimed.status == MissionStatus.RUNNING.value,
              f"claimed={getattr(claimed, 'mission_id', None)}")

        # 6) Executor adapters simulate — NOTHING real is dispatched.
        approved = validate_mission({"brand": "IBC", "platform": "instagram",
                                     "objective": "content_publish",
                                     "topic": {"title": "IUL basics"},
                                     "creative": {"required": True},
                                     "compliance": {"status": "approved"}})
        ath = await athena_adapter.submit_mission(db, approved)
        hig = await higgbot_adapter.submit_mission(db, approved)
        no_real_dispatch = (ath.get("simulated") is True
                            and hig.get("simulated") is True
                            and "dispatched" not in ath)
        check("executors_simulate_no_real_dispatch", no_real_dispatch,
              "athena+higgbot returned simulated proposals only")
        check("higgbot_placeholder_is_free",
              (hig.get("placeholder_asset") or {}).get("cost_usd") == 0.0,
              "$0 placeholder asset")

        # 7) Conversation turns — policy-safe, no "--", correct routing.
        interest = await conversation_engine.handle_inbound(
            db, prospect_id="acc-1", brand="IBC", platform="instagram",
            message="tell me more about this")
        high = await conversation_engine.handle_inbound(
            db, prospect_id="acc-2", brand="NXG", platform="facebook",
            message="how much does it cost? ready to sign up")
        stop = await conversation_engine.handle_inbound(
            db, prospect_id="acc-3", brand="IBC", platform="instagram",
            message="please stop")
        draft = interest.get("draft_message") or ""
        check("autonomous_draft_never_double_dash", not contains_forbidden_dashes(draft),
              f"draft={draft!r}")
        check("autonomous_draft_policy_ok", interest.get("message_ok") is True, "")
        check("high_intent_routes_to_human",
              high.get("needs_human") is True and high.get("draft_message") is None,
              "no auto-advice on high intent")
        check("optout_is_honored_immediately",
              stop.get("action") in ("honor_opt_out", None)
              and stop.get("touchpoint_outcome") in ("none", None),
              "stop honored, no message")

        # 8) Outcomes rolled up into the North Star.
        roll = await analytics.rollup(db)
        check("north_star_computed", roll["touchpoints"] >= 2 and roll["qualified"] >= 1,
              f"{roll['qualified']} qualified / {roll['touchpoints']} touchpoints "
              f"= {roll['qualified_per_1k']}/1k")

        # 9) Allocation respects the kill switch (paused → zero), then restores.
        await flags.set(db, "SYSTEM_PAUSE", True)
        paused_plan = await allocation_engine.plan_day(db, total=1000)
        await flags.set(db, "SYSTEM_PAUSE", False)
        live_plan = await allocation_engine.plan_day(db, total=1000)
        check("killswitch_zeroes_allocation", paused_plan["planned_total"] == 0,
              "SYSTEM_PAUSE → zero allocation")
        check("allocation_sums_to_target", live_plan["planned_total"] == 1000,
              "unpaused allocation sums to target")

        # 10) Optimizer only tunes whitelisted params (safety), dashboard composes.
        rej = await optimizer.propose(db, "messaging.dash_rule", 1)
        check("optimizer_refuses_forbidden_key", rej.get("ok") is False,
              "messaging/compliance/kill keys are non-tunable")
        snap = await dashboard.snapshot(db)
        check("dashboard_composes",
              "north_star" in snap and "queue" in snap and "executors" in snap,
              "dashboard snapshot assembled")

        passed = sum(1 for c in checks if c["ok"])
        total = len(checks)
        ok = passed == total
        if not ok:
            logger.warning(f"acceptance FAILED {passed}/{total}: "
                           f"{[c['name'] for c in checks if not c['ok']]}")
        return {"ok": ok, "passed": passed, "total": total, "checks": checks,
                "mode": mode.value}


acceptance_harness = AcceptanceHarness()
