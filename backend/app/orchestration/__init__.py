"""
ORELIUS orchestration layer — the executive intelligence + coordination spine for
the autonomous multi-agent ecosystem (ORELIUS ⇄ ATHENA ⇄ HIGGBOT ⇄ LUCIUS).

Phase 1 (foundation): the typed mission protocol, the agent registry, the messaging
humanization guardrail, and the system kill switches / run-mode. Later phases add the
mission queue, the ATHENA/HIGGBOT/LUCIUS adapters, the specialist agents, the
touchpoint/allocation engines, performance feedback, and the North-Star dashboard.

Nothing here replaces the existing ORELIUS engine — it extends it.
"""
from .mission import MissionPacket, MissionStatus, validate_mission  # noqa: F401
from .agent_registry import agent_registry, AgentSpec  # noqa: F401
from .messaging_policy import (  # noqa: F401
    validate_autonomous_message,
    sanitize_message,
    contains_forbidden_dashes,
    enforce as enforce_message_policy,
    HUMANIZATION_SYSTEM_PROMPT,
)
from .flags import flags, SocialMode, PAUSE_FLAGS  # noqa: F401
