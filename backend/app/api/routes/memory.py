"""
Shared Memory API — the ORELIUS <-> LUCIUS hub.

LUCIUS calls these to keep a common memory with ORELIUS:
  POST /api/memory   -> record an event (what LUCIUS just did)
  GET  /api/memory   -> read recent shared events (what ORELIUS did, and history)

Machine-to-machine auth via the `X-Shared-Secret` header, which must equal the
LUCIUS_SHARED_SECRET configured on ORELIUS. (No JWT — this is a service link.)
"""
from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from ...database import get_db
from ...core.shared_memory import shared_memory
from ...config import settings
from ...utils.logger import logger

router = APIRouter()


class MemoryEventIn(BaseModel):
    content: str
    kind: str = "action"
    actor: str = "LUCIUS"
    meta: Optional[dict] = None


def _require_secret(x_shared_secret: Optional[str]) -> None:
    if not settings.lucius_shared_secret:
        raise HTTPException(
            status_code=503,
            detail="Shared memory is not configured. Set LUCIUS_SHARED_SECRET on ORELIUS.",
        )
    if x_shared_secret != settings.lucius_shared_secret:
        raise HTTPException(status_code=401, detail="Invalid shared-memory secret")


@router.post("/memory")
async def write_memory(
    event: MemoryEventIn,
    db: AsyncSession = Depends(get_db),
    x_shared_secret: Optional[str] = Header(default=None, alias="X-Shared-Secret"),
):
    """LUCIUS records an event into the shared memory."""
    _require_secret(x_shared_secret)
    saved = await shared_memory.remember(
        db,
        content=event.content,
        kind=event.kind,
        actor=event.actor or "LUCIUS",
        meta=event.meta,
    )
    logger.info(f"Shared memory write from {saved['actor']} ({saved['kind']})")
    return {"ok": True, "event": saved}


@router.get("/memory")
async def read_memory(
    limit: int = Query(default=20, ge=1, le=100),
    actor: Optional[str] = Query(default=None),
    db: AsyncSession = Depends(get_db),
    x_shared_secret: Optional[str] = Header(default=None, alias="X-Shared-Secret"),
):
    """LUCIUS reads recent shared events (newest last)."""
    _require_secret(x_shared_secret)
    events = await shared_memory.recall(db, limit=limit, actor=actor)
    return {"events": events, "count": len(events)}
