"""
System flags — kill switches and run-mode (directive §44 simulation, §46 kill switch).

Durable, DB-backed booleans that gate outbound action, layered over config defaults.
An emergency stop must immediately prevent NEW outbound actions while preserving all
queued state. Flags are checkable from the API, the dashboard, and LUCIUS.
"""
from __future__ import annotations

from enum import Enum
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..utils.logger import logger


class SocialMode(str, Enum):
    SIMULATION = "simulation"   # no real messages/publishing/engagement/spend (default)
    DRY_RUN = "dry_run"         # compute + return proposed actions, execute nothing
    LIVE = "live"               # real actions on connected providers


# The global kill switches (directive §46).
PAUSE_FLAGS = [
    "SYSTEM_PAUSE",
    "MESSAGING_PAUSE",
    "PUBLISHING_PAUSE",
    "OUTBOUND_PAUSE",
    "NXG_PAUSE",
    "IBC_PAUSE",
    "HIGGBOT_PAUSE",
    "ATHENA_PAUSE",
]


class Flags:
    """Reads durable SystemFlag rows, falling back to config/env defaults."""

    def _env_default(self, name: str) -> bool:
        # e.g. SYSTEM_PAUSE -> settings.system_pause (bool), default False.
        return bool(getattr(settings, name.lower(), False))

    async def get(self, db: AsyncSession, name: str) -> bool:
        try:
            from ..models.orchestration import SystemFlag
            row = (await db.execute(
                select(SystemFlag).where(SystemFlag.name == name)
            )).scalars().first()
            if row is not None:
                return bool(row.value)
        except Exception as e:  # noqa: BLE001 - never let a flag read break a request
            logger.debug(f"flag read {name} fell back to default: {e}")
        return self._env_default(name)

    async def set(self, db: AsyncSession, name: str, value: bool) -> None:
        from ..models.orchestration import SystemFlag
        row = (await db.execute(
            select(SystemFlag).where(SystemFlag.name == name)
        )).scalars().first()
        if row:
            row.value = bool(value)
        else:
            db.add(SystemFlag(name=name, value=bool(value)))
        await db.flush()
        logger.info(f"System flag set: {name}={value}")

    async def mode(self, db: AsyncSession) -> SocialMode:
        """Effective run mode. SYSTEM_PAUSE forces simulation regardless of config."""
        if await self.get(db, "SYSTEM_PAUSE"):
            return SocialMode.SIMULATION
        raw = str(getattr(settings, "social_automation_mode", "simulation")).lower()
        try:
            return SocialMode(raw)
        except ValueError:
            return SocialMode.SIMULATION

    async def is_simulation(self, db: AsyncSession) -> bool:
        return (await self.mode(db)) != SocialMode.LIVE

    async def outbound_allowed(self, db: AsyncSession, brand: Optional[str] = None) -> bool:
        """True only if nothing gates a real outbound action for this brand."""
        if await self.is_simulation(db):
            return False
        for f in ("SYSTEM_PAUSE", "OUTBOUND_PAUSE"):
            if await self.get(db, f):
                return False
        if brand:
            b = brand.upper()
            if b in ("NXG", "IBC") and await self.get(db, f"{b}_PAUSE"):
                return False
        return True

    async def snapshot(self, db: AsyncSession) -> dict:
        """All flags + mode, for the dashboard / LUCIUS / health checks."""
        out = {"mode": (await self.mode(db)).value}
        for f in PAUSE_FLAGS:
            out[f] = await self.get(db, f)
        return out


flags = Flags()
