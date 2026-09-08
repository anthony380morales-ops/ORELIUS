"""
Conversation engine (directive §19, §20) — coordinates one inbound turn end to end:
persist it, decide the next action + a policy-safe draft, advance the stored stage,
and on a human-handoff signal alert LUCIUS.

Simulation-first: a draft is produced but NEVER sent here — sending is a live-mode
executor action. An opt-out is honored immediately and durably.
"""
from __future__ import annotations

from typing import Dict, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from ..utils.logger import logger
from .mission import ConversationStage
from .prospects import prospect_memory
from .agents.conversation_strategist import conversation_strategist
from .adapters import lucius_adapter


class ConversationEngine:
    async def handle_inbound(self, db: AsyncSession, prospect_id: str, brand: str,
                             platform: str, message: str, handle: Optional[str] = None,
                             concern: Optional[str] = None, drafter=None) -> Dict:
        """Process one inbound message and return the strategist's decision."""
        row = await prospect_memory.upsert(db, prospect_id, brand, platform,
                                           handle=handle, concern=concern)

        # Respect a standing opt-out — never re-engage.
        if row.do_not_contact:
            return {"ok": True, "prospect_id": prospect_id, "action": "suppressed",
                    "reason": "do_not_contact", "draft_message": None}

        await prospect_memory.record_turn(db, prospect_id, "prospect", message)

        decision = await conversation_strategist.decide(
            prospect_id=prospect_id, current_stage=row.stage,
            inbound_message=message, concern=row.concern or (concern or ""),
            drafter=drafter,
        )

        # Advance the durable stage.
        try:
            nxt = ConversationStage(decision.next_stage)
        except ValueError:
            nxt = ConversationStage(row.stage)
        await prospect_memory.advance(db, prospect_id, nxt)

        # Record the (unsent) draft so the thread history is complete.
        if decision.draft_message:
            await prospect_memory.record_turn(db, prospect_id, "agent_draft",
                                              decision.draft_message)

        # Human handoff → alert the owner via LUCIUS (owner comms are never gated).
        if decision.needs_human:
            await lucius_adapter.announce_handoff(
                db, mission_id=prospect_id,
                detail=f"High-intent conversation on {platform} ({brand}). "
                       f"They said: {message[:200]}")
            logger.info(f"conversation {prospect_id} routed to human")

        # Record this interaction as a meaningful touchpoint (feedback loop → Phase
        # 10 allocation). qualified when it reaches qualification/handoff; meaningful
        # when we produced a genuine reply; none when nothing actionable happened.
        outcome = ("qualified" if (decision.needs_human or nxt in (
                       ConversationStage.QUALIFIED, ConversationStage.ROUTED,
                       ConversationStage.HUMAN_HANDOFF))
                   else "meaningful" if decision.draft_message else "none")
        try:
            from .analytics import analytics
            await analytics.record_touchpoint(
                db, brand=brand, action="reply", outcome=outcome,
                platform=platform, prospect_id=prospect_id)
        except Exception as e:  # noqa: BLE001 - telemetry must not break the reply
            logger.debug(f"touchpoint record skipped: {e}")

        out = decision.model_dump(mode="json")
        out["ok"] = True
        out["touchpoint_outcome"] = outcome
        return out


conversation_engine = ConversationEngine()
