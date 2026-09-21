"""
Autonomous morning brief + daily poster.

Each morning (07:30 PT by default) ORELIUS, on its own:
  1. Pulls the financial-intelligence report.
  2. Pre-compiles the ENTIRE day's posts (each slot × each brand), rotating the
     NXG income tier and IBC economic angle so every post is distinct.
  3. Drops the report + the full day's post plan (what publishes, and when) into
     the Master's conversation, so he wakes up to it without asking.

Then at each scheduled slot it publishes the pre-compiled post for that slot, so
what the Master read in the morning is exactly what goes out.

Runs as an in-process asyncio task started from the app lifespan. Works on
Render's free tier because the ATHENA bridge polls every ~15s, keeping the
instance awake. Fired slots + the brief are persisted in AutomationState so a
redeploy never double-posts or re-briefs.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone, tzinfo
from typing import List
from zoneinfo import ZoneInfo

from sqlalchemy import select

from ..config import settings
from ..database import AsyncSessionLocal
from ..models.automation_state import AutomationState
from ..models.conversation import MessageRole, MessageSource
from ..utils.logger import logger
from .hot_topic import hot_topic_reels, _next_rotation
from .finance_intel import finance_intel
from .memory_manager import memory_manager

_STATE_KEY = "autopost_state"
_PLAN_KEY = "daily_post_plan"
_CHECK_SECONDS = 30


def _parse_list(raw: str) -> List[str]:
    return [x.strip() for x in (raw or "").split(",") if x.strip()]


def _tz() -> tzinfo:
    """Resolve the configured timezone. If the tz database is unavailable (e.g. a
    slim image missing `tzdata`), fall back to a fixed Pacific offset so the loop
    keeps firing instead of crashing every tick. This fallback must NEVER raise —
    a raise here silently kills the whole autopost loop."""
    name = getattr(settings, "autopost_timezone", "America/Los_Angeles")
    try:
        return ZoneInfo(name)
    except Exception as e:  # noqa: BLE001
        logger.error(
            f"autopost: ZoneInfo('{name}') failed ({e}); is `tzdata` installed? "
            f"Falling back to a fixed UTC-8 offset so posting still fires."
        )
        return timezone(timedelta(hours=-8), "PST-fallback")


def _hhmm_display(hhmm: str) -> str:
    try:
        h, m = [int(x) for x in hhmm.split(":")]
        ap = "AM" if h < 12 else "PM"
        h12 = h % 12 or 12
        return f"{h12}:{m:02d} {ap}"
    except Exception:  # noqa: BLE001
        return hhmm


async def _load(db, key: str) -> dict:
    try:
        row = (await db.execute(select(AutomationState).where(AutomationState.key == key))).scalars().first()
        if row and isinstance(row.data, dict):
            return dict(row.data)
    except Exception as e:  # noqa: BLE001
        logger.debug(f"autopost load {key} failed: {e}")
    return {}


async def _save(db, key: str, data: dict) -> None:
    try:
        row = (await db.execute(select(AutomationState).where(AutomationState.key == key))).scalars().first()
        if row:
            row.data = data
        else:
            db.add(AutomationState(key=key, data=data))
        await db.flush()
    except Exception as e:  # noqa: BLE001
        logger.debug(f"autopost save {key} failed: {e}")


def _master_id() -> str:
    ids = getattr(settings, "allowed_login_ids", []) or []
    return ids[0] if ids else "anthony"


# ------------------------------------------------------------------ morning brief
def _format_brief(intel: str, times: List[str], plan_slots: dict) -> str:
    parts = [
        "🌅 Good morning, Master. Here is today's financial-intelligence brief and the "
        "full plan of what I'll publish today.",
        "",
        "━━━━━━ FINANCIAL INTELLIGENCE ━━━━━━",
        (intel or "").strip() or "(No fresh intelligence retrieved this morning.)",
        "",
        "━━━━━━ TODAY'S POSTS (auto-publishing) ━━━━━━",
    ]
    for t in times:
        slot = plan_slots.get(t, {})
        parts.append(f"\n⏰ {_hhmm_display(t)}")
        nxg = slot.get("nxg")
        ibc = slot.get("ibc")
        if nxg:
            tier = nxg.get("tier_label", "")
            cap = (nxg.get("caption", "") or "").strip().replace("\n", " ")
            if len(cap) > 220:
                cap = cap[:220].rstrip() + "…"
            parts.append(f"  • NXG · Facebook — {tier}")
            parts.append(f"    “{cap}”")
        if ibc:
            parts.append(f"  • IBC · Instagram — {ibc.get('title', 'Economic briefing')}")
            for p in (ibc.get("panels") or [])[:3]:
                fig = p.get("figure", ""); lab = p.get("label", ""); hd = p.get("headline", "")
                parts.append(f"    {fig}  {lab} — {hd}")
    parts.append("\n(Everything above publishes automatically at its time. Reply if you want any of it changed.)")
    return "\n".join(parts)


async def _run_morning_brief(db, day: str) -> None:
    times = _parse_list(getattr(settings, "autopost_times", "08:00,13:00,15:00,19:00"))
    brands = _parse_list(getattr(settings, "autopost_brands", "nxg,ibc"))
    if not times or not brands:
        return
    logger.info(f"morning-brief: building for {day} (slots={times}, brands={brands})")

    # 1. Pull the intelligence report (records it too).
    intel = ""
    try:
        res = await finance_intel.generate_brief(db)
        intel = (res or {}).get("summary", "") or ""
    except Exception as e:  # noqa: BLE001
        logger.warning(f"morning-brief intel failed: {e}")
        try:
            intel = await finance_intel.live_briefing()
        except Exception:  # noqa: BLE001
            intel = ""

    # 2. Pre-compile the whole day's posts, one rotation per slot (distinct each slot).
    plan_slots: dict = {}
    for t in times:
        rotation = await _next_rotation(db)
        slot_pkgs: dict = {}
        for b in brands:
            try:
                r = await hot_topic_reels.compile_package(db, brand=b, intel=intel or None, rotation=rotation)
                if r.get("ok"):
                    slot_pkgs[r["brand"]] = r["package"]
            except Exception as e:  # noqa: BLE001
                logger.warning(f"morning-brief compile {b}@{t} failed: {e}")
        plan_slots[t] = slot_pkgs
    await _save(db, _PLAN_KEY, {"date": day, "slots": plan_slots})

    # 3. Drop the brief + plan into the Master's conversation.
    try:
        conv = await memory_manager.get_or_create_conversation(db, _master_id(), MessageSource.WEB)
        await memory_manager.add_message(db, conv.id, MessageRole.ASSISTANT, _format_brief(intel, times, plan_slots))
        logger.info("morning-brief: posted report + plan to the Master's conversation")
    except Exception as e:  # noqa: BLE001
        logger.error(f"morning-brief: could not write to conversation: {e}")
    await db.commit()


# ------------------------------------------------------------------ slot publish
async def _fire(db, brands: List[str], slot: str, day: str) -> None:
    """Publish this slot — prefer the pre-compiled morning plan; else compile fresh."""
    plan = await _load(db, _PLAN_KEY)
    slot_pkgs = (plan.get("slots") or {}).get(slot) if plan.get("date") == day else None

    if slot_pkgs:
        sent = {}
        for b in brands:
            pkg = slot_pkgs.get(b)
            if not pkg:
                continue
            try:
                r = await hot_topic_reels.dispatch_package(db, b, pkg, solo=False)
                if r.get("ok"):
                    sent[b] = r.get("dispatched")
            except Exception as e:  # noqa: BLE001
                logger.error(f"autopost {slot}: dispatch {b} failed: {e}")
        logger.info(f"autopost {slot}: dispatched from morning plan -> {sent}")
        return

    # Fallback: no plan for today (brief didn't run) — compile fresh, then dispatch.
    logger.info(f"autopost {slot}: no morning plan, compiling fresh")
    try:
        compiled = await hot_topic_reels.compile_brands(db, brands)
        if not compiled.get("ok"):
            logger.warning(f"autopost {slot}: nothing to compile ({compiled.get('reason')})")
            return
        result = await hot_topic_reels.dispatch_brands(db, brands, solo=False)
        sent = {b: r.get("dispatched") for b, r in (result.get("results") or {}).items() if r.get("ok")}
        logger.info(f"autopost {slot}: dispatched (fresh) -> {sent}")
    except Exception as e:  # noqa: BLE001
        logger.error(f"autopost {slot} fresh dispatch failed: {e}")


async def _tick() -> None:
    brands = _parse_list(getattr(settings, "autopost_brands", "nxg,ibc"))
    times = _parse_list(getattr(settings, "autopost_times", "08:00,13:00,15:00,19:00"))
    grace = int(getattr(settings, "autopost_grace_minutes", 90))
    if not brands or not times:
        return

    now = datetime.now(_tz())
    day = now.strftime("%Y-%m-%d")

    async with AsyncSessionLocal() as db:
        state = await _load(db, _STATE_KEY)
        if state.get("date") != day:
            state = {"date": day, "fired": [], "brief": False}
        fired = set(state.get("fired", []))

        # Morning brief (once/day), fires within the grace window like a slot.
        if getattr(settings, "morning_brief_enabled", True) and not state.get("brief"):
            bt = getattr(settings, "morning_brief_time", "07:30")
            try:
                bh, bm = [int(x) for x in bt.split(":")]
                bdt = now.replace(hour=bh, minute=bm, second=0, microsecond=0)
                if bdt <= now <= bdt + timedelta(minutes=grace):
                    await _run_morning_brief(db, day)
                    state["brief"] = True
                    await _save(db, _STATE_KEY, state)
                    await db.commit()
            except Exception as e:  # noqa: BLE001
                logger.error(f"morning-brief tick error: {e}")

        # Publishing slots.
        for slot in times:
            if slot in fired:
                continue
            try:
                hh, mm = [int(x) for x in slot.split(":")]
            except ValueError:
                continue
            slot_dt = now.replace(hour=hh, minute=mm, second=0, microsecond=0)
            if slot_dt <= now <= slot_dt + timedelta(minutes=grace):
                await _fire(db, brands, slot, day)
                fired.add(slot)
                state["fired"] = sorted(fired)
                await _save(db, _STATE_KEY, state)
                await db.commit()


async def run_autopost_loop() -> None:
    """Background loop: check the schedule every ~30s; run the morning brief and
    fire due slots."""
    if not getattr(settings, "autopost_enabled", False):
        logger.info("autopost disabled (autopost_enabled=false)")
        return
    logger.info(
        f"autopost online — brief={getattr(settings, 'morning_brief_time', '')} "
        f"times={getattr(settings, 'autopost_times', '')} "
        f"tz={getattr(settings, 'autopost_timezone', '')} "
        f"brands={getattr(settings, 'autopost_brands', '')}"
    )
    while True:
        try:
            await _tick()
        except Exception as e:  # noqa: BLE001 - the loop must never die
            logger.error(f"autopost loop error: {e}")
        await asyncio.sleep(_CHECK_SECONDS)
