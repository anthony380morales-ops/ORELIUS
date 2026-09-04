"""
System status and health endpoints
"""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from ...database import get_db
from ...core import oreilus_engine
from ...models.conversation import Conversation, Message
from ...models.audit_log import AuditLog
from ...models.task import Task
from ...utils.logger import logger
import psutil
import datetime

router = APIRouter()


@router.get("/system/daily-report")
async def daily_report(db: AsyncSession = Depends(get_db)):
    """Concise 'wake-up' status report ORELIUS greets the Master with each day.

    Covers system health, automation pass/fail (only), and memory — cheaply (no
    live Claude call), so the chat can show it on open without burning credits.
    """
    from ...config import settings
    from ...models.report import Report, ReportType
    from ...models.shared_memory import SharedMemoryEvent

    now = datetime.datetime.utcnow()

    # --- System health (light checks, no external calls) ---
    components: dict = {}
    db_ok = True
    try:
        await db.execute(select(func.count()).select_from(SharedMemoryEvent))
    except Exception as e:  # noqa: BLE001
        db_ok = False
        logger.debug(f"daily-report db check failed: {e}")
    components["database"] = "online" if db_ok else "error"
    components["brain"] = "configured" if settings.anthropic_api_key else "missing key"
    components["shared_memory"] = "online" if settings.lucius_shared_secret else "disabled"
    healthy = db_ok and bool(settings.anthropic_api_key)
    system_health = "Operational" if healthy else "Degraded"

    # --- Automation: finance briefing pass/fail (only) ---
    finance = {"status": "No run yet", "last_run": None}
    try:
        last = (
            await db.execute(
                select(Report)
                .where(Report.report_type == ReportType.BANKING_INTELLIGENCE)
                .order_by(Report.created_at.desc())
                .limit(1)
            )
        ).scalars().first()
        if last:
            age_h = (now - last.report_date).total_seconds() / 3600 if last.report_date else 999
            ok = bool(last.content and last.content.get("sources"))
            fresh = age_h <= 30  # ran within the last day-ish
            finance = {
                "status": "PASS" if (ok and fresh) else ("STALE" if ok else "FAIL"),
                "last_run": last.report_date.isoformat() if last.report_date else None,
            }
    except Exception as e:  # noqa: BLE001
        logger.debug(f"daily-report finance check failed: {e}")

    # --- Memory footprint ---
    memory = {"shared_events": 0, "reports": 0, "conversations": 0}
    try:
        memory["shared_events"] = (
            await db.execute(select(func.count()).select_from(SharedMemoryEvent))
        ).scalar() or 0
        memory["reports"] = (
            await db.execute(select(func.count()).select_from(Report))
        ).scalar() or 0
        memory["conversations"] = (
            await db.execute(select(func.count()).select_from(Conversation))
        ).scalar() or 0
    except Exception as e:  # noqa: BLE001
        logger.debug(f"daily-report memory check failed: {e}")

    # --- Assemble the spoken report ---
    tick = {"PASS": "✅", "FAIL": "❌", "STALE": "⚠️", "No run yet": "—"}.get(finance["status"], "—")
    lines = [
        f"**Good day, Master.** Here is your status report — {now:%A, %d %B %Y} (UTC).",
        "",
        f"**System Health:** {'🟢' if healthy else '🔴'} {system_health}",
        f"- Brain: {components['brain']} · Database: {components['database']} · Shared memory: {components['shared_memory']}",
        "",
        "**Automations:**",
        f"- Daily Financial Intelligence: {tick} {finance['status']}"
        + (f" (last run {finance['last_run'][:10]})" if finance.get("last_run") else ""),
        "",
        "**Memory:**",
        f"- {memory['shared_events']} shared events · {memory['reports']} reports · {memory['conversations']} conversations on record",
        "",
        "All systems reporting. How may I serve you today, Master?",
    ]

    return {
        "date": now.isoformat(),
        "system_health": system_health,
        "components": components,
        "automation": {"finance_brief": finance},
        "memory": memory,
        "report_markdown": "\n".join(lines),
    }


