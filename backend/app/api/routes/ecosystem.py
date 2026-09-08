"""
Ecosystem orchestration API (directive §13, §46, §54).

ORELIUS's control surface for the multi-agent ecosystem: submit/inspect/cancel/retry
missions to ATHENA, read executor health/capabilities, inspect the queue, and flip
the kill switches / run-mode. All routes require the same JWT auth as chat.

Simulation-first: a submitted mission only performs real outbound action when the
run mode is 'live' AND no kill switch gates it; otherwise it returns the proposed
job without doing anything real.
"""
from fastapi import APIRouter, Depends, HTTPException, Body
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

from ...database import get_db
from ...core.auth import get_current_user
from ...utils.logger import logger
from ...orchestration.mission import validate_mission, MissionStatus
from ...orchestration.mission_queue import mission_queue
from ...orchestration.adapters import athena_adapter, higgbot_adapter, lucius_adapter
from ...orchestration.control import control_surface, SCOPE_TO_FLAG
from ...orchestration.flags import flags, PAUSE_FLAGS

router = APIRouter()


def _mission_view(row) -> dict:
    return {
        "mission_id": row.mission_id,
        "status": row.status,
        "brand": row.brand,
        "platform": row.platform,
        "objective": row.objective,
        "priority": row.priority,
        "attempts": row.attempts,
        "executor": row.executor,
        "result": row.result,
        "error": row.error,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "expires_at": row.expires_at.isoformat() if row.expires_at else None,
    }


@router.post("/ecosystem/athena/missions")
async def submit_athena_mission(
    packet: dict = Body(...),
    db: AsyncSession = Depends(get_db),
    user: str = Depends(get_current_user),
):
    """Validate → queue → (attempt) execute a mission through ATHENA."""
    try:
        mp = validate_mission(packet)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=422, detail=f"invalid mission packet: {e}")

    row = await mission_queue.enqueue(db, mp, executor="athena")

    # Held for compliance → don't execute; report why.
    if row.status == MissionStatus.BLOCKED.value:
        return {"mission": _mission_view(row),
                "submit": {"ok": False, "reason": "compliance_not_approved"}}

    # Attempt execution now (a worker loop can also drive this later).
    submit = await athena_adapter.submit_mission(db, mp)
    if submit.get("simulated"):
        row.status = MissionStatus.COMPLETED.value          # simulation completes logically
        row.result = submit
    elif submit.get("dispatched"):
        row.status = MissionStatus.RUNNING.value            # ATHENA works async
        row.result = submit
    else:
        row.status = MissionStatus.WAITING.value            # opportunity, no direct endpoint
        row.result = submit
    await db.flush()
    return {"mission": _mission_view(row), "submit": submit}


@router.get("/ecosystem/athena/missions/{mission_id}")
async def get_athena_mission(
    mission_id: str,
    db: AsyncSession = Depends(get_db),
    user: str = Depends(get_current_user),
):
    row = await mission_queue.get(db, mission_id)
    if not row:
        raise HTTPException(status_code=404, detail="mission not found")
    return {"mission": _mission_view(row), "packet": row.packet}


@router.post("/ecosystem/athena/missions/{mission_id}/cancel")
async def cancel_athena_mission(
    mission_id: str,
    db: AsyncSession = Depends(get_db),
    user: str = Depends(get_current_user),
):
    ok = await mission_queue.cancel(db, mission_id)
    return {"ok": ok}


@router.post("/ecosystem/athena/missions/{mission_id}/retry")
async def retry_athena_mission(
    mission_id: str,
    db: AsyncSession = Depends(get_db),
    user: str = Depends(get_current_user),
):
    ok = await mission_queue.retry(db, mission_id)
    return {"ok": ok}


@router.get("/ecosystem/athena/health")
async def athena_health(
    db: AsyncSession = Depends(get_db),
    user: str = Depends(get_current_user),
):
    return await athena_adapter.health(db)


@router.get("/ecosystem/athena/capabilities")
async def athena_capabilities(user: str = Depends(get_current_user)):
    return await athena_adapter.capabilities()


# --------------------------------------------------------------- HIGGBOT (creative)
@router.post("/ecosystem/higgbot/creative")
async def submit_higgbot_creative(
    packet: dict = Body(...),
    db: AsyncSession = Depends(get_db),
    user: str = Depends(get_current_user),
):
    """Validate a creative mission → build the brief → (attempt) produce via HIGGBOT.

    The creative path is ORELIUS → ATHENA → HIGGBOT; in simulation/dry-run or when
    HIGGBOT_PAUSE is set, the proposed job + a $0 placeholder asset are returned
    without dispatching anything real.
    """
    try:
        mp = validate_mission(packet)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=422, detail=f"invalid mission packet: {e}")

    row = await mission_queue.enqueue(db, mp, executor="higgbot")
    if row.status == MissionStatus.BLOCKED.value:
        return {"mission": _mission_view(row),
                "submit": {"ok": False, "reason": "compliance_not_approved"}}

    submit = await higgbot_adapter.submit_mission(db, mp)
    if not submit.get("ok"):
        row.status = MissionStatus.BLOCKED.value
    elif submit.get("simulated"):
        row.status = MissionStatus.COMPLETED.value      # simulation completes logically
    elif submit.get("dispatched"):
        row.status = MissionStatus.RUNNING.value         # ATHENA/HIGGBOT work async
    row.result = submit
    await db.flush()
    return {"mission": _mission_view(row), "submit": submit}


