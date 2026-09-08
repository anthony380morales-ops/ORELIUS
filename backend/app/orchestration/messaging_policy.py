"""
Autonomous messaging humanization + compliance guardrail.

Every autonomous message the ecosystem sends (Instagram, Facebook, Manychat, SMS,
comments, replies, follow-ups, nurture) must read like a real person in a real
conversation — not a CRM sequence.

ABSOLUTE OUTPUT RULE: an autonomous message must NEVER contain the character
sequence "--" (ASCII double-hyphen). If a generated message contains it, it is
regenerated; as a final backstop `sanitize_message` strips it so it can never ship.
(The single em-dash "—" is a different character and is allowed.)

North-star messaging metric:
    Meaningful Conversation Rate = meaningful two-way conversations / touchpoints

This module is pure/testable: no network, no model calls. The generator prompt is
here so the whole policy lives in one versioned place (directive §62).
"""
from __future__ import annotations

import re
from typing import List, Tuple

POLICY_VERSION = "messaging-humanization-1.0"

# The hard rule.
FORBIDDEN_SEQUENCE = "--"

# Canned sales phrases to avoid unless they genuinely fit (directive: messaging §7).
BANNED_PHRASES = [
    "i'd love to hop on a call",
    "i wanted to reach out",
    "just checking in",
    "i'd love to connect",
    "let me know if you're interested",
    "would you be interested in learning more",
    "i hope this message finds you well",
    "as per my last message",
    "circle back",
    "touch base",
]

# Manufactured-urgency / pressure signals (directive: messaging §14).
URGENCY_SIGNALS = [
    "act now", "limited time", "don't miss out", "last chance", "hurry",
    "only today", "expires soon", "spots are filling", "before it's too late",
]


HUMANIZATION_SYSTEM_PROMPT = """You are writing a single message inside a real, ongoing conversation on social media. Write it the way a thoughtful real person would actually type it — not a marketer, not a CRM, not a bot.

HARD RULES (non-negotiable):
- NEVER use the character sequence "--" anywhere in the message.
- Never invent a past interaction, shared history, or personal familiarity you don't have.
- Never use manufactured urgency, scarcity, countdowns, fear, or pressure.
- Never make guarantees, promise returns, or give individualized regulated financial/insurance advice. Educate and route; a licensed human handles regulated specifics.
- Never disguise the nature of a solicitation where disclosure is required.

VOICE:
- Sound human and natural. Use contractions. Vary sentence length. Short is fine.
- Match the energy and register of the person you're replying to.
- Don't sound polished, corporate, scripted, or sales-heavy.
- Don't reintroduce the brand/offer when they already know the context.

CONVERSATION:
- Respond to what the person ACTUALLY said. Acknowledge it before moving forward.
- Keep the conversation alive: prefer a short reply that invites a natural response.
- Ask at most ONE primary question, and only if the answer would genuinely help you
  understand, personalize, classify, or route. If it wouldn't, don't ask.
- Don't interrogate. Alternate between acknowledging, adding something useful, and asking.
- Don't dump links, explanations, or CTAs early. Build progressively.
- Use curiosity over qualification. Prefer "what got you thinking about X?" over
  "are you interested in X?".
- If their message is vague, ask a light natural follow-up instead of forcing a label.
- If they change topics, follow the shift naturally, then ease back later.

Avoid canned lines like "just checking in", "I wanted to reach out", "let me know if
you're interested", "I'd love to connect/hop on a call" unless they truly fit.

Before you finalize, silently check: does this sound like a real person would send it
in THIS exact conversation? Is it short enough? Is it not a script? Does it give an
easy, natural reason to reply? Does it contain "--"? If it contains "--", rewrite it.

Output only the message text."""


def contains_forbidden_dashes(text: str) -> bool:
    """True if the message contains the banned "--" sequence."""
    return FORBIDDEN_SEQUENCE in (text or "")


def sanitize_message(text: str) -> str:
    """Final backstop: guarantee no "--" ever ships.

    Collapses runs of hyphens (--, ---, ...) into a comma+space when they sit
    between words, or a single space otherwise. Regeneration is preferred; this is
    the last line of defense so the hard rule holds even if a generator slips.
    """
    if not text:
        return text
    # "word--word" -> "word, word"; other hyphen runs -> single space.
    out = re.sub(r"(\w)\s*-{2,}\s*(\w)", r"\1, \2", text)
    out = re.sub(r"-{2,}", " ", out)
    return re.sub(r"[ \t]{2,}", " ", out).strip()


def _too_many_questions(text: str) -> bool:
    return (text or "").count("?") >= 3


def _has_banned_phrase(text: str) -> List[str]:
    low = (text or "").lower()
    return [p for p in BANNED_PHRASES if p in low]


def _has_urgency(text: str) -> List[str]:
    low = (text or "").lower()
    return [p for p in URGENCY_SIGNALS if p in low]


def validate_autonomous_message(text: str, max_chars: int = 600) -> dict:
    """Run the conversation-continuation checks. Returns a structured verdict.

    needs_regen is True when the message should be regenerated (the "--" rule, or a
    stacked set of soft issues). `ok` is True only when nothing tripped.
    """
    issues: List[str] = []
    if contains_forbidden_dashes(text):
        issues.append("contains_double_dash")           # hard rule → always regen
    banned = _has_banned_phrase(text)
    if banned:
        issues.append("canned_sales_phrase:" + ",".join(banned))
    urgency = _has_urgency(text)
    if urgency:
        issues.append("manufactured_urgency:" + ",".join(urgency))
    if _too_many_questions(text):
        issues.append("too_many_questions")
    if text and len(text) > max_chars:
        issues.append("too_long")

    hard = "contains_double_dash" in issues or any(i.startswith("manufactured_urgency") for i in issues)
    needs_regen = hard or len(issues) >= 2
    return {
        "ok": len(issues) == 0,
        "needs_regen": needs_regen,
        "issues": issues,
        "policy_version": POLICY_VERSION,
    }


def enforce(text: str) -> Tuple[str, dict]:
    """Validate, and if the hard "--" rule tripped, sanitize as a backstop.

    Returns (safe_text, verdict). safe_text NEVER contains "--". Callers should still
    prefer regeneration when verdict['needs_regen'] is True, but this guarantees the
    absolute rule holds no matter what.
    """
    verdict = validate_autonomous_message(text)
    safe = sanitize_message(text) if contains_forbidden_dashes(text) else text
    return safe, verdict