@router.get("/system/optimization")
async def get_optimization_stats():
    """
    Credit-saver stats: model in use, cache hit rates, token usage, estimated
    USD cost and savings. Lets the Master see that ORELIUS is running lean.
    """
    try:
        return oreilus_engine.optimization_stats()
    except Exception as e:
        logger.error(f"Optimization stats error: {e}")
        return {"error": str(e)}


@router.get("/system/status")
async def get_system_status(db: AsyncSession = Depends(get_db)):
    """
    Get comprehensive system status

    Returns:
        System status information
    """
    try:
        # Validate O.R.E.I.L.U.S. core
        core_status = await oreilus_engine.validate_system()

        # Get database statistics
        conversations_count = await db.scalar(select(func.count(Conversation.id)))
        messages_count = await db.scalar(select(func.count(Message.id)))
        audit_logs_count = await db.scalar(select(func.count(AuditLog.id)))

        # Get system resources
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')

        return {
            "status": core_status["status"],
            "components": core_status["components"],
            "database": {
                "conversations": conversations_count,
                "messages": messages_count,
                "audit_logs": audit_logs_count,
            },
            "resources": {
                "cpu_percent": cpu_percent,
                "memory_percent": memory.percent,
                "memory_available_gb": round(memory.available / (1024 ** 3), 2),
                "disk_percent": disk.percent,
                "disk_free_gb": round(disk.free / (1024 ** 3), 2),
            },
            "timestamp": datetime.datetime.utcnow().isoformat(),
        }

    except Exception as e:
        logger.error(f"System status error: {e}")
        return {
            "status": "error",
            "error": str(e),
        }


@router.get("/system/logs")
async def get_audit_logs(
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
):
    """
    Get recent audit logs

    Args:
        limit: Number of logs to retrieve
        db: Database session

    Returns:
        Recent audit logs
    """
    try:
        query = (
            select(AuditLog)
            .order_by(AuditLog.created_at.desc())
            .limit(limit)
        )
        result = await db.execute(query)
        logs = result.scalars().all()

        return [
            {
                "id": log.id,
                "event_type": log.event_type.value,
                "severity": log.severity.value,
                "user_id": log.user_id,
                "description": log.description,
                "metadata": log.event_metadata,
                "created_at": log.created_at.isoformat(),
            }
            for log in logs
        ]

    except Exception as e:
        logger.error(f"Get audit logs error: {e}")
        return []


@router.get("/system/metrics")
async def get_system_metrics(db: AsyncSession = Depends(get_db)):
    """
    Get system metrics and statistics

    Returns:
        System metrics
    """
    try:
        # Message statistics
        total_messages = await db.scalar(select(func.count(Message.id)))
        total_tokens = await db.scalar(select(func.sum(Message.token_count)))

        # Recent activity (last 24 hours)
        one_day_ago = datetime.datetime.utcnow() - datetime.timedelta(days=1)
        recent_messages = await db.scalar(
            select(func.count(Message.id)).where(Message.created_at >= one_day_ago)
        )

        # Audit log statistics
        total_audit_logs = await db.scalar(select(func.count(AuditLog.id)))
        security_alerts = await db.scalar(
            select(func.count(AuditLog.id)).where(
                AuditLog.severity.in_(["warning", "error", "critical"])
            )
        )

        return {
            "messages": {
                "total": total_messages,
                "total_tokens": total_tokens,
                "last_24h": recent_messages,
            },
            "security": {
                "total_audit_logs": total_audit_logs,
                "security_alerts": security_alerts,
            },
            "timestamp": datetime.datetime.utcnow().isoformat(),
        }

    except Exception as e:
        logger.error(f"Get metrics error: {e}")
        return {"error": str(e)}
