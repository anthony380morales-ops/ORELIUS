"""
Durable mission queue (directive §9) — Postgres-backed source of truth.

Provides idempotency, duplicate detection, priority, retries with exponential
backoff, a dead-letter terminal state, scheduled execution, expiration, and
cancellation. Postgres is the durable store; a Redis fast-path can layer on later
without changing this contract.

Pure helpers (priority rank, backoff, dedup key) are separated so they unit-test
with no database; the async methods are integration-tested against SQLite.
"""
from __future__ import annotations

import hashlib
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from ..utils.logger import logger
from .mission import MissionPacket, MissionStatus, ComplianceStatus

# States a mission can still move out of (not terminal).
ACTIVE_STATES = {
    MissionStatus.CREATED.value, MissionStatus.VALIDATING.value,
    MissionStatus.QUEUED.value, MissionStatus.RUNNING.value,
    MissionStatus.WAITING.value, MissionStatus.BLOCKED.value,
}
TERMINAL_STATES = {
    MissionStatus.COMPLETED.value, MissionStatus.FAILED.value,
    MissionStatus.CANCELLED.value, MissionStatus.EXPIRED.value,
}

_PRIORITY_RANK = {"urgent": 0, "high": 1, "medium": 2, "low": 3}


# ------------------------------------------------------------------- pure helpers
def priority_rank(priority: str) -> int:
    return _PRIORITY_RANK.get((priority or "medium").lower(), 2)


def backoff_seconds(attempt: int, base: int = 30, cap: int = 3600) -> int:
    """Exponential backoff for retry #attempt (1-based), capped."""
    if attempt < 1:
        attempt = 1
    return min(cap, base * (2 ** (attempt - 1)))


def dedup_key_for(packet: MissionPacket) -> str:
    """Stable key so the same intent isn't queued twice in one day."""
    topic = packet.topic.title if packet.topic else ""
    day = packet.created_at.astimezone(timezone.utc).strftime("%Y-%m-%d")
    raw = f"{packet.brand.value}|{packet.platform.value}|{packet.objective.value}|{topic}|{day}"
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


def _now() -> datetime:
    # Naive UTC to match the model's DateTime columns / server defaults.
    return datetime.now(timezone.utc).replace(tzinfo=None)


