"""
Autonomous daily poster.

ORELIUS compiles FRESH brand content and dispatches it to ATHENA on a fixed
daily schedule, so posts appear without anyone asking. Each slot posts exactly
ONE piece per brand (solo=False), so the number of posts matches the schedule.

Runs as an in-process asyncio task started from the app lifespan. It works on
Render's free tier because the ATHENA bridge polls /api/memory every ~15s, which
keeps the instance awake so this loop keeps ticking.

Schedule + brands come from settings (autopost_times, autopost_brands,
autopost_timezone, autopost_grace_minutes). Fired slots are persisted in
AutomationState so a redeploy near a slot time never double-posts.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from typing import List
from zoneinfo import ZoneInfo

from sqlalchemy import select

from ..config import settings
from ..database import AsyncSessionLocal
from ..models.automation_state import AutomationState
from ..utils.logger import logger
from .hot_topic import hot_topic_reels

_STATE_KEY = "autopost_state"
_CHECK_SECONDS = 30


def _parse_list(raw: str) -> List[str]:
    return [x.strip() for x in (raw or "").split(",") if x.strip()]


def _tz() -> ZoneInfo:
    try:
        return ZoneInfo(getattr(settings, "autopost_timezone", "America/Los_Angeles"))
    except Exception:  # noqa: BLE001 - bad tz name shouldn't crash the loop
        return ZoneInfo("America/Los_Angeles")


async def _load_state(db) -> dict:
    try:
        row = (await db.execute(
            select(AutomationState).where(AutomationState.key == _STATE_KEY)
        )).scalars().first()
        if row and isinstance(row.data, dict):
            return dict(row.data)
    except Exception as e:  # noqa: BLE001
        logger.debug(f"autopost load state failed: {e}")
    return {}


async def _save_state(db, data: dict) -> None:
    try:
        row = (await db.execute(
            select(AutomationState).where(AutomationState.key == _STATE_KEY)
        )).scalars().first()
        if row:
            row.data = data
        else:
            db.add(AutomationState(key=_STATE_KEY, data=data))
        await db.flush()
    except Exception as e:  # noqa: BLE001
        logger.debug(f"autopost save state failed: {e}")


async def _fire(db, brands: List[str], slot: str, day: str) -> None:
    """Compile fresh content and dispatch ONE post per brand."""
    logger.info(f"autopost: firing slot {slot} ({day}) for brands={brands}")
    try:
        compiled = await hot_topic_reels.compile_brands(db, brands)
        if not compiled.get("ok"):
            logger.warning(f"autopost {slot}: compile produced nothing ({compiled.get('reason')}); "
                           f"skipping dispatch this slot")
            return
        result = await hot_topic_reels.dispatch_brands(db, brands, solo=False)
        sent = {b: r.get("dispatched") for b, r in (result.get("results") or {}).items() if r.get("ok")}
        logger.info(f"autopost {slot}: dispatched {sent}")
    except Exception as e:  # noqa: BLE001 - never let one slot kill the loop
        logger.error(f"autopost {slot} failed: {e}")


async def _tick() -> None:
    brands = _parse_list(getattr(settings, "autopost_brands", "nxg,ibc"))
    times = _parse_list(getattr(settings, "autopost_times", "08:00,13:00,15:00,19:00"))
    grace = int(getattr(settings, "autopost_grace_minutes", 90))
    if not brands or not times:
        return

    now = datetime.now(_tz())
    day = now.strftime("%Y-%m-%d")

    async with AsyncSessionLocal() as db:
        state = await _load_state(db)
        if state.get("date") != day:
            state = {"date": day, "fired": []}
        fired = set(state.get("fired", []))

        for slot in times:
            if slot in fired:
                continue
            try:
                hh, mm = [int(x) for x in slot.split(":")]
            except ValueError:
                continue
            slot_dt = now.replace(hour=hh, minute=mm, second=0, microsecond=0)
            # Fire once the slot time has arrived, within the grace window (so a
            # late-waking instance still posts, but a long-missed slot is skipped).
            if slot_dt <= now <= slot_dt + timedelta(minutes=grace):
                await _fire(db, brands, slot, day)
                fired.add(slot)
                state["fired"] = sorted(fired)
                await _save_state(db, state)
                await db.commit()


async def run_autopost_loop() -> None:
    """Background loop: check the schedule every ~30s and fire due slots."""
    if not getattr(settings, "autopost_enabled", False):
        logger.info("autopost disabled (autopost_enabled=false)")
        return
    logger.info(
        f"autopost online — times={getattr(settings, 'autopost_times', '')} "
        f"tz={getattr(settings, 'autopost_timezone', '')} "
        f"brands={getattr(settings, 'autopost_brands', '')}"
    )
    while True:
        try:
            await _tick()
        except Exception as e:  # noqa: BLE001 - the loop must never die
            logger.error(f"autopost loop error: {e}")
        await asyncio.sleep(_CHECK_SECONDS)
