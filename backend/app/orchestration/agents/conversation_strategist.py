"""
Conversation Strategist agent (directive §6, §19, §20, registry id
`conversation_strategist`).

Given a prospect's current stage and their latest inbound message, it decides the
next best action and — when a message is appropriate — drafts a HUMAN-sounding
reply that is guaranteed to satisfy the autonomous-messaging policy.

Non-negotiables enforced here (directive: messaging humanization):
  • The absolute rule: an autonomous message NEVER contains "--". Every draft is
    run through messaging_policy.enforce(), so the returned text cannot contain it.
  • No manufactured urgency, no canned sales phrases, one primary question, respond
    to what the person actually said.
  • High intent or anything resembling licensed/individualized advice → route to a
    human; the agent produces NO autonomous message in that case.
  • A stop/opt-out is honored immediately; no message is sent.

Simulation-first: the strategist DRAFTS; it never sends. Sending is a live-mode
executor action gated by the kill switches.
"""
from __future__ import annotations

from typing import Dict, List, Optional

from pydantic import BaseModel

from ..mission import ConversationStage
from ..messaging_policy import enforce, validate_autonomous_message, HUMANIZATION_SYSTEM_PROMPT
from ..conversation import (
    classify_signal, next_stage, recommend_action, requires_human, TERMINAL_STAGES,
)
from ...utils.logger import logger


class ConversationDecision(BaseModel):
    prospect_id: str
    signal: str
    current_stage: str
    next_stage: str
    action: str
    needs_human: bool = False
    draft_message: Optional[str] = None
    message_ok: bool = True
    issues: List[str] = []
    sent: bool = False              # always False here — strategist never sends


def _template_reply(stage: ConversationStage, signal: str, concern: str = "") -> str:
    """Deterministic, human-sounding fallback draft (no model call needed).

    Kept plain and curious, one question, no urgency, no canned lines, and never
    containing the forbidden sequence."""
    c = (concern or "").strip().lower()
    if signal == "objection":
        return "totally fair. what would make it feel worth a closer look for you?"
    if signal == "question":
        return "good question. happy to walk through it. what part matters most to you right now?"
    by_stage = {
        ConversationStage.NEW: "hey, appreciated you reaching out. what got you thinking about this?",
        ConversationStage.OBSERVED: "saw your note. what's on your mind with it?",
        ConversationStage.ENGAGED: "that makes sense. what's the piece you're weighing most?",
        ConversationStage.OPEN: "got it. when you picture getting this sorted, what does good look like for you?",
        ConversationStage.DISCOVERY: (
            f"that helps. so it sounds like {c or 'protecting what matters'} is the real priority. "
            "did i read that right?"),
        ConversationStage.CLASSIFIED: "makes sense. would it help if i shared a couple of options that fit that?",
        ConversationStage.PERMISSION: "happy to go deeper whenever you want. want me to lay it out?",
        ConversationStage.NURTURE: "no rush at all. i'll leave you with something useful and you reach out when it fits.",
    }
    return by_stage.get(stage, "appreciate you. what's the main thing you're hoping to figure out?")


class ConversationStrategistAgent:
    async def decide(self, prospect_id: str, current_stage: str, inbound_message: str,
                     concern: str = "", drafter=None) -> ConversationDecision:
        """Decide next action + (maybe) a policy-safe draft. `drafter`, if given, is
        an async fn(system_prompt, user_prompt)->str used to generate the reply; when
        omitted a deterministic human-sounding template is used (no model call)."""
        try:
            stage = ConversationStage(current_stage)
        except ValueError:
            stage = ConversationStage.NEW

        signal = classify_signal(inbound_message)
        nxt = next_stage(stage, signal)
        action = recommend_action(stage, signal)

        # Opt-out → honor immediately, no message.
        if signal == "stop":
            return ConversationDecision(
                prospect_id=prospect_id, signal=signal, current_stage=stage.value,
                next_stage=ConversationStage.DO_NOT_CONTACT.value, action="honor_opt_out",
                needs_human=False, draft_message=None)

        # High intent / licensed-advice request → route to a human, no auto message.
        if requires_human(signal, inbound_message):
            return ConversationDecision(
                prospect_id=prospect_id, signal=signal, current_stage=stage.value,
                next_stage=nxt.value, action="route_to_human", needs_human=True,
                draft_message=None)

        # Terminal stage → nothing to say.
        if stage in TERMINAL_STAGES:
            return ConversationDecision(
                prospect_id=prospect_id, signal=signal, current_stage=stage.value,
                next_stage=stage.value, action="none", needs_human=False,
                draft_message=None)

        # Draft a reply: try the model drafter, else deterministic template.
        draft = ""
        if drafter is not None:
            try:
                draft = await drafter(HUMANIZATION_SYSTEM_PROMPT, self._draft_prompt(
                    stage, signal, inbound_message, concern))
            except Exception as e:  # noqa: BLE001 - never fail the decision on a draft
                logger.warning(f"strategist drafter failed, using template: {e}")
                draft = ""
        if not (draft or "").strip():
            draft = _template_reply(stage, signal, concern)

        # ABSOLUTE backstop: the returned text can never contain "--".
        safe, verdict = enforce(draft)
        # If a soft/hard issue remains, fall back to the known-clean template once.
        if verdict["needs_regen"]:
            safe, verdict = enforce(_template_reply(stage, signal, concern))

        return ConversationDecision(
            prospect_id=prospect_id, signal=signal, current_stage=stage.value,
            next_stage=nxt.value, action=action, needs_human=False,
            draft_message=safe, message_ok=validate_autonomous_message(safe)["ok"],
            issues=verdict.get("issues", []))

    @staticmethod
    def _draft_prompt(stage: ConversationStage, signal: str, inbound: str,
                      concern: str) -> str:
        return (
            f"Conversation stage: {stage.value}. Inbound signal: {signal}.\n"
            f"They just said: \"{inbound}\".\n"
            + (f"Their known concern: {concern}.\n" if concern else "")
            + "Write ONE short, natural reply that responds to what they actually said, "
              "stays curious, asks at most one question, and moves the conversation "
              "forward by a single step. No sales language, no urgency."
        )


conversation_strategist = ConversationStrategistAgent()