class MissionQueue:
    """Async, durable queue over the `missions` table."""

    async def enqueue(self, db: AsyncSession, packet: MissionPacket,
                      executor: str = "athena") -> "object":
        from ..models.orchestration import Mission
        packet.with_default_expiry()
        key = dedup_key_for(packet)

        # Idempotency / duplicate detection: reuse an active mission with same intent.
        existing = (await db.execute(
            select(Mission).where(Mission.dedup_key == key)
            .where(Mission.status.in_(list(ACTIVE_STATES)))
        )).scalars().first()
        if existing:
            logger.info(f"mission dedup hit: {existing.mission_id} (key {key[:8]})")
            return existing

        # A mission may only be QUEUED once compliance is approved; else it is held.
        approved = packet.compliance.status == ComplianceStatus.APPROVED
        status = MissionStatus.QUEUED.value if approved else MissionStatus.BLOCKED.value

        expires = packet.expires_at.replace(tzinfo=None) if packet.expires_at else None
        row = Mission(
            mission_id=packet.mission_id, status=status,
            brand=packet.brand.value, platform=packet.platform.value,
            objective=packet.objective.value, priority=packet.priority.value,
            packet=packet.model_dump(mode="json"), result={},
            dedup_key=key, attempts=0, max_attempts=3,
            executor=executor, expires_at=expires,
        )
        db.add(row)
        await db.flush()
        logger.info(f"mission enqueued: {row.mission_id} status={status}")
        return row

    async def claim_next(self, db: AsyncSession,
                         executor: Optional[str] = None) -> Optional["object"]:
        """Claim the highest-priority due mission and mark it RUNNING."""
        from ..models.orchestration import Mission
        now = _now()
        q = (select(Mission)
             .where(Mission.status == MissionStatus.QUEUED.value)
             .where((Mission.scheduled_at.is_(None)) | (Mission.scheduled_at <= now))
             .where((Mission.next_attempt_at.is_(None)) | (Mission.next_attempt_at <= now))
             .where((Mission.expires_at.is_(None)) | (Mission.expires_at > now)))
        if executor:
            q = q.where(Mission.executor == executor)
        rows = (await db.execute(q)).scalars().all()
        if not rows:
            return None
        rows.sort(key=lambda m: (priority_rank(m.priority), m.created_at or now))
        row = rows[0]
        row.status = MissionStatus.RUNNING.value
        await db.flush()
        return row

    async def complete(self, db: AsyncSession, mission_id: str,
                       result: Dict, cost_usd: float = 0.0) -> None:
        row = await self.get(db, mission_id)
        if not row:
            return
        row.status = MissionStatus.COMPLETED.value
        row.result = result or {}
        row.cost_usd = (row.cost_usd or 0.0) + float(cost_usd or 0.0)
        await db.flush()

    async def fail(self, db: AsyncSession, mission_id: str, error: str,
                   retryable: bool = True) -> str:
        """Record a failure; requeue with backoff or dead-letter after max attempts."""
        row = await self.get(db, mission_id)
        if not row:
            return "missing"
        row.attempts = (row.attempts or 0) + 1
        row.error = (error or "")[:512]
        if retryable and row.attempts < (row.max_attempts or 3):
            row.status = MissionStatus.QUEUED.value
            row.next_attempt_at = _now() + timedelta(seconds=backoff_seconds(row.attempts))
            await db.flush()
            return "requeued"
        row.status = MissionStatus.FAILED.value      # dead-letter
        await db.flush()
        return "dead_letter"

    async def escalate(self, db: AsyncSession, mission_id: str, reason: str = "") -> None:
        row = await self.get(db, mission_id)
        if row and row.status not in TERMINAL_STATES:
            row.status = MissionStatus.ESCALATED.value
            row.error = (reason or "")[:512]
            await db.flush()

    async def approve(self, db: AsyncSession, mission_id: str) -> bool:
        """Compliance cleared a held mission → make it runnable."""
        row = await self.get(db, mission_id)
        if row and row.status == MissionStatus.BLOCKED.value:
            row.status = MissionStatus.QUEUED.value
            await db.flush()
            return True
        return False

    async def cancel(self, db: AsyncSession, mission_id: str) -> bool:
        row = await self.get(db, mission_id)
        if row and row.status not in TERMINAL_STATES:
            row.status = MissionStatus.CANCELLED.value
            await db.flush()
            return True
        return False

    async def retry(self, db: AsyncSession, mission_id: str) -> bool:
        """Requeue a failed/cancelled mission for another run."""
        row = await self.get(db, mission_id)
        if row and row.status in (MissionStatus.FAILED.value, MissionStatus.CANCELLED.value):
            row.status = MissionStatus.QUEUED.value
            row.next_attempt_at = None
            row.error = None
            await db.flush()
            return True
        return False

    async def expire_due(self, db: AsyncSession) -> int:
        """Mark past-expiry, non-terminal missions EXPIRED. Returns count."""
        from ..models.orchestration import Mission
        now = _now()
        rows = (await db.execute(
            select(Mission)
            .where(Mission.expires_at.is_not(None)).where(Mission.expires_at <= now)
            .where(Mission.status.in_(list(ACTIVE_STATES)))
        )).scalars().all()
        for r in rows:
            r.status = MissionStatus.EXPIRED.value
        if rows:
            await db.flush()
        return len(rows)

    async def get(self, db: AsyncSession, mission_id: str) -> Optional["object"]:
        from ..models.orchestration import Mission
        return (await db.execute(
            select(Mission).where(Mission.mission_id == mission_id)
        )).scalars().first()

    async def stats(self, db: AsyncSession) -> Dict:
        from ..models.orchestration import Mission
        rows = (await db.execute(
            select(Mission.status, func.count()).group_by(Mission.status)
        )).all()
        by_status = {s: c for s, c in rows}
        return {
            "by_status": by_status,
            "total": sum(by_status.values()),
            "queue_depth": by_status.get(MissionStatus.QUEUED.value, 0),
            "running": by_status.get(MissionStatus.RUNNING.value, 0),
            "dead_letter": by_status.get(MissionStatus.FAILED.value, 0),
            "blocked": by_status.get(MissionStatus.BLOCKED.value, 0),
        }


mission_queue = MissionQueue()
