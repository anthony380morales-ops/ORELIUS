"""
Phase 14 test — the end-to-end simulation acceptance gate (§69).

Runs the whole loop against in-memory SQLite and asserts EVERY check passes. This is
the single gate that proves the ecosystem is safe and coherent in simulation before
any real credential exists.

Run with pytest, or directly:  python backend/tests/test_acceptance.py
"""
import asyncio

from sqlalchemy.pool import StaticPool
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from app.database import Base
from app.orchestration.acceptance import acceptance_harness


_ENGINES: list = []


def _run(coro):
    async def _wrapped():
        try:
            return await coro
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


def test_full_ecosystem_acceptance_passes():
    async def go():
        db = await _fresh_session()
        report = await acceptance_harness.run(db)
        failed = [c["name"] for c in report["checks"] if not c["ok"]]
        assert report["ok"] is True, f"failed checks: {failed}"
        assert report["passed"] == report["total"]
        # sanity: the safety-critical checks are actually present in the report
        names = {c["name"] for c in report["checks"]}
        for required in (
            "mode_is_simulation",
            "compliance_gate_releases_clean",
            "compliance_blocks_prohibited_claim",
            "executors_simulate_no_real_dispatch",
            "autonomous_draft_never_double_dash",
            "high_intent_routes_to_human",
            "optout_is_honored_immediately",
            "killswitch_zeroes_allocation",
            "optimizer_refuses_forbidden_key",
        ):
            assert required in names, f"missing check: {required}"
    _run(go())


def test_acceptance_reports_every_check_individually():
    async def go():
        db = await _fresh_session()
        report = await acceptance_harness.run(db)
        # each check is a labeled, inspectable pass/fail with detail
        for c in report["checks"]:
            assert set(c.keys()) == {"name", "ok", "detail"}
            assert c["ok"] is True, f"{c['name']}: {c['detail']}"
        print(f"acceptance: {report['passed']}/{report['total']} checks passed")
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
    print(f"\n{passed}/{len(fns)} acceptance tests passed.")


if __name__ == "__main__":
    _run_all()
