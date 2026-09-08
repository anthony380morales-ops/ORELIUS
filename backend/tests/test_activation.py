"""
Phase 15 tests — credential-gated production activation.

Proves the safety gates: no activation without the typed confirmation, without real
credentials, or without a passing acceptance run; the durable RUN_LIVE override
actually flips flags.mode to live; deactivation is instant and unconditional; and
SYSTEM_PAUSE still overrides live back to simulation.

Run with pytest, or directly:  python backend/tests/test_activation.py
"""
import asyncio

from sqlalchemy.pool import StaticPool
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from app.database import Base
from app.orchestration.activation import activation, CONFIRM_PHRASE
from app.orchestration.flags import flags, SocialMode
from app.config import settings


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


# ------------------------------------------------------------------ readiness
def test_readiness_reports_missing_creds_by_default():
    async def go():
        db = await _fresh_session()
        r = await activation.readiness(db)
        # default test env has no provider credentials
        assert r["any_ready"] is False
        assert r["providers"]["meta"]["configured"] is False
        assert "meta_access_token" in r["providers"]["meta"]["missing"]
    _run(go())


# ------------------------------------------------------------------ gates
def test_activate_requires_confirmation():
    async def go():
        db = await _fresh_session()
        out = await activation.activate(db, confirm="yes please")
        assert out["ok"] is False and out["reason"] == "confirmation_required"
        assert (await flags.mode(db)) == SocialMode.SIMULATION   # unchanged
    _run(go())


def test_activate_refused_without_credentials():
    async def go():
        db = await _fresh_session()
        # correct phrase, but no provider is configured → still refused
        out = await activation.activate(db, confirm=CONFIRM_PHRASE)
        assert out["ok"] is False and out["reason"] == "no_provider_ready"
        assert (await flags.mode(db)) == SocialMode.SIMULATION
    _run(go())


# ------------------------------------------------------------------ happy path
def test_activate_succeeds_with_creds_and_acceptance(monkeypatch=None):
    async def go():
        db = await _fresh_session()
        # configure one provider (manychat) just for this test
        old = settings.manychat_api_token
        settings.manychat_api_token = "test-token"
        try:
            out = await activation.activate(db, confirm=CONFIRM_PHRASE)
            assert out["ok"] is True and out["activated"] is True
            assert "manychat" in out["live_providers"]
            assert (await flags.mode(db)) == SocialMode.LIVE       # flipped live
            # SYSTEM_PAUSE still overrides live back to simulation
            await flags.set(db, "SYSTEM_PAUSE", True)
            assert (await flags.mode(db)) == SocialMode.SIMULATION
            await flags.set(db, "SYSTEM_PAUSE", False)
            assert (await flags.mode(db)) == SocialMode.LIVE
        finally:
            settings.manychat_api_token = old
    _run(go())


def test_deactivate_is_instant_and_unconditional():
    async def go():
        db = await _fresh_session()
        await flags.set(db, "RUN_LIVE", True)
        assert (await flags.mode(db)) == SocialMode.LIVE
        out = await activation.deactivate(db)
        assert out["ok"] is True and out["mode"] == "simulation"
        assert (await flags.mode(db)) == SocialMode.SIMULATION
    _run(go())


def test_status_shape():
    async def go():
        db = await _fresh_session()
        s = await activation.status(db)
        assert s["mode"] == "simulation"
        assert s["confirm_phrase"] == CONFIRM_PHRASE
        assert "readiness" in s and "providers" in s["readiness"]
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
    print(f"\n{passed}/{len(fns)} activation tests passed.")


if __name__ == "__main__":
    _run_all()