@router.get("/ecosystem/higgbot/health")
async def higgbot_health(
    db: AsyncSession = Depends(get_db),
    user: str = Depends(get_current_user),
):
    return await higgbot_adapter.health(db)


@router.get("/ecosystem/higgbot/capabilities")
async def higgbot_capabilities(user: str = Depends(get_current_user)):
    return await higgbot_adapter.capabilities()


@router.get("/ecosystem/queue/stats")
async def queue_stats(
    db: AsyncSession = Depends(get_db),
    user: str = Depends(get_current_user),
):
    return await mission_queue.stats(db)


@router.get("/ecosystem/flags")
async def get_flags(
    db: AsyncSession = Depends(get_db),
    user: str = Depends(get_current_user),
):
    return await flags.snapshot(db)


@router.post("/ecosystem/flags/{name}")
async def set_flag(
    name: str,
    value: bool = Body(..., embed=True),
    db: AsyncSession = Depends(get_db),
    user: str = Depends(get_current_user),
):
    """Flip a kill switch (SYSTEM_PAUSE, MESSAGING_PAUSE, ...)."""
    name = name.upper()
    if name not in PAUSE_FLAGS:
        raise HTTPException(status_code=400, detail=f"unknown flag; allowed: {PAUSE_FLAGS}")
    await flags.set(db, name, bool(value))
    logger.info(f"kill switch {name}={value} set by {user}")
    return await flags.snapshot(db)


# ----------------------------------------------- LUCIUS control surface (Phase 5)
@router.get("/ecosystem/control/status")
async def control_status(
    db: AsyncSession = Depends(get_db),
    user: str = Depends(get_current_user),
):
    """One consolidated snapshot LUCIUS reads back to the owner: mode, kill
    switches, queue depth, pending approvals + handoffs, executor health."""
    return await control_surface.status(db)


@router.post("/ecosystem/control/pause")
async def control_pause(
    scope: str = Body(..., embed=True),
    db: AsyncSession = Depends(get_db),
    user: str = Depends(get_current_user),
):
    """Voice-friendly pause by scope (all·messaging·publishing·outbound·nxg·ibc·
    higgbot·athena·creative·social·…)."""
    out = await control_surface.pause(db, scope, actor=user)
    if not out.get("ok"):
        raise HTTPException(status_code=400,
                            detail=f"unknown scope; allowed: {sorted(set(SCOPE_TO_FLAG))}")
    return out


@router.post("/ecosystem/control/resume")
async def control_resume(
    scope: str = Body(..., embed=True),
    db: AsyncSession = Depends(get_db),
    user: str = Depends(get_current_user),
):
    """Voice-friendly resume by scope (inverse of pause)."""
    out = await control_surface.resume(db, scope, actor=user)
    if not out.get("ok"):
        raise HTTPException(status_code=400,
                            detail=f"unknown scope; allowed: {sorted(set(SCOPE_TO_FLAG))}")
    return out


@router.get("/ecosystem/control/approvals")
async def control_approvals(
    db: AsyncSession = Depends(get_db),
    user: str = Depends(get_current_user),
):
    """Missions held by the compliance gate, awaiting owner approval."""
    return {"pending": await control_surface.pending_approvals(db)}


@router.post("/ecosystem/control/approvals/{mission_id}/approve")
async def control_approve(
    mission_id: str,
    db: AsyncSession = Depends(get_db),
    user: str = Depends(get_current_user),
):
    ok = await control_surface.approve(db, mission_id)
    return {"ok": ok, "mission_id": mission_id}


@router.get("/ecosystem/control/handoffs")
async def control_handoffs(
    db: AsyncSession = Depends(get_db),
    user: str = Depends(get_current_user),
):
    """Work needing a human: escalated + explicit human-handoff missions."""
    return {"pending": await control_surface.pending_handoffs(db)}


@router.post("/ecosystem/control/handoffs/{mission_id}/resolve")
async def control_resolve_handoff(
    mission_id: str,
    note: str = Body("", embed=True),
    db: AsyncSession = Depends(get_db),
    user: str = Depends(get_current_user),
):
    ok = await control_surface.resolve_handoff(db, mission_id, note=note)
    return {"ok": ok, "mission_id": mission_id}


@router.get("/ecosystem/lucius/health")
async def lucius_health(
    db: AsyncSession = Depends(get_db),
    user: str = Depends(get_current_user),
):
    return await lucius_adapter.health(db)


@router.get("/ecosystem/lucius/capabilities")
async def lucius_capabilities(user: str = Depends(get_current_user)):
    return await lucius_adapter.capabilities()
