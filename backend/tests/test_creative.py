"""
Phase 4 tests — HIGGBOT creative contract + adapter.

Pure brief-building and tier→budget mapping run with no DB. The adapter submit
flows run against an in-memory aiosqlite engine (simulation mode, the default),
so nothing real is ever dispatched.

Run with pytest, or directly:  python backend/tests/test_creative.py
"""
import asyncio

from sqlalchemy.pool import StaticPool
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from app.database import Base
from app.orchestration.mission import validate_mission, Brand
from app.orchestration.creative import (
    build_brief, to_higgbot_job, tier_budget_usd, QualityTier, AssetKind, CreativeBrief,
)
from app.orchestration.adapters import higgbot_adapter
from app.orchestration.adapters.athena_adapter import translate as athena_translate


# ------------------------------------------------------------------ pure: budgets
def test_tier_budget_ordering():
    assert tier_budget_usd(QualityTier.DRAFT) < tier_budget_usd(QualityTier.PROD) \
        < tier_budget_usd(QualityTier.HERO)


# ------------------------------------------------------------------ pure: brief
def test_build_brief_defaults_to_reel_and_prod():
    p = validate_mission({"brand": "IBC", "platform": "instagram",
                          "objective": "content_publish",
                          "topic": {"title": "Why IUL beats a savings account"},
                          "creative": {"required": True},
                          "compliance": {"status": "approved"}})
    brief = build_brief(p)
    assert brief.asset_kind == AssetKind.REEL
    assert brief.quality == QualityTier.PROD          # default higgbot_quality
    assert brief.aspect_ratio == "9:16"
    assert "IUL" in brief.prompt
    assert brief.budget_usd == tier_budget_usd(QualityTier.PROD)


def test_ibc_gets_brand_voice_nxg_does_not():
    ibc = build_brief(validate_mission({"brand": "IBC", "platform": "instagram",
                                        "objective": "content_publish",
                                        "topic": {"title": "t"},
                                        "creative": {"required": True}}))
    nxg = build_brief(validate_mission({"brand": "NXG", "platform": "facebook",
                                        "objective": "content_publish",
                                        "topic": {"title": "t"},
                                        "creative": {"required": True}}))
    assert ibc.brand == Brand.IBC and ibc.brand_voice != ""      # ibluezcluezflow voice
    assert nxg.brand == Brand.NXG and nxg.brand_voice == ""      # brands never merged


def test_hero_tier_flows_through():
    p = validate_mission({"brand": "IBC", "platform": "instagram",
                          "objective": "content_publish",
                          "topic": {"title": "flagship"},
                          "creative": {"required": True, "higgbot_quality": "hero"}})
    brief = build_brief(p)
    assert brief.quality == QualityTier.HERO
    assert brief.budget_usd == tier_budget_usd(QualityTier.HERO)


# ------------------------------------------------------------------ pure: job shape
def test_to_higgbot_job_is_provider_agnostic_and_budget_capped():
    brief = CreativeBrief(mission_id="M1", brand=Brand.IBC, prompt="x",
                          quality=QualityTier.PROD, count=2)
    job = to_higgbot_job(brief)
    assert job["kind"] == "design"                    # routes via ATHENA's design bridge
    assert "provider" not in job                       # HIGGBOT's router chooses
    assert job["max_spend_usd"] == brief.max_spend()   # per-asset cap × count
    assert "Budget:" in job["request"]
    assert "Compliance:" in job["request"]


def test_athena_adapter_routes_pure_creative_to_design():
    # engagement objective + creative required → design job (not instagram_post)
    p = validate_mission({"brand": "IBC", "platform": "instagram",
                          "objective": "engagement",
                          "topic": {"title": "brand kit"},
                          "creative": {"required": True}})
    job = athena_translate(p)
    assert job["kind"] == "design"
    assert job.get("creative") is not None            # carries the HIGGBOT brief
    assert job.get("task")                             # design-engine hint present


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
    import app.models.orchestration  # noqa: F401 — register tables on Base
    engine = create_async_engine(
        "sqlite+aiosqlite://", echo=False,
        poolclass=StaticPool, connect_args={"check_same_thread": False},
    )
    _ENGINES.append(engine)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)()


# ------------------------------------------------------------------ adapter (async)
def test_submit_brief_is_simulated_with_placeholder():
    async def go():
        db = await _fresh_session()
        brief = CreativeBrief(mission_id="M2", brand=Brand.IBC, prompt="reel")
        out = await higgbot_adapter.submit_brief(db, brief)
        assert out["ok"] is True and out["simulated"] is True    # default = simulation
        assert out["placeholder_asset"]["cost_usd"] == 0.0        # $0 stand-in
        assert out["would_dispatch"]["kind"] == "design"          # computed, not sent
    _run(go())


def test_submit_mission_blocked_without_compliance():
    async def go():
        db = await _fresh_session()
        p = validate_mission({"brand": "IBC", "platform": "instagram",
                              "objective": "content_publish",
                              "topic": {"title": "t"}, "creative": {"required": True}})
        out = await higgbot_adapter.submit_mission(db, p)
        assert out["ok"] is False and out["reason"] == "compliance_not_approved"
    _run(go())


def test_submit_mission_simulated_when_approved():
    async def go():
        db = await _fresh_session()
        p = validate_mission({"brand": "IBC", "platform": "instagram",
                              "objective": "content_publish",
                              "topic": {"title": "t"}, "creative": {"required": True},
                              "compliance": {"status": "approved"}})
        out = await higgbot_adapter.submit_mission(db, p)
        assert out["ok"] is True and out["simulated"] is True
        assert out["brief"]["brand"] == "IBC"
    _run(go())


def test_higgbot_pause_forces_simulation_even_if_flag_set():
    async def go():
        db = await _fresh_session()
        await flags_set(db, "HIGGBOT_PAUSE", True)
        brief = CreativeBrief(mission_id="M3", brand=Brand.IBC, prompt="reel")
        out = await higgbot_adapter.submit_brief(db, brief)
        assert out["simulated"] is True                           # paused → never dispatch
    _run(go())


async def flags_set(db, name, value):
    from app.orchestration.flags import flags
    await flags.set(db, name, value)


def _run_all():
    import inspect
    fns = [v for k, v in sorted(globals().items())
           if k.startswith("test_") and inspect.isfunction(v)]
    passed = 0
    for fn in fns:
        fn()
        passed += 1
        print(f"  ok  {fn.__name__}")
    print(f"\n{passed}/{len(fns)} creative/HIGGBOT tests passed.")


if __name__ == "__main__":
    _run_all()
