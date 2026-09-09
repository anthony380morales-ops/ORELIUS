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

# The two accounts ORELIUS builds for. Each is a DISTINCT brand with its own voice,
# format, and destination (directive §22 — brands never share a voice). ATHENA's
# stored roadmap holds the exact publishing routing for each.
def _brand_specs() -> Dict[str, Dict]:
    # The action ATHENA runs to publish ORELIUS-SUPPLIED content (contract).
    publish_action = getattr(settings, "athena_content_action", "publish")
    return {
        "ibc": {
            "name": "ibluezcluezflow",
            "account_id": getattr(settings, "ibluezcluezflow_account_id", "ibluezcluezflow"),
            "brand_id": getattr(settings, "ibluezcluezflow_brand_id", "IBC"),
            "platform": "instagram",
            "guidelines": settings.ibluezcluezflow_guidelines,
            "accounts": getattr(settings, "ibluezcluezflow_accounts",
                                "the ibluezcluezflow Instagram pages"),
            "format": "reel",                 # short-form Instagram reel
            "state_key": "hot_topic_package_ibc",
            # Route through ATHENA's /jobs publish handler; accountId + format tell it
            # WHICH account and WHICH medium. (Falls back to autopilot only if ATHENA
            # doesn't yet support the publish action.)
            "athena_kind": "instagram_post",
            "athena_action": publish_action,
            "solo": bool(getattr(settings, "hot_topic_solo_reels", False)),
            "target": "instagram_reels",
        },
        "nxg": {
            "name": "NXG Life Group",
            "account_id": getattr(settings, "nxg_account_id", "nxg_life_group"),
            "brand_id": getattr(settings, "nxg_brand_id", "NXG"),
            "platform": "facebook",
            "guidelines": getattr(settings, "nxg_facebook_guidelines", ""),
            "accounts": getattr(settings, "nxg_facebook_accounts",
                                "the NXG Life Group Facebook page"),
            "format": "facebook_post",        # a Facebook feed post (not a reel)
            "state_key": "hot_topic_package_nxg",
            "athena_kind": "instagram_post",  # same /jobs publish handler; accountId routes
            "athena_action": publish_action,
            "solo": False,                    # one consolidated Facebook post
            "target": "facebook_page",
        },
    }


def _resolve_brand(brand: Optional[str]) -> str:
    b = (brand or "ibc").strip().lower()
    if b in ("nxg", "facebook", "nxg_life_group", "nxglifegroup"):
        return "nxg"
    return "ibc"


def _compile_system(n: int, brand: str = "ibc") -> str:
    spec = _brand_specs()[_resolve_brand(brand)]
    fmt = spec["format"]
    if fmt == "reel":
        artifact = "one strong REEL IDEA"
        idea_desc = "the reel/post concept in 1-3 sentences"
    else:
        artifact = "one strong FACEBOOK POST IDEA"
        idea_desc = "the Facebook post concept in 1-3 sentences"
    return (
        f"You are ORELIUS's content strategist for the life-insurance brand "
        f"{spec['name']}. From the compiled economic intelligence provided, pick the "
        f"{n} BEST and HOTTEST distinct VERIFIED facts, and compress each into ONE "
        f"plain-language line framed for this brand's audience. Then construct a single "
        f"scroll-stopping post CAPTION, a set of relevant HASHTAGS, and {artifact} that "
        f"ties the facts together — all in THIS brand's voice and format.\n\n"
        "HARD RULES:\n"
        "1. Use ONLY facts present in the intelligence provided — never invent a number, "
        "a development, or a source. Keep each fact plain and punchy.\n"
        "2. Education, not individualized advice; no promises of returns.\n"
        "3. Tie everything to protecting and growing with life insurance, in the brand "
        "voice and the brand's format below.\n\n"
        "BRAND VOICE + FORMAT (guide the caption + hashtags + idea):\n"
        f"{spec['guidelines']}\n\n"
        f"Return ONLY a single-line JSON object with ALL FOUR keys present and non-empty: "
        f"{{\"facts\": [ {n} plain-language strings ], \"caption\": \"the full post "
        "caption\", \"hashtags\": \"space-separated hashtags, each starting with #\", "
        f"\"post_idea\": \"{idea_desc}\"}}. The hashtags MUST be their own field — never "
        "fold them into the caption. Do NOT wrap the JSON in markdown or code fences, and "
        "do NOT add any text before or after. Inside string values use \\n for any line "
        "breaks — never a raw line break. Output the JSON object only."
    )


