"""
Hot-topic reel pipeline — economic intel -> ATHENA viral reels.

ORELIUS takes the economic intelligence it has already compiled, pulls the THREE
most important verified facts, frames each as the hottest topic for the life-
insurance niche today, and dispatches THREE solo Instagram reels to ATHENA — one
verified fact per reel. Each reel brief tells ATHENA to use the higgbot
(Higgsfield) engine to produce an award-winning, viral video and publish it to the
correct ibluezcluezflow accounts, following the brand content guidelines.

Verified-source discipline holds: every fact comes from the compiled economic
briefing (which is itself cited/official). ORELIUS never invents a figure.
"""
from __future__ import annotations

import json
from typing import Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..utils.logger import logger
from .claude_client import claude_client
from .finance_intel import finance_intel
from . import athena


def _distill_system(n: int) -> str:
    return (
        f"You are ORELIUS's viral content strategist for the life-insurance brand "
        f"ibluezcluezflow. From the economic intelligence provided, pick the {n} MOST "
        f"important, most timely, DISTINCT verified facts, and turn each into the hottest, "
        f"most engaging topic for the life-insurance niche today. For each, design a "
        f"scroll-stopping solo Instagram REEL concept that follows the brand guidelines.\n\n"
        "HARD RULES:\n"
        "1. Use ONLY facts present in the intelligence provided — cite the figure and its "
        "source. Never invent a number, a development, or a source.\n"
        "2. Each reel centers on ONE fact and ONE clear life-insurance / Infinite Banking / "
        "protect-and-grow angle.\n"
        "3. Education, not individualized advice; no promises of returns; plain, bold, "
        "high-trust language.\n\n"
        "BRAND CONTENT GUIDELINES (follow exactly):\n"
        f"{settings.ibluezcluezflow_guidelines}\n\n"
        f"Return ONLY a JSON object: {{\"reels\": [ ... {n} objects ... ]}} where each object "
        "has keys: \"topic\" (the one-line hot topic), \"fact\" (the single verified fact "
        "in plain words), \"source\" (outlet/agency), \"hook\" (the first 1-2 seconds line), "
        "\"angle\" (the life-insurance tie-in), \"reel_concept\" (what the video shows, "
        "shot by shot, scroll-stopping), \"caption\" (caption direction + key points), "
        "\"hashtags\" (3-6, space-separated), \"cta\" (soft call to action). Output JSON only."
    )


class HotTopicReels:
    """Distills the top facts and dispatches solo reels to ATHENA."""

    async def _latest_intel(self, db: AsyncSession) -> str:
        """The economic intelligence ORELIUS has compiled — latest stored brief, else live."""
        try:
            from ..models.report import Report, ReportType
            row = (
                await db.execute(
                    select(Report)
                    .where(Report.report_type == ReportType.BANKING_INTELLIGENCE)
                    .order_by(Report.created_at.desc())
                    .limit(1)
                )
            ).scalars().first()
            if row and row.summary and len(row.summary.strip()) > 120:
                return row.summary
        except Exception as e:  # noqa: BLE001
            logger.debug(f"hot-topic latest intel read failed: {e}")
        # Fall back to a fresh live briefing (cited, current).
        try:
            return await finance_intel.live_briefing()
        except Exception as e:  # noqa: BLE001
            logger.warning(f"hot-topic live intel failed: {e}")
            return ""

    async def _distill(self, intel: str, n: int) -> List[Dict]:
        prompt = (
            "Here is today's compiled economic intelligence. Extract the top facts and "
            "design the reels per your rules:\n\n" + intel
        )
        try:
            raw = await claude_client.chat(
                messages=[{"role": "user", "content": prompt}],
                system_prompt=_distill_system(n),
                stream=False,
                max_tokens=settings.oreilus_report_max_tokens,
            )
        except Exception as e:  # noqa: BLE001
            logger.error(f"hot-topic distill failed: {e}")
            return []
        obj = self._parse_json(raw)
        reels = (obj or {}).get("reels") if isinstance(obj, dict) else None
        if isinstance(reels, list) and reels:
            return [r for r in reels if isinstance(r, dict)][:n]
        return []

    def _reel_brief(self, concept: Dict, idx: int, total: int) -> str:
        accounts = settings.ibluezcluezflow_accounts
        return (
            f"Create and PUBLISH an award-winning, VIRAL Instagram REEL (solo reel "
            f"{idx} of {total}) for {accounts}, following the brand content guidelines "
            f"below. Use the higgbot (Higgsfield) engine to generate the reel video to an "
            f"award-winning, scroll-stopping, viral standard. This reel centers on ONE "
            f"verified fact — do not combine it with the other reels.\n\n"
            f"HOT TOPIC: {concept.get('topic','')}\n"
            f"THE FACT (verified): {concept.get('fact','')} "
            f"(source: {concept.get('source','')})\n"
            f"HOOK (first 1-2s): {concept.get('hook','')}\n"
            f"ANGLE (life-insurance tie-in): {concept.get('angle','')}\n"
            f"REEL VISUAL CONCEPT: {concept.get('reel_concept','')}\n"
            f"CAPTION DIRECTION: {concept.get('caption','')}\n"
            f"HASHTAGS: {concept.get('hashtags','')}\n"
            f"CTA: {concept.get('cta','')}\n\n"
            f"BRAND CONTENT GUIDELINES (follow exactly):\n{settings.ibluezcluezflow_guidelines}\n\n"
            f"Publish to the correct {accounts}."
        )

    async def build_and_dispatch(self, db: AsyncSession) -> Dict:
        """Distill the top facts and dispatch one solo reel per fact to ATHENA."""
        if not getattr(settings, "athena_enabled", True):
            return {"ok": False, "reason": "athena_disabled"}

        n = max(1, int(getattr(settings, "hot_topic_reels", 3)))
        intel = await self._latest_intel(db)
        if not intel:
            return {"ok": False, "reason": "no_intel"}

        concepts = await self._distill(intel, n)
        if not concepts:
            return {"ok": False, "reason": "distill_failed"}

        dispatched: List[Dict] = []
        for i, concept in enumerate(concepts, 1):
            brief = self._reel_brief(concept, i, len(concepts))
            await athena.enqueue_design_request(
                db, request=brief, kind="instagram_post", action="once"
            )
            dispatched.append({
                "topic": concept.get("topic", ""),
                "fact": concept.get("fact", ""),
                "source": concept.get("source", ""),
            })
        logger.info(f"Hot-topic: dispatched {len(dispatched)} reels to ATHENA")
        return {"ok": True, "reels": dispatched}

    @staticmethod
    def _parse_json(raw: str) -> Optional[Dict]:
        if not raw:
            return None
        text = raw.strip()
        if text.startswith("```"):
            text = text.strip("`")
            if text[:4].lower() == "json":
                text = text[4:]
        start, end = text.find("{"), text.rfind("}")
        if start == -1 or end == -1 or end <= start:
            return None
        try:
            obj = json.loads(text[start:end + 1])
            return obj if isinstance(obj, dict) else None
        except Exception:  # noqa: BLE001
            return None


hot_topic_reels = HotTopicReels()
