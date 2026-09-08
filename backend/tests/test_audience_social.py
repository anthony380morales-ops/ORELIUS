"""
Phase 7 tests — audience-intelligence + social-opportunity agents.

Pure mapping/slate logic runs with no DB. Two async tests drive the agents against
in-memory SQLite with the NXG lead source stubbed, so nothing hits Supabase.

Run with pytest, or directly:  python backend/tests/test_audience_social.py
"""
import asyncio

from sqlalchemy.pool import StaticPool
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from app.database import Base
from app.orchestration.mission import Brand, Platform, MissionPacket, Objective, TouchpointAction
from app.orchestration.agents.audience_intelligence import (
    audience_intelligence, AudienceInsight, apply_audience, top_concerns_from_leads,
)
from app.orchestration.agents.social_opportunity import (
    social_opportunity, opportunity_slate,
)
from app.config import settings


# ------------------------------------------------------------------ pure: audience
def test_top_concerns_ranks_and_filters():
    leads = [
        {"concern": "Retirement income"}, {"concern": "Retirement income"},
        {"concern": "Protecting the family"}, {"concern": "n/a"}, {"concern": ""},
    ]
    top = top_concerns_from_leads(leads)
    assert top[0] == "Retirement income"          # most common first
    assert "n/a" not in top and "" not in top      # junk filtered


def test_top_concerns_empty():
    assert top_concerns_from_leads([]) == []
    assert top_concerns_from_leads([{"concern": "none"}]) == []


def test_apply_audience_sharpens_mission():
    mp = MissionPacket(brand=Brand.NXG, platform=Platform.FACEBOOK,
                       objective=Objective.CONTENT_PUBLISH)
    insight = AudienceInsight(brand=Brand.NXG, segment="california_families",
                              top_concerns=["Retirement income"], confidence=0.8)
    apply_audience(mp, insight)
    assert mp.audience.segment == "Retirement income"
    assert mp.audience.confidence == 0.8


# ------------------------------------------------------------- pure: opportunities
def test_opportunity_slate_is_compliant_and_baseline_sized():
    slate = opportunity_slate(Brand.IBC)
    assert len(slate) == 6
    assert all(o.requires_live_api for o in slate)      # real targets gated to APIs
    assert all(o.platform == Platform.INSTAGRAM for o in slate)  # IBC → instagram
    # sized against the IBC baseline (shares sum to 1.0 → total ≈ baseline)
    total = sum(o.est_touchpoints for o in slate)
    assert abs(total - settings.ibc_touchpoint_baseline) <= 3
    # no unsolicited-mass-DM action in the permitted mix
    actions = {o.action for o in slate}
    assert TouchpointAction.PERMITTED_DM not in actions
    assert TouchpointAction.CONTENT_DISTRIBUTION in actions


def test_nxg_opportunities_route_to_facebook():
    slate = opportunity_slate(Brand.NXG)
    assert all(o.platform == Platform.FACEBOOK for o in slate)
    total = sum(o.est_touchpoints for o in slate)
    assert abs(total - settings.nxg_touchpoint_baseline) <= 3


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


# ------------------------------------------------------------------ async: profile
def test_ibc_profile_uses_brand_not_leads():
    async def go():
        db = await _fresh_session()
        insight = await audience_intelligence.profile(db, Brand.IBC)
        assert insight.source == "brand_profile"
        assert insight.segment == "professionals_entrepreneurs"
        assert "being your own banker" in insight.top_concerns
    _run(go())


def test_nxg_profile_reuses_live_lead_concerns():
    async def go():
        db = await _fresh_session()
        from app.core import nxg_intel as nxg_mod

        async def fake_recent(_db, limit=25):
            return {"ok": True, "leads": [
                {"concern": "Retirement income"}, {"concern": "Retirement income"},
                {"concern": "Living benefits"},
            ]}

        orig = nxg_mod.nxg_intel.recent_leads
        nxg_mod.nxg_intel.recent_leads = fake_recent
        try:
            insight = await audience_intelligence.profile(db, Brand.NXG)
        finally:
            nxg_mod.nxg_intel.recent_leads = orig

        assert insight.source == "nxg_leads"
        assert insight.top_concerns[0] == "Retirement income"   # real dominant concern
        assert insight.sample_size == 3
    _run(go())


def test_nxg_profile_falls_back_when_leads_unavailable():
    async def go():
        db = await _fresh_session()
        from app.core import nxg_intel as nxg_mod

        async def fake_recent(_db, limit=25):
            return {"ok": False, "reason": "unconfigured"}

        orig = nxg_mod.nxg_intel.recent_leads
        nxg_mod.nxg_intel.recent_leads = fake_recent
        try:
            insight = await audience_intelligence.profile(db, Brand.NXG)
        finally:
            nxg_mod.nxg_intel.recent_leads = orig

        assert insight.source == "brand_profile"                # graceful fallback
        assert insight.top_concerns                              # still has defaults
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
    print(f"\n{passed}/{len(fns)} audience/social-opportunity tests passed.")


if __name__ == "__main__":
    _run_all()
