"""
O.R.E.L.I.U.S. -> ATHENA design bridge (brain side).

ATHENA is Anthony's autonomous design/content agent. It runs 24/7 on his own
machine and only listens on localhost (127.0.0.1:8787), so the cloud-hosted
ORELIUS cannot call it directly. Instead ORELIUS *delegates*:

    1. When the Master asks for anything design related, the Haiku brain calls
       the `athena_design` tool.
    2. That writes a `design_request` event into the shared_memory table.
    3. A tiny bridge daemon on Anthony's machine (integrations/athena/) polls
       ORELIUS for new `design_request` events, drives ATHENA's local /jobs API,
       and writes a `design_result` event back into shared memory.
    4. ORELIUS surfaces that result on the next turn (shared memory is injected
       into its persona every message).

Everything here is credit-cheap: the tool call is resolved in a single model
turn (no extra round-trip) and the request is just one small DB row.
"""
from __future__ import annotations

from typing import Dict, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..utils.logger import logger
from .shared_memory import shared_memory


# Actions ATHENA understands (mirrors ATHENA's own /jobs API + client contract).
#   once     - run a single content/design cycle now
#   batch    - produce a batch of designs/posts
#   research - research a topic / gather references before designing
#   brief    - draft a creative brief / plan (default, cheapest for ATHENA)
#   autopilot- let ATHENA run its full autonomous pipeline
#   status   - report what ATHENA is currently doing
ATHENA_ACTIONS = ["brief", "once", "batch", "research", "autopilot", "status"]


# Anthropic tool schema handed to the Haiku brain.
ATHENA_TOOL: Dict = {
    "name": "athena_design",
    "description": (
        "Delegate any design, branding, visual, or content-creation work to ATHENA, "
        "the Master's dedicated autonomous design agent. Use this whenever the Master "
        "asks for something design related: creating or restyling visuals, graphics, "
        "posts, branding, layouts, mockups, creative briefs, content research, or "
        "running ATHENA's content pipeline. ATHENA works asynchronously on the "
        "Master's own machine; calling this dispatches the job to her and she reports "
        "back through your shared memory. Do NOT use this for plain questions you can "
        "answer yourself — only for actual design/content production work."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "brief": {
                "type": "string",
                "description": (
                    "A clear, self-contained description of the design/content work for "
                    "ATHENA — what to make, the goal, style, audience, and any specifics "
                    "the Master gave. Write it as an instruction ATHENA can act on alone."
                ),
            },
            "action": {
                "type": "string",
                "enum": ATHENA_ACTIONS,
                "description": (
                    "How ATHENA should handle it: 'brief' (draft a plan/creative brief — "
                    "the safe default), 'once' (produce one design/post now), 'batch' "
                    "(produce several), 'research' (gather references/ideas first), "
                    "'autopilot' (run her full autonomous pipeline), or 'status' (just "
                    "report what she's doing)."
                ),
            },
            "days": {
                "type": "integer",
                "description": (
                    "Optional time window in days when the action needs one (e.g. a batch "
                    "or research spanning a period). Omit if not relevant."
                ),
            },
        },
        "required": ["brief"],
    },
}


def _normalize_action(action: Optional[str]) -> str:
    action = (action or settings.athena_default_action or "brief").strip().lower()
    return action if action in ATHENA_ACTIONS else "brief"


async def enqueue_design_request(
    db: AsyncSession,
    brief: str,
    action: Optional[str] = None,
    days: Optional[int] = None,
) -> Dict:
    """Record a `design_request` in shared memory for the ATHENA bridge to pick up.

    Returns the stored event dict (includes its id), or a best-effort empty dict
    if persistence failed — a design dispatch must never crash the chat reply.
    """
    action = _normalize_action(action)
    brief = (brief or "").strip()
    meta = {"action": action, "status": "queued"}
    if days is not None:
        meta["days"] = int(days)

    try:
        event = await shared_memory.remember(
            db,
            content=brief[:4000] or f"ATHENA {action} request",
            kind="design_request",
            actor="ORELIUS",
            meta=meta,
        )
        logger.info(f"Queued ATHENA design_request #{event.get('id')} (action={action})")
        return event
    except Exception as e:  # noqa: BLE001 - dispatch must never break a reply
        logger.error(f"Failed to queue ATHENA design_request: {e}")
        return {}


def confirmation_text(brief: str, action: str, preface: str = "") -> str:
    """ORELIUS's spoken confirmation that the job was handed to ATHENA."""
    action = _normalize_action(action)
    verb = {
        "brief": "draft a creative brief for",
        "once": "produce",
        "batch": "produce a batch for",
        "research": "research references for",
        "autopilot": "run her full pipeline on",
        "status": "report her current status regarding",
    }.get(action, "work on")
    short = brief.strip()
    if len(short) > 200:
        short = short[:200].rstrip() + "…"
    line = (
        f"Understood, Master. I've dispatched this to ATHENA — she'll {verb} "
        f"“{short}” and report back through our shared memory. "
        f"I'll surface her result here as soon as it lands."
    )
    preface = (preface or "").strip()
    return f"{preface}\n\n{line}".strip() if preface else line
