"""
Conversation state machine (directive §19) — the persistent stages a prospect
moves through, and the guarded transitions between them.

Pure and DB-free: allowed transitions, terminal states, signal classification, and
next-best-action all unit-test without a database. The strategist agent and the
prospect-memory service build on this.

The machine is conservative by design: high-intent or licensed-activity signals
route to a human, and a stop/opt-out signal is always honored immediately
(directive §31 compliance, §20 human handoff).
"""
from __future__ import annotations

import re
from typing import Dict, Set

from .mission import ConversationStage

# Terminal stages — no autonomous action continues from here.
TERMINAL_STAGES: Set[ConversationStage] = {
    ConversationStage.OUTCOME, ConversationStage.DO_NOT_CONTACT,
    ConversationStage.UNQUALIFIED, ConversationStage.BLOCKED,
}

# Stages that hand control to a person (not terminal, but no autonomous message).
HUMAN_STAGES: Set[ConversationStage] = {
    ConversationStage.HUMAN_HANDOFF, ConversationStage.ROUTED, ConversationStage.QUALIFIED,
}

# Allowed forward transitions. Any stage may always fall to a stop/do-not-contact
# (handled in next_stage), so those are omitted here.
ALLOWED_TRANSITIONS: Dict[ConversationStage, Set[ConversationStage]] = {
    ConversationStage.NEW: {ConversationStage.OBSERVED, ConversationStage.ENGAGED},
    ConversationStage.OBSERVED: {ConversationStage.ENGAGED, ConversationStage.NURTURE},
    ConversationStage.ENGAGED: {ConversationStage.OPEN, ConversationStage.NURTURE},
    ConversationStage.OPEN: {ConversationStage.DISCOVERY, ConversationStage.NURTURE},
    ConversationStage.DISCOVERY: {ConversationStage.CLASSIFIED, ConversationStage.NURTURE},
    ConversationStage.CLASSIFIED: {ConversationStage.PERMISSION, ConversationStage.NURTURE,
                                   ConversationStage.UNQUALIFIED},
    ConversationStage.PERMISSION: {ConversationStage.QUALIFIED, ConversationStage.NURTURE},
    ConversationStage.QUALIFIED: {ConversationStage.ROUTED, ConversationStage.HUMAN_HANDOFF},
    ConversationStage.ROUTED: {ConversationStage.HUMAN_HANDOFF, ConversationStage.OUTCOME},
    ConversationStage.HUMAN_HANDOFF: {ConversationStage.OUTCOME},
    ConversationStage.NURTURE: {ConversationStage.ENGAGED, ConversationStage.OPEN},
}

# --- inbound signal classification (keyword heuristic; a model can refine later) ---
_STOP = re.compile(r"\b(stop|unsubscribe|leave me alone|not interested|remove me|go away)\b", re.I)
_HIGH_INTENT = re.compile(r"\b(sign up|how much|price|quote|buy|ready|call me|get started|apply|enroll)\b", re.I)
_LICENSED = re.compile(r"\b(should i buy|which policy|how much coverage|is .* right for me|advice|recommend)\b", re.I)
_QUESTION = re.compile(r"\?")
_OBJECTION = re.compile(r"\b(too expensive|scam|don'?t trust|no thanks|maybe later|busy)\b", re.I)
_INTEREST = re.compile(r"\b(interested|tell me more|curious|sounds good|how does|what about|learn more)\b", re.I)


def classify_signal(message: str) -> str:
    """Classify an inbound message into a coarse conversation signal."""
    m = (message or "").strip()
    if not m:
        return "empty"
    if _STOP.search(m):
        return "stop"
    if _HIGH_INTENT.search(m) or _LICENSED.search(m):
        return "high_intent"      # → route to a human (never auto-advise)
    if _OBJECTION.search(m):
        return "objection"
    if _INTEREST.search(m):
        return "interest"
    if _QUESTION.search(m):
        return "question"
    return "neutral"


def requires_human(signal: str, message: str = "") -> bool:
    """High intent or anything that looks like a request for individualized,
    licensed advice must go to a person (directive §20, §31)."""
    return signal == "high_intent" or bool(_LICENSED.search(message or ""))


def can_transition(current: ConversationStage, nxt: ConversationStage) -> bool:
    if nxt in (ConversationStage.DO_NOT_CONTACT,):
        return True                                   # opt-out always allowed
    return nxt in ALLOWED_TRANSITIONS.get(current, set())


def next_stage(current: ConversationStage, signal: str) -> ConversationStage:
    """Compute the next stage from the current stage + inbound signal, staying
    within allowed transitions. Never advances out of a terminal stage."""
    if current in TERMINAL_STAGES:
        return current
    if signal == "stop":
        return ConversationStage.DO_NOT_CONTACT
    if signal == "high_intent":
        # jump toward qualification/handoff from wherever we are
        return (ConversationStage.QUALIFIED if current in (
            ConversationStage.PERMISSION, ConversationStage.CLASSIFIED,
            ConversationStage.DISCOVERY) else ConversationStage.HUMAN_HANDOFF)

    # normal forward progression by one step along the happy path
    happy = {
        ConversationStage.NEW: ConversationStage.ENGAGED,
        ConversationStage.OBSERVED: ConversationStage.ENGAGED,
        ConversationStage.ENGAGED: ConversationStage.OPEN,
        ConversationStage.OPEN: ConversationStage.DISCOVERY,
        ConversationStage.DISCOVERY: ConversationStage.CLASSIFIED,
        ConversationStage.CLASSIFIED: ConversationStage.PERMISSION,
        ConversationStage.PERMISSION: ConversationStage.QUALIFIED,
        ConversationStage.NURTURE: ConversationStage.ENGAGED,
    }
    if signal == "objection":
        return ConversationStage.NURTURE if current not in TERMINAL_STAGES else current
    target = happy.get(current, current)
    return target if can_transition(current, target) else current


def recommend_action(stage: ConversationStage, signal: str) -> str:
    """The next best action label for a stage + signal (used by the strategist)."""
    if signal == "stop":
        return "honor_opt_out"
    if signal == "high_intent":
        return "route_to_human"
    return {
        ConversationStage.NEW: "observe_or_engage",
        ConversationStage.OBSERVED: "engage",
        ConversationStage.ENGAGED: "open_conversation",
        ConversationStage.OPEN: "ask_discovery_question",
        ConversationStage.DISCOVERY: "classify_need",
        ConversationStage.CLASSIFIED: "request_permission",
        ConversationStage.PERMISSION: "qualify",
        ConversationStage.QUALIFIED: "route_to_human",
        ConversationStage.NURTURE: "nurture_value",
    }.get(stage, "nurture_value")
