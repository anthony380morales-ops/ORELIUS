"""
O.R.E.L.I.U.S. -> ATHENA bridge (brain side).

ATHENA is Anthony's autonomous design + content agent. It runs 24/7 on his own
machine and only listens on localhost, so the cloud-hosted ORELIUS cannot call it
directly. ORELIUS *delegates* by writing a `design_request` event into shared
memory; a small bridge daemon on Anthony's machine drives ATHENA's local HTTP API
and writes a `design_result` back.

ATHENA exposes three job surfaces (all polled at /jobs/:id):
  * design         -> POST /design {prompt, ...}  (logos, posters, graphics, social
                      art, product/lifestyle shots, etc. -> saved to output/design)
  * instagram_post -> POST /jobs   {action}       (research + create + publish/
                      schedule a real Instagram post; gated on quality)
  * website        -> POST /site   {prompt}       (build a landing page / site)

Everything here is credit-cheap: the tool call is resolved in a single model turn
and the request is just one small DB row.
"""
from __future__ import annotations

from typing import Dict, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..utils.logger import logger
from .shared_memory import shared_memory


# What kind of ATHENA work a request maps to (decides which endpoint the bridge hits).
ATHENA_KINDS = ["design", "instagram_post", "website"]

# Instagram pipeline actions (POST /jobs) — only relevant for kind=instagram_post.
ATHENA_ACTIONS = ["once", "autopilot", "batch", "research", "brief"]

# Design-engine task types (POST /design) — optional hint for kind=design.
ATHENA_DESIGN_TASKS = [
    "concept", "poster", "typography", "logo", "vector", "product", "lifestyle",
    "edit", "brand_style", "social", "motion", "story", "commercial", "cinematic", "ugc",
]


# Anthropic tool schema handed to the Haiku brain.
ATHENA_TOOL: Dict = {
    "name": "athena_design",
    "description": (
        "Delegate design, content, and creative production to ATHENA, the Master's "
        "autonomous design agent running on his machine. Use this for ANYTHING design "
        "or content related. ATHENA can: (1) generate design assets — logos, posters, "
        "typography, graphics, social images, product/lifestyle/brand art (saved as "
        "image files the Master can open); (2) create AND publish/schedule a real "
        "Instagram post for his brand; (3) build a website / landing page. Calling this "
        "dispatches the job to ATHENA and she reports the result (file paths, score, or "
        "'scheduled') back through your shared memory. Pick the correct `kind`. Do NOT "
        "use this for plain questions you can answer yourself."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "request": {
                "type": "string",
                "description": (
                    "A clear, self-contained description of what to make — the design "
                    "prompt, post idea, or site brief, with style/goal/audience and any "
                    "specifics the Master gave. Write it as an instruction ATHENA can act "
                    "on alone. For a design, be visual and concrete."
                ),
            },
            "kind": {
                "type": "string",
                "enum": ATHENA_KINDS,
                "description": (
                    "Which ATHENA capability to use:\n"
                    "- 'design': generate a design/graphic asset (logo, poster, social "
                    "image, product shot, etc.). Saved as files the Master can view. USE "
                    "THIS for 'make/design/create a <visual>'.\n"
                    "- 'instagram_post': research, create, AND publish/schedule a real "
                    "Instagram post for the brand. USE THIS for 'post', 'publish today's "
                    "post', 'put something on Instagram'.\n"
                    "- 'website': build a website or landing page."
                ),
            },
            "task": {
                "type": "string",
                "enum": ATHENA_DESIGN_TASKS,
                "description": (
                    "Only for kind='design': the design task type that best fits "
                    "(e.g. 'logo', 'poster', 'social', 'product'). Omit if unsure."
                ),
            },
            "action": {
                "type": "string",
                "enum": ATHENA_ACTIONS,
                "description": (
                    "Only for kind='instagram_post': 'once' (create+publish one post now "
                    "— the default), 'autopilot' (full daily pipeline, one post/day), "
                    "'batch' (several days), 'research' (trends only, no post), 'brief' "
                    "(email a plan only, no post)."
                ),
            },
            "days": {
                "type": "integer",
                "description": "Only for action='batch': how many days of posts. Omit otherwise.",
            },
        },
        "required": ["request", "kind"],
    },
}


def _normalize_kind(kind: Optional[str]) -> str:
    kind = (kind or "design").strip().lower()
    return kind if kind in ATHENA_KINDS else "design"


def _normalize_action(action: Optional[str]) -> str:
    action = (action or settings.athena_default_action or "once").strip().lower()
    return action if action in ATHENA_ACTIONS else "once"


async def enqueue_design_request(
    db: AsyncSession,
    request: str,
    kind: Optional[str] = None,
    task: Optional[str] = None,
    action: Optional[str] = None,
    days: Optional[int] = None,
) -> Dict:
    """Record a `design_request` in shared memory for the ATHENA bridge to pick up.

    The bridge reads `meta.kind` to choose the endpoint:
      design -> POST /design {prompt},  instagram_post -> POST /jobs {action},
      website -> POST /site {prompt}.
    Returns the stored event dict (with its id), or {} if persistence failed — a
    dispatch must never crash the chat reply.
    """
    kind = _normalize_kind(kind)
    request = (request or "").strip()
    meta: Dict = {"kind": kind, "status": "queued"}

    if kind == "instagram_post":
        meta["action"] = _normalize_action(action)
        if days is not None:
            try:
                meta["days"] = int(days)
            except (TypeError, ValueError):
                pass
    elif kind == "design" and task:
        t = str(task).strip().lower()
        if t in ATHENA_DESIGN_TASKS:
            meta["task"] = t

    try:
        event = await shared_memory.remember(
            db,
            content=request[:4000] or f"ATHENA {kind} request",
            kind="design_request",
            actor="ORELIUS",
            meta=meta,
        )
        logger.info(f"Queued ATHENA design_request #{event.get('id')} (kind={kind}, meta={meta})")
        return event
    except Exception as e:  # noqa: BLE001 - dispatch must never break a reply
        logger.error(f"Failed to queue ATHENA design_request: {e}")
        return {}


def confirmation_text(request: str, kind: str, preface: str = "") -> str:
    """ORELIUS's spoken confirmation that the job was handed to ATHENA."""
    kind = _normalize_kind(kind)
    short = (request or "").strip()
    if len(short) > 200:
        short = short[:200].rstrip() + "…"

    if kind == "instagram_post":
        line = (
            f"Understood, Master. I've dispatched this to ATHENA — she'll create and "
            f"publish an Instagram post for “{short}” and report back through our shared "
            f"memory. I'll surface her result (and whether it cleared her quality gate) "
            f"here as soon as it lands."
        )
    elif kind == "website":
        line = (
            f"Understood, Master. I've handed this to ATHENA to build “{short}”. She'll "
            f"report the result through our shared memory and I'll bring it to you."
        )
    else:  # design
        line = (
            f"Understood, Master. I've dispatched this to ATHENA's design engine — she'll "
            f"produce “{short}” and save it to her design output folder. I'll surface the "
            f"result and file paths here through our shared memory as soon as she's done."
        )

    preface = (preface or "").strip()
    return f"{preface}\n\n{line}".strip() if preface else line
