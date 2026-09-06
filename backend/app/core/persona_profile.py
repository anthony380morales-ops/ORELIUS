"""
Persona Profile Manager — ORELIUS's living read on the Master's personality.

This powers the "normal AI chatbot" side of ORELIUS: over ordinary conversation
he quietly learns how the Master communicates (style, tone, interests, likes,
dislikes, stable facts) and tailors replies to flow with that personality — the
way Claude or ChatGPT feel natural once they know you.

Two operations:
  • render_context(db)  -> a compact "who you're talking to" block injected into
                           the CHAT system prompt so every reply is on-personality.
  • observe(...)        -> called after each exchange; increments a counter and,
                           only every few exchanges (credit discipline), runs one
                           cheap reflection pass to refresh the stored profile.

ISOLATION (non-negotiable): none of this touches the daily Financial Intelligence
automation. finance_intel.py builds its own strict system prompt and pipeline and
never imports this module. Personality shapes conversation only — never how
finance data is gathered, filtered by the 2-month barrier, de-duplicated, or
synthesized. The two systems share nothing but the database engine.
"""
from __future__ import annotations

import json
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .claude_client import claude_client
from ..config import settings
from ..models.persona_profile import PersonaProfile
from ..utils.logger import logger


# The reflection runs on its own analyst prompt — deliberately NOT the ORELIUS
# persona — so it reasons about the Master coolly and returns clean JSON.
_REFLECTION_SYSTEM = """You are a profiler. From the recent conversation and the existing profile, produce an UPDATED read of the human's personality so an assistant can mirror how they like to communicate.

Return ONLY a compact JSON object (no prose, no markdown) with these keys:
- "summary": 1-2 sentences on who they are and how they like to be spoken to.
- "communication_style": short phrase (e.g. "direct, casual, wants brevity").
- "tone": short phrase (e.g. "warm, dry humor, no hand-holding").
- "interests": array of up to 6 short topics they care about.
- "values": array of up to 5 short things they prioritize.
- "likes": array of up to 5 short things that land well with them.
- "dislikes": array of up to 5 short things to avoid (jargon, hedging, etc.).
- "notable_facts": array of up to 8 short, STABLE facts about them (role, ventures, family, goals). Only durable facts, never one-off task details.

Rules:
- Merge new observations into the existing profile; keep what still holds, drop what's contradicted.
- Only include well-supported traits. If unsure, leave a field as its previous value or "".
- Keep every string short. Never invent facts. Output JSON only."""


