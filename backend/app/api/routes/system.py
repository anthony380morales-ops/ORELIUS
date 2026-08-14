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
