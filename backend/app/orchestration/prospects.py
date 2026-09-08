"""
Prospect memory (directive §19) — durable per-prospect conversation state.

A thin async service over the `prospects` table: upsert, record a turn (bounded
inline history), advance the stage, and honor an opt-out. Persisted so a
conversation survives across sessions and the strategist can reason over history.
"""
from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..utils.logger import logger
from .mission import ConversationStage

_MAX_TURNS = 40


class ProspectMemory:
    async def get(self, db: AsyncSession, prospect_id: str):
        from ..models.orchestration import Prospect
        return (await db.execute(
            select(Prospect).where(Prospect.prospect_id == prospect_id)
        )).scalars().first()

    async def upsert(self, db: AsyncSession, prospect_id: str, brand: str,
                     platform: str, handle: Optional[str] = None,
                     concern: Optional[str] = None):
        from ..models.orchestration import Prospect
        row = await self.get(db, prospect_id)
        if row is None:
            row = Prospect(
                prospect_id=prospect_id, brand=brand, platform=platform,
                handle=handle, concern=concern,
                stage=ConversationStage.NEW.value, turns=[], notes={},
            )
            db.add(row)
        else:
            if handle:
                row.handle = handle
            if concern:
                row.concern = concern
        await db.flush()
        return row

    async def record_turn(self, db: AsyncSession, prospect_id: str, role: str,
                          text: str) -> None:
        row = await self.get(db, prospect_id)
        if not row:
            return
        turns: List[Dict] = list(row.turns or [])
        turns.append({"role": role, "text": (text or "")[:2000],
                      "ts": datetime.utcnow().isoformat()})
        row.turns = turns[-_MAX_TURNS:]                  # keep history bounded
        if role == "prospect":
            row.last_inbound_at = datetime.utcnow()
        await db.flush()

    async def advance(self, db: AsyncSession, prospect_id: str,
                      stage: ConversationStage, score: Optional[float] = None) -> None:
        row = await self.get(db, prospect_id)
        if not row:
            return
        row.stage = stage.value
        if score is not None:
            row.score = float(score)
        if stage == ConversationStage.DO_NOT_CONTACT:
            row.do_not_contact = True
        await db.flush()

    async def set_consent(self, db: AsyncSession, prospect_id: str, consent: bool) -> None:
        row = await self.get(db, prospect_id)
        if row:
            row.consent = bool(consent)
            await db.flush()

    async def mark_do_not_contact(self, db: AsyncSession, prospect_id: str) -> bool:
        row = await self.get(db, prospect_id)
        if not row:
            return False
        row.do_not_contact = True
        row.stage = ConversationStage.DO_NOT_CONTACT.value
        await db.flush()
        logger.info(f"prospect {prospect_id} marked do_not_contact")
        return True


prospect_memory = ProspectMemory()
