"""
BLUEPRINTS — weekly cinematic video episode compiler (the "prompt", injected).

This is the brain side of the BLUEPRINTS video engine: it writes ONE 60-second
(aim 50s) cinematic episode a week for BOTH pages, in the old-money / wealth-noir
world, under the same novelty rule as the feed (never repeat a prior week's hook,
number, or angle). ATHENA renders it with fal.ai (lip-synced talking shots of the
Master + cinematic b-roll) and falls back to the still layer until fal is funded.

Nothing here touches the daily posting path; it is called only for the weekly video.
"""
from __future__ import annotations

import json
from typing import Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..core.claude_client import claude_client
from ..utils.logger import logger

# The injected world + format. ORIGINAL (not copied from any reference account).
BLUEPRINTS_WORLD = (
    "SERIES: BLUEPRINTS — a weekly cinematic short for NXG Life Group (life insurance, "
    "Infinite Banking, economic intelligence) posted to both pages.\n"
    "WORLD: old-money / wealth-noir. Calm, refined, quietly powerful; the opposite of hype. "
    "The villain is THE SYSTEM (banks, inflation, Wall Street) that keeps the middle class "
    "renting money. The hero is the Master, old-money styled, who teaches people to OWN the "
    "thing everyone else borrows from. Palette: near-black + vault gold, danger red for the "
    "threat only. Wardrobe: OLD MONEY, a fresh tailored look each week (no logos, no flash).\n"
    "VOICE: educational, intriguing, deadpan-confident, legacy-minded. Licensed CA agent: "
    "educational only, never guarantees/returns language, never invent a figure.\n"
    "ORIGINALITY: never reuse the same hook, number, sign-off, or angle as a recent episode."
)

# 5-beat 60s engine (same shape ATHENA's assembler expects).
_EPISODE_SCHEMA = (
    '{"title":"episode title (<=5 words)",'
    '"wardrobe":"this week\'s old-money outfit, one line (for the wardrobe still)",'
    '"beats":[{"t0":0,"t1":5,"text":"ONE-TO-THREE WORD TITLE CARD, ALL CAPS",'
    '"color":"gold|white|red","vo":"the spoken line for this beat, <18 words"} '
    '(exactly 5 beats: Threat 0-5, Trap 5-15, Method 15-40, Proof 40-52, Legacy 52-60)],'
    '"shotPrompts":["4-7 cinematic b-roll prompts for image->video: vault, ledger, cash, '
    'skyline, fountain pen, etc., dark + gold, 9:16"],'
    '"signoff":"original closing line (NOT a copied catchphrase)",'
    '"cta":"one-word DM CTA line, e.g. Comment BLUEPRINT",'
    '"caption":"the post caption for both pages (NXG legacy angle; IBC uses the same video)"}'
)


def blueprints_episode_system(avoid: Optional[List[str]] = None) -> str:
    avoid_block = ""
    if avoid:
        avoid_block = (
            "\n\nNOVELTY — these hooks/numbers/angles ran recently; do NOT repeat them, pick a "
            "fresh economic topic and a new proof number:\n" + "\n".join(f"- {a}" for a in avoid[:20])
        )
    return (
        BLUEPRINTS_WORLD + "\n\n"
        "Write THIS WEEK'S episode from the compiled economic intelligence. Teach ONE idea "
        "(an IBC / IUL / cash-value / economic concept) with ONE concrete verified number as "
        "the proof. Lead with a non-obvious thesis, not a data dump. Keep each VO line short "
        "and spoken-natural; the on-screen title cards are 1-3 words. Never use a double hyphen "
        "or any long dash." + avoid_block + "\n\n"
        "Return ONLY a single-line JSON object, no markdown, no code fences, with this shape:\n"
        + _EPISODE_SCHEMA
    )


async def compile_blueprints_episode(db: AsyncSession, intel: str,
                                     avoid: Optional[List[str]] = None) -> Optional[Dict]:
    """Compile one weekly BLUEPRINTS episode spec (beats + VO + shot prompts + wardrobe).
    Returns the parsed dict, or None on failure (ATHENA then uses a safe default)."""
    try:
        raw = await claude_client.chat(
            messages=[{"role": "user", "content":
                       "Today's compiled economic intelligence:\n\n" + (intel or "")}],
            system_prompt=blueprints_episode_system(avoid),
            stream=False,
            max_tokens=getattr(settings, "oreilus_report_max_tokens", 2000),
            temperature=0.6,
        )
        s = (raw or "").strip()
        a, b = s.find("{"), s.rfind("}")
        if a == -1 or b <= a:
            return None
        obj = json.loads(s[a:b + 1])
        if isinstance(obj, dict) and isinstance(obj.get("beats"), list) and obj["beats"]:
            return obj
    except Exception as e:  # noqa: BLE001
        logger.warning(f"blueprints episode compile failed: {e}")
    return None
