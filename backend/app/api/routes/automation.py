"""
Automation API — scheduled/triggerable ORELIUS jobs.

Currently exposes the daily Financial Intelligence briefing:
  POST /api/automation/finance-brief         -> run it now (fetch + synthesize + store)
  GET  /api/automation/finance-brief/latest  -> read the most recent briefing

Machine-to-machine auth via the `X-Shared-Secret` header (same secret as the
shared-memory hub, LUCIUS_SHARED_SECRET). This lets a free external cron service
hit the endpoint at 8:00 AM PST daily to run the automation on schedule, even on
Render's free tier (which sleeps when idle — the cron call wakes it).
"""
from fastapi import APIRouter, Depends, Header, HTTPException
from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...database import get_db
from ...core.finance_intel import finance_intel
from ...config import settings
from ...utils.logger import logger

router = APIRouter()


def _require_secret(x_shared_secret: Optional[str]) -> None:
    if not settings.lucius_shared_secret:
        raise HTTPException(
            status_code=503,
            detail="Automation is not configured. Set LUCIUS_SHARED_SECRET on ORELIUS.",
        )
    if x_shared_secret != settings.lucius_shared_secret:
        raise HTTPException(status_code=401, detail="Invalid automation secret")


@router.post("/automation/finance-brief")
async def run_finance_brief(
    db: AsyncSession = Depends(get_db),
    x_shared_secret: Optional[str] = Header(default=None, alias="X-Shared-Secret"),
):
    """Run the daily financial intelligence briefing now (verified sources only)."""
    _require_secret(x_shared_secret)
    logger.info("Running daily financial intelligence briefing...")
    result = await finance_intel.generate_brief(db)
    logger.info(f"Finance brief complete (ok={result.get('ok')})")
    return result


@router.get("/automation/finance-brief/latest")
async def latest_finance_brief(
    db: AsyncSession = Depends(get_db),
    x_shared_secret: Optional[str] = Header(default=None, alias="X-Shared-Secret"),
):
    """Return the most recent stored financial briefing."""
    _require_secret(x_shared_secret)
    from ...models.report import Report, ReportType

    row = (
        await db.execute(
            select(Report)
            .where(Report.report_type == ReportType.BANKING_INTELLIGENCE)
            .order_by(Report.created_at.desc())
            .limit(1)
        )
    ).scalars().first()
    if not row:
        return {"ok": False, "summary": "No financial briefing has been generated yet."}
    return {
        "ok": True,
        "title": row.title,
        "summary": row.summary,
        "report_date": row.report_date.isoformat() if row.report_date else None,
        "data": row.content,
    }