class HotTopicReels:
    """Compiles the post package, then (on command) dispatches it to ATHENA/higgbot."""

    # ------------------------------------------------------- compiled-package store
    async def _load_package(self, db: AsyncSession, brand: str = "ibc") -> Dict:
        key = _brand_specs()[_resolve_brand(brand)]["state_key"]
        try:
            row = (await db.execute(
                select(AutomationState).where(AutomationState.key == key)
            )).scalars().first()
            if row and isinstance(row.data, dict):
                return dict(row.data)
        except Exception as e:  # noqa: BLE001
            logger.debug(f"hot-topic load package failed: {e}")
        return {}

    async def _save_package(self, db: AsyncSession, package: Dict, brand: str = "ibc") -> None:
        key = _brand_specs()[_resolve_brand(brand)]["state_key"]
        try:
            row = (await db.execute(
                select(AutomationState).where(AutomationState.key == key)
            )).scalars().first()
            if row:
                row.data = package
            else:
                db.add(AutomationState(key=key, data=package))
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
    async def compile_package(self, db: AsyncSession, brand: str = "ibc",
                              intel: Optional[str] = None) -> Dict:
        """Compile a brand-tailored post package (facts + caption + hashtags + idea).

        `brand`: 'ibc' (ibluezcluezflow reel) or 'nxg' (NXG Facebook post). `intel`
        lets a caller pass the briefing once and reuse it across both brands."""
        brand = _resolve_brand(brand)
        spec = _brand_specs()[brand]
        n = max(1, int(getattr(settings, "hot_topic_facts", 3)))
        if intel is None:
            intel = await self._latest_intel(db)
        if not intel:
            return {"ok": False, "reason": "no_intel", "brand": brand}

        prompt = ("Here is today's compiled economic intelligence. Compile the package per "
                  "your rules:\n\n" + intel)

        obj: Optional[Dict] = None
        raw = ""
        for attempt in range(2):  # one retry — JSON reliability
            try:
                raw = await claude_client.chat(
                    messages=[{"role": "user", "content": prompt}],
                    system_prompt=_compile_system(n, brand),
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
            logger.warning(f"hot-topic compile ({brand}): unparseable output: {raw[:300]!r}")
            return {"ok": False, "reason": "compile_failed", "brand": brand}

        package = {
            "brand": brand,
            "brand_name": spec["name"],
            "format": spec["format"],
            "accounts": spec["accounts"],
            "facts": [str(f).strip() for f in obj.get("facts") or [] if str(f).strip()][:n],
            "caption": str(obj.get("caption", "")).strip(),
            "hashtags": str(obj.get("hashtags", "")).strip(),
            "post_idea": str(obj.get("post_idea", "")).strip(),
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        if not package["facts"]:
            return {"ok": False, "reason": "compile_failed", "brand": brand}
        await self._save_package(db, package, brand)
        return {"ok": True, "package": package, "brand": brand}

    async def compile_brands(self, db: AsyncSession, brands: List[str]) -> Dict:
        """Compile one or more brands from a SINGLE shared briefing (one web search)."""
        brands = [_resolve_brand(b) for b in brands] or ["ibc"]
        # de-dup, preserve order
        seen: List[str] = []
        for b in brands:
            if b not in seen:
                seen.append(b)
        intel = await self._latest_intel(db)
        if not intel:
            return {"ok": False, "reason": "no_intel", "results": {}}
        results: Dict[str, Dict] = {}
        for b in seen:
            results[b] = await self.compile_package(db, brand=b, intel=intel)
        ok = any(r.get("ok") for r in results.values())
        return {"ok": ok, "results": results}

    # ------------------------------------------------------------ STEP 2: dispatch
    async def dispatch(self, db: AsyncSession, brand: str = "ibc") -> Dict:
        """Hand a brand's held package to ATHENA for generation + publish."""
        if not getattr(settings, "athena_enabled", True):
            return {"ok": False, "reason": "athena_disabled"}

        brand = _resolve_brand(brand)
        spec = _brand_specs()[brand]
        stored = await self._load_package(db, brand)
        package = stored if stored.get("facts") else None
        if package is None:
            # Nothing compiled yet — compile on the fly so the dispatch still works.
            res = await self.compile_package(db, brand=brand)
            if not res.get("ok"):
                return {"ok": False, "reason": res.get("reason", "no_package"), "brand": brand}
            package = res["package"]

        # Full ORELIUS -> ATHENA publish contract. ATHENA's account-aware handler reads
        # accountId/brandId/platform/format to route to the correct account, and
        # `content` (structured) / the brief text as the exact post to publish.
        meta_extra = {
            "accountId": spec["account_id"],
            "brandId": spec["brand_id"],
            "brand": spec["name"],
            "platform": spec["platform"],
            "target": spec["target"],
            "format": spec["format"],
            "account": spec["accounts"],
            "publish": True,
            "content": {
                "caption": package.get("caption", ""),
                "hashtags": package.get("hashtags", ""),
                "post_idea": package.get("post_idea", ""),
                "facts": package.get("facts", []),
            },
        }
        if spec["solo"]:
            count = 0
            facts = package.get("facts") or []
            for i, fact in enumerate(facts, 1):
                await athena.enqueue_design_request(
                    db, request=self._athena_brief(package, brand, solo_fact=fact,
                                                   idx=i, total=len(facts)),
                    kind=spec["athena_kind"], action=spec["athena_action"],
                    meta_extra=meta_extra,
                )
                count += 1
            dispatched = count
        else:
            await athena.enqueue_design_request(
                db, request=self._athena_brief(package, brand),
                kind=spec["athena_kind"], action=spec["athena_action"],
                meta_extra=meta_extra,
            )
            dispatched = 1

        logger.info(f"Hot-topic: dispatched {dispatched} {spec['format']} job(s) "
                    f"to ATHENA for {spec['name']}")
        return {"ok": True, "package": package, "dispatched": dispatched, "brand": brand}

    async def dispatch_brands(self, db: AsyncSession, brands: List[str]) -> Dict:
        """Dispatch one or more brands' packages to ATHENA."""
        brands = [_resolve_brand(b) for b in brands] or ["ibc"]
        seen: List[str] = []
        for b in brands:
            if b not in seen:
                seen.append(b)
        results: Dict[str, Dict] = {b: await self.dispatch(db, brand=b) for b in seen}
        ok = any(r.get("ok") for r in results.values())
        return {"ok": ok, "results": results}

    def _athena_brief(self, package: Dict, brand: str = "ibc",
                      solo_fact: Optional[str] = None, idx: int = 1, total: int = 1) -> str:
        brand = _resolve_brand(brand)
        spec = _brand_specs()[brand]
        higg = getattr(settings, "higgbot_name", "higgbot")
        accounts = spec["accounts"]
        facts = package.get("facts") or []
        if solo_fact is not None:
            facts_block = f"THE FACT (verified, plain language): {solo_fact}"
            header = f"Solo piece {idx} of {total} — centers on ONE fact."
        else:
            facts_block = "KEY FACTS (verified, plain language):\n" + "\n".join(
                f"{i}. {f}" for i, f in enumerate(facts, 1)
            )
            header = "This piece carries the compiled package (all facts + caption)."

        if spec["format"] == "reel":
            what = (f"generate an AWARD-WINNING Instagram REEL for {accounts}")
            roadmap = "ibluezcluezflow"
        else:
            what = (f"produce and publish a FACEBOOK FEED POST (not a reel) for {accounts}")
            roadmap = "NXG Life Group"
        return (
            f"[{spec['name']}] Hand these details to {higg} — the Master's OWN custom "
            f"design agent (NOT Higgsfield) — to {what}. {header} Execute publishing per "
            f"the {roadmap} CONTENT ROADMAP you hold in your files (format, style, and "
            f"account routing come from that roadmap).\n\n"
            f"POST CAPTION:\n{package.get('caption','')}\n\n"
            f"HASHTAGS:\n{package.get('hashtags','')}\n\n"
            f"POST IDEA:\n{package.get('post_idea','')}\n\n"
            f"{facts_block}\n\n"
            f"Follow the {roadmap} content roadmap in your files for everything else."
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