class PersonaProfileManager:
    """Learns and serves the Master's conversational personality profile."""

    def __init__(self):
        self.enabled = getattr(settings, "persona_learning_enabled", True)
        self.update_every = getattr(settings, "persona_update_every", 6)
        self.reflect_max_tokens = getattr(settings, "persona_reflect_max_tokens", 700)
        self.context_char_cap = getattr(settings, "persona_context_char_cap", 1400)

    # ---- storage -----------------------------------------------------------
    async def _get_row(self, db: AsyncSession) -> Optional[PersonaProfile]:
        res = await db.execute(select(PersonaProfile).where(PersonaProfile.id == 1))
        return res.scalar_one_or_none()

    async def load(self, db: AsyncSession) -> dict:
        """Return the current profile dict (empty dict if none learned yet)."""
        try:
            row = await self._get_row(db)
            if row and isinstance(row.profile, dict):
                return row.profile
        except Exception as e:  # noqa: BLE001 - never break a reply over this
            logger.debug(f"persona load skipped: {e}")
        return {}

    # ---- inject into the chat system prompt --------------------------------
    async def render_context(self, db: AsyncSession) -> str:
        """A compact 'who you're talking to' block for the CHAT system prompt.

        Empty string until enough has been learned, so early conversations are
        unaffected. Never included in the finance automation's prompt.
        """
        if not self.enabled:
            return ""
        profile = await self.load(db)
        if not profile:
            return ""

        def _line(label: str, key: str) -> str:
            val = profile.get(key)
            if isinstance(val, list):
                val = ", ".join(str(v) for v in val if v)
            val = (str(val) if val else "").strip()
            return f"- {label}: {val}\n" if val else ""

        block = "\n\n# WHO YOU'RE TALKING TO (learned from your conversations)\n"
        summary = (profile.get("summary") or "").strip()
        if summary:
            block += summary + "\n"
        block += _line("Communication style", "communication_style")
        block += _line("Tone that lands", "tone")
        block += _line("Interests", "interests")
        block += _line("Values", "values")
        block += _line("Responds well to", "likes")
        block += _line("Avoid", "dislikes")
        facts = profile.get("notable_facts")
        if isinstance(facts, list) and facts:
            block += "- Things you know about him: " + "; ".join(str(f) for f in facts if f) + "\n"
        block += (
            "Mirror this personality naturally so your replies feel tailor-made — match his "
            "rhythm, brevity, and tone. Never announce that you keep this profile; just sound "
            "like someone who knows him. This is for conversation only; it does not change how "
            "you run the daily financial intelligence briefing.\n"
        )
        return block[: self.context_char_cap]

    # ---- learn from an exchange -------------------------------------------
    async def observe(
        self,
        db: AsyncSession,
        history: list[dict],
        user_message: str,
        assistant_reply: str,
    ) -> None:
        """Count this exchange; every Nth one, refresh the profile (cheaply)."""
        if not self.enabled:
            return
        try:
            row = await self._get_row(db)
            if row is None:
                row = PersonaProfile(id=1, profile={}, exchanges_since_update=0, total_exchanges=0)
                db.add(row)
                await db.flush()

            row.exchanges_since_update = (row.exchanges_since_update or 0) + 1
            row.total_exchanges = (row.total_exchanges or 0) + 1

            if row.exchanges_since_update < self.update_every:
                return  # not time to spend credits on a reflection yet

            updated = await self._reflect(row.profile or {}, history, user_message, assistant_reply)
            if updated:
                row.profile = updated
                row.exchanges_since_update = 0
                logger.info("Persona profile refreshed from recent conversation")
        except Exception as e:  # noqa: BLE001 - learning must never break a reply
            logger.debug(f"persona observe skipped: {e}")

    async def _reflect(
        self,
        current: dict,
        history: list[dict],
        user_message: str,
        assistant_reply: str,
    ) -> Optional[dict]:
        """One cheap Haiku call that returns an updated profile JSON."""
        # Keep the signal small: the last few turns are plenty.
        recent = history[-8:] if history else []
        convo_lines = []
        for m in recent:
            role = "Master" if m.get("role") == "user" else "ORELIUS"
            content = str(m.get("content", ""))[:500]
            convo_lines.append(f"{role}: {content}")
        convo = "\n".join(convo_lines)

        prompt = (
            "EXISTING PROFILE (JSON):\n"
            + json.dumps(current, ensure_ascii=False)
            + "\n\nRECENT CONVERSATION:\n"
            + convo
            + "\n\nReturn the updated profile JSON only."
        )
        try:
            raw = await claude_client.chat(
                messages=[{"role": "user", "content": prompt}],
                system_prompt=_REFLECTION_SYSTEM,
                stream=False,
                max_tokens=self.reflect_max_tokens,
            )
        except Exception as e:  # noqa: BLE001
            logger.debug(f"persona reflect call failed: {e}")
            return None
        return self._parse_json(raw)

    @staticmethod
    def _parse_json(raw: str) -> Optional[dict]:
        """Extract a JSON object from the model's reply, tolerant of stray text."""
        if not raw:
            return None
        text = raw.strip()
        # Strip code fences if present.
        if text.startswith("```"):
            text = text.strip("`")
            if text.lower().startswith("json"):
                text = text[4:]
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1 or end <= start:
            return None
        try:
            obj = json.loads(text[start : end + 1])
            return obj if isinstance(obj, dict) else None
        except Exception:  # noqa: BLE001
            return None


# Global instance
persona_profile = PersonaProfileManager()
