"""
Phase 6 tests — economic-intelligence + financial-impact agents + planner.

Most tests are pure (no DB, no network, no model calls). One async test drives
the planner end to end against in-memory SQLite with the compiled-intel source
stubbed, so nothing hits finance_intel or Claude.

Run with pytest, or directly:  python backend/tests/test_intelligence.py
"""
import asyncio

from sqlalchemy.pool import StaticPool
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from app.database import Base
from app.orchestration.mission import Brand, Objective, Platform, ComplianceStatus, Priority
from app.orchestration.agents.economic_intelligence import signals_from_package, EconomicSignal
from app.orchestration.agents.financial_impact import financial_impact
from app.orchestration.planner import build_content_missions, intelligence_planner

_PACKAGE = {
    "facts": [
        "The Fed held interest rates steady while inflation cooled to 3 percent",
        "US national debt crossed a new record this quarter",
        "A local park added three new benches",   # low relevance
    ],
    "caption": "Here is what the economy is telling you about protecting your money.",
    "post_idea": "Explain why rising rates matter for savings and life insurance.",
    "created_at": "2026-09-08T00:00:00Z",
}


# ------------------------------------------------------------------ economic intel
def test_signals_from_package_maps_facts():
    sigs = signals_from_package(_PACKAGE)
    assert len(sigs) == 3
    assert all(isinstance(s, EconomicSignal) for s in sigs)
    assert sigs[0].headline.startswith("The Fed held")
    # framing (caption + post idea) is shared onto every signal
    assert "protecting your money" in sigs[0].framing
    assert sigs[0].id != sigs[1].id                       # stable, distinct ids


def test_signals_from_empty_package():
    assert signals_from_package({}) == []
    assert signals_from_package({"facts": ["  ", ""]}) == []


# ------------------------------------------------------------------ financial impact
def test_impact_scores_and_ranks_by_relevance():
    sigs = signals_from_package(_PACKAGE)
    angles = financial_impact.assess(sigs, Brand.NXG)
    assert len(angles) == 3
    # ranked highest score first; the finance-heavy facts beat the park bench
    assert angles[0].opportunity_score >= angles[-1].opportunity_score
    park = [a for a in angles if a.signal_id == sigs[2].id][0]
    fed = [a for a in angles if a.signal_id == sigs[0].id][0]
    assert fed.opportunity_score > park.opportunity_score
    assert all(a.needs_compliance_review for a in angles)  # always reviewed


def test_impact_brand_voice_separation():
    sigs = signals_from_package(_PACKAGE)
    ibc = financial_impact.assess(sigs, Brand.IBC)[0]
    nxg = financial_impact.assess(sigs, Brand.NXG)[0]
    assert "Infinite Banking" in ibc.angle
    assert ibc.audience_hint == "professionals_entrepreneurs"
    assert nxg.audience_hint == "california_families"


# ------------------------------------------------------------------ planner (pure)
def test_build_content_missions_are_held_on_compliance():
    sigs = signals_from_package(_PACKAGE)
    angles = financial_impact.assess(sigs, Brand.IBC)
    missions = build_content_missions(sigs, angles, Brand.IBC)
    assert len(missions) == 3
    m = missions[0]
    assert m.brand == Brand.IBC and m.platform == Platform.INSTAGRAM   # IBC → instagram
    assert m.objective == Objective.CONTENT_PUBLISH
    assert m.creative.required is True
    assert m.compliance.status == ComplianceStatus.PENDING             # not ready
    assert m.is_ready_for_executor() is False
    assert m.topic.title == sigs[0].headline
    assert m.brief["angle"]                                            # carries the angle


def test_nxg_missions_route_to_facebook():
    sigs = signals_from_package(_PACKAGE)
    angles = financial_impact.assess(sigs, Brand.NXG)
    missions = build_content_missions(sigs, angles, Brand.NXG)
    assert all(m.platform == Platform.FACEBOOK for m in missions)


def test_priority_tracks_score():
    sigs = signals_from_package(_PACKAGE)
    angles = financial_impact.assess(sigs, Brand.NXG)
    missions = build_content_missions(sigs, angles, Brand.NXG)
    # the top-ranked mission is at least as high priority as the last
    order = {Priority.HIGH: 0, Priority.MEDIUM: 1, Priority.LOW: 2}
    assert order[missions[0].priority] <= order[missions[-1].priority]


# ------------------------------------------------------------------ planner (async)
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


def test_scan_enqueues_blocked_missions_with_stubbed_intel():
    async def go():
        db = await _fresh_session()

        # Stub the compiled-intel source so no finance_intel / Claude call happens.
        from app.core import hot_topic as ht_mod

        async def fake_compile(_db):
            return {"ok": True, "package": _PACKAGE}

        orig = ht_mod.hot_topic_reels.compile_package
        ht_mod.hot_topic_reels.compile_package = fake_compile
        try:
            out = await intelligence_planner.scan(db, Brand.NXG, enqueue=True)
        finally:
            ht_mod.hot_topic_reels.compile_package = orig

        assert len(out["signals"]) == 3
        assert len(out["missions"]) == 3
        assert len(out["enqueued"]) == 3
        # every enqueued proposal is held on compliance (BLOCKED), not runnable
        from app.orchestration.mission_queue import mission_queue
        stats = await mission_queue.stats(db)
        assert stats["blocked"] == 3 and stats["queue_depth"] == 0
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
    print(f"\n{passed}/{len(fns)} intelligence/planner tests passed.")


if __name__ == "__main__":
    _run_all()
