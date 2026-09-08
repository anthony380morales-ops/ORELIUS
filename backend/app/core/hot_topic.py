"""
Hot-topic reel pipeline — a two-step, Master-driven flow.

STEP 1 (compile): from the financial-intelligence briefing ORELIUS already
compiled, he pulls the 3 best & hottest VERIFIED facts, compresses each into plain
language for the hottest life-insurance-niche angle, then constructs a post caption
with viral hashtags and a reel idea. He SHOWS the package to the Master and holds it.

STEP 2 (dispatch): on the Master's word, ORELIUS hands that package to ATHENA, who
gives the details to higgbot — the Master's OWN custom design agent (not Higgsfield)
— to generate an award-winning reel for the ibluezcluezflow pages and publish per
the ibluezcluezflow content roadmap ATHENA holds in her files.

Verified-source discipline holds: every fact comes from the cited economic briefing;
ORELIUS never invents a figure.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..utils.logger import logger
from .claude_client import claude_client
from .finance_intel import finance_intel
from ..models.automation_state import AutomationState  # noqa: F401 (register table)
from . import athena

_STATE_KEY = "hot_topic_package"


def _compile_system(n: int) -> str:
    return (
        f"You are ORELIUS's viral content strategist for the life-insurance brand "
        f"ibluezcluezflow. From the compiled economic intelligence provided, pick the "
        f"{n} BEST and HOTTEST distinct VERIFIED facts, and compress each into ONE "
        f"plain-language line framed for the hottest life-insurance-niche angle. Then "
        f"construct a single scroll-stopping post CAPTION, a set of VIRAL HASHTAGS, and "
        f"one strong REEL/POST IDEA that ties the facts together.\n\n"
        "HARD RULES:\n"
        "1. Use ONLY facts present in the intelligence provided — never invent a number, "
        "a development, or a source. Keep each fact plain and punchy.\n"
        "2. Education, not individualized advice; no promises of returns.\n"
        "3. Tie everything to a life-insurance / Infinite Banking / protect-and-grow "
        "angle, in the brand voice.\n\n"
        "BRAND VOICE (guide the caption + hashtags):\n"
        f"{settings.ibluezcluezflow_guidelines}\n\n"
        f"Return ONLY a single-line JSON object with ALL FOUR keys present and non-empty: "
        f"{{\"facts\": [ {n} plain-language strings ], \"caption\": \"the full post "
        "caption\", \"hashtags\": \"6-10 space-separated viral hashtags, each starting "
        "with #\", \"post_idea\": \"the reel/post concept in 1-3 sentences\"}}. The "
        "hashtags MUST be their own field — never fold them into the caption. Do NOT wrap "
        "the JSON in markdown or code fences, and do NOT add any text before or after. "
        "Inside string values use \\n for any line breaks — never a raw line break. "
        "Output the JSON object only."
    )


class HotTopicReels:
    """Compiles the post package, then (on command) dispatches it to ATHENA/higgbot."""

    # ------------------------------------------------------- compiled-package store
    async def _load_package(self, db: AsyncSession) -> Dict:
        try:
            row = (await db.execute(
                select(AutomationState).where(AutomationState.key == _STATE_KEY)
            )).scalars().first()
            if row and isinstance(row.data, dict):
                return dict(row.data)
        except Exception as e:  # noqa: BLE001
            logger.debug(f"hot-topic load package failed: {e}")
        return {}

    async def _save_package(self, db: AsyncSession, package: Dict) -> None:
        try:
            row = (await db.execute(
                select(AutomationState).where(AutomationState.key == _STATE_KEY)
            )).scalars().first()
            if row:
                row.data = package
            else:
                db.add(AutomationState(key=_STATE_KEY, data=package))
            await db.flush()
        except Exception as e:  # noqa: BLE001
            logger.debug(f"hot-topic save package failed: {e}")

    @staticmethod
    def _is_empty_brief(text: str) -> bool:
        """True for the finance engine's 'no new data' message — no facts to compile."""
        low = (text or "").lower()
        return ("no newly-released" in low or "nothing to repeat" in low
                or "could not retrieve live economic news" in low
                or "no new verified" in low)

    async def _latest_intel(self, db: AsyncSession) -> str:
        """The economic intelligence to build reels from.

        PREFER the LIVE, web-searched, cited briefing (the same rich source the chat
        economic-news answer uses) — the stored automation report is the de-duped
        numeric feed and is frequently a 'no new data' message with nothing to
        compile. Fall back to a stored brief only if it has real content.
        """
        live = ""
        try:
            live = await finance_intel.live_briefing()
        except Exception as e:  # noqa: BLE001
            logger.warning(f"hot-topic live intel failed: {e}")
        if live and len(live.strip()) > 200 and not self._is_empty_brief(live):
            return live

        try:
            from ..models.report import Report, ReportType
            row = (await db.execute(
                select(Report)
                .where(Report.report_type == ReportType.BANKING_INTELLIGENCE)
                .order_by(Report.created_at.desc())
                .limit(1)
            )).scalars().first()
            s = (row.summary or "").strip() if row else ""
            if s and len(s) > 200 and not self._is_empty_brief(s):
                return s
        except Exception as e:  # noqa: BLE001
            logger.debug(f"hot-topic stored intel read failed: {e}")

        return live  # may be empty / an 'empty brief' — caller handles gracefully

    # ------------------------------------------------------------- STEP 1: compile
    async def compile_package(self, db: AsyncSession) -> Dict:
        """Compile the 3 hottest facts + caption + hashtags + reel idea, and hold it."""
        n = max(1, int(getattr(settings, "hot_topic_facts", 3)))
        intel = await self._latest_intel(db)
        if not intel:
            return {"ok": False, "reason": "no_intel"}

        prompt = ("Here is today's compiled economic intelligence. Compile the package per "
                  "your rules:\n\n" + intel)

        obj: Optional[Dict] = None
        raw = ""
        for attempt in range(2):  # one retry — JSON reliability
            try:
                raw = await claude_client.chat(
                    messages=[{"role": "user", "content": prompt}],
                    system_prompt=_compile_system(n),
                    stream=False,
                    max_tokens=settings.oreilus_report_max_tokens,
                    temperature=0.3,  # low temp → clean, structured JSON
                )
            except Exception as e:  # noqa: BLE001
                logger.error(f"hot-topic compile call failed (attempt {attempt + 1}): {e}")
                continue
            obj = self._parse_json(raw)
            if isinstance(obj, dict) and isinstance(obj.get("facts"), list) and obj["facts"]:
                break
            obj = None

        if obj is None:
            logger.warning(f"hot-topic compile: unparseable model output: {raw[:300]!r}")
            return {"ok": False, "reason": "compile_failed"}

        package = {
            "facts": [str(f).strip() for f in obj.get("facts") or [] if str(f).strip()][:n],
            "caption": str(obj.get("caption", "")).strip(),
            "hashtags": str(obj.get("hashtags", "")).strip(),
            "post_idea": str(obj.get("post_idea", "")).strip(),
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        if not package["facts"]:
            return {"ok": False, "reason": "compile_failed"}
        await self._save_package(db, package)
        return {"ok": True, "package": package}

    # ------------------------------------------------------------ STEP 2: dispatch
    async def dispatch(self, db: AsyncSession) -> Dict:
        """Hand the held package to ATHENA -> higgbot for reel generation + publish."""
        if not getattr(settings, "athena_enabled", True):
            return {"ok": False, "reason": "athena_disabled"}

        stored = await self._load_package(db)
        package = stored if stored.get("facts") else None
        if package is None:
            # Nothing compiled yet — compile on the fly so the dispatch still works.
            res = await self.compile_package(db)
            if not res.get("ok"):
                return {"ok": False, "reason": res.get("reason", "no_package")}
            package = res["package"]

        solo = bool(getattr(settings, "hot_topic_solo_reels", False))
        if solo:
            count = 0
            for i, fact in enumerate(package.get("facts") or [], 1):
                await athena.enqueue_design_request(
                    db, request=self._reel_brief(package, solo_fact=fact,
                                                 idx=i, total=len(package["facts"])),
                    kind="instagram_post", action="once",
                )
                count += 1
            dispatched = count
        else:
            await athena.enqueue_design_request(
                db, request=self._reel_brief(package), kind="instagram_post", action="once",
            )
            dispatched = 1

        logger.info(f"Hot-topic: dispatched {dispatched} reel job(s) to ATHENA/higgbot")
        return {"ok": True, "package": package, "dispatched": dispatched}

    def _reel_brief(self, package: Dict, solo_fact: Optional[str] = None,
                    idx: int = 1, total: int = 1) -> str:
        higg = getattr(settings, "higgbot_name", "higgbot")
        accounts = settings.ibluezcluezflow_accounts
        facts = package.get("facts") or []
        if solo_fact is not None:
            facts_block = f"THE FACT (verified, plain language): {solo_fact}"
            header = (f"Solo reel {idx} of {total} — this reel centers on ONE fact.")
        else:
            facts_block = "KEY FACTS (verified, plain language):\n" + "\n".join(
                f"{i}. {f}" for i, f in enumerate(facts, 1)
            )
            header = "This reel carries the compiled package (all facts + caption)."
        return (
            f"Hand these details to {higg} — the Master's OWN custom design agent (NOT "
            f"Higgsfield) — to generate an AWARD-WINNING Instagram REEL for {accounts}. "
            f"{header} Execute publishing per the ibluezcluezflow CONTENT ROADMAP you hold "
            f"in your files (format, style, and account routing come from that roadmap).\n\n"
            f"POST CAPTION:\n{package.get('caption','')}\n\n"
            f"VIRAL HASHTAGS:\n{package.get('hashtags','')}\n\n"
            f"REEL / POST IDEA:\n{package.get('post_idea','')}\n\n"
            f"{facts_block}\n\n"
            f"Follow the ibluezcluezflow content roadmap in your files for everything else."
        )

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
        region = text[start:end + 1]
        try:
            obj = json.loads(region)
            return obj if isinstance(obj, dict) else None
        except Exception:  # noqa: BLE001
            pass
        # Tolerant retry: the model often puts RAW line breaks inside string values
        # (multi-line captions), which is invalid JSON. Collapse control chars to
        # spaces — structural whitespace stays valid, in-string breaks become spaces.
        try:
            cleaned = region.replace("\r", " ").replace("\t", " ").replace("\n", " ")
            obj = json.loads(cleaned)
            return obj if isinstance(obj, dict) else None
        except Exception:  # noqa: BLE001
            return None


hot_topic_reels = HotTopicReels()
