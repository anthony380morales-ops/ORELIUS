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
from .shared_memory import shared_memory
from ..models.automation_state import AutomationState  # noqa: F401 (register table)
from . import athena

import re

# ATHENA hard-rejects any caption containing the sequence "--" (its autonomous-text
# guardrail) and returns published:false WITHOUT posting. Beyond that, the brand rule
# is NO long dashes at all in published copy. So before a package is ever stored or
# dispatched, replace every double(+) hyphen, em dash, and en dash with a comma.
# Single hyphens inside words/ranges (year-over-year, 3.75-4%) are preserved.
_LONG_DASH = re.compile(r"\s*(?:-{2,}|[—–])\s*")


def _sanitize_for_athena(text: str) -> str:
    """Make compiled text safe for ATHENA's guardrails and the brand's no-dash rule:
    replace every long/double/em/en dash with a comma (never emit a dash), then tidy
    the resulting punctuation. Single hyphens inside words/ranges are preserved."""
    s = _LONG_DASH.sub(", ", (text or ""))
    s = re.sub(r"\s+,", ",", s)        # no space before a comma
    s = re.sub(r"(,\s*){2,}", ", ", s) # collapse doubled commas
    return s.strip().strip(",").strip()


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


# NXG serves three income tiers. Each post is tailored to ONE tier; ORELIUS rotates
# through them so the page speaks to every segment over time. This is the "who am I
# solving a problem for today" that drives the story-first NXG caption.
NXG_INCOME_TIERS = [
    {
        "key": "budget",
        "label": "Low-Income / Budget-Conscious families",
        "audience": ("working families and individuals on a tight budget who quietly "
                     "believe real protection is a luxury they can't afford"),
        "emotional_core": ("the fear of leaving the people they love with debt, funeral "
                           "costs, or nothing — and the shame of thinking they can't fix it"),
        "product_angle": ("affordable, essential protection (like term life) that often "
                          "costs less than they expect and keeps their family from falling "
                          "off a cliff if the worst happens"),
        "promise": "value, durability, and covering the essentials — protection they can actually afford",
    },
    {
        "key": "massmarket",
        "label": "Middle-Income / Mass-Market families",
        "audience": ("hardworking middle-class families and homeowners who built a stable "
                     "life and don't want one event to unravel it"),
        "emotional_core": ("the quiet fear that the life they worked so hard for — the "
                           "home, the kids' future, the income — could come apart if "
                           "something happened to them"),
        "product_angle": ("income replacement, mortgage protection, and coverage that can "
                          "also build value — protecting the life they've built and the "
                          "future they're planning for"),
        "promise": "balance of quality, protection, and convenience — protecting everything they've earned",
    },
    {
        "key": "affluent",
        "label": "High-Income / Affluent families & business owners",
        "audience": ("successful professionals, high earners, and business owners focused "
                     "on legacy, taxes, and passing wealth on their terms"),
        "emotional_core": ("the weight of making sure everything they built endures — that "
                           "family and business are protected for generations"),
        "product_angle": ("bespoke strategy — estate & legacy planning, tax-advantaged "
                          "wealth transfer, business protection, and generational wealth"),
        "promise": "exclusivity, premium quality, and a personalized strategy built around their life",
    },
]


def _select_tier(index: Optional[int] = None) -> Dict:
    """Pick which income tier a NXG post targets. Rotates by the rotation index so
    EACH post targets a different demographic; falls back to day-of-year."""
    if index is None:
        index = datetime.now(timezone.utc).timetuple().tm_yday
    return NXG_INCOME_TIERS[index % len(NXG_INCOME_TIERS)]


# IBC covers a different ECONOMIC ANGLE each post, so every graphic through the day
# carries distinct facts (not the same Fed/CPI/mortgage numbers repeated). Rotated
# by the same rotation index that drives NXG's tier.
IBC_ANGLES = [
    "interest rates & the Federal Reserve — rate decisions, fed funds, what it means for borrowing and saving",
    "inflation & cost of living — CPI, real wages, purchasing power, everyday prices",
    "housing & mortgages — mortgage rates, affordability, home equity, real estate",
    "jobs & the broader economy — employment, GDP, consumer spending, recession signals",
    "markets & yields — Treasury yields, stocks, bonds, where safe money earns today",
    "debt & banking — national debt, deficits, bank stability, FDIC, where big money parks",
    # News-driven themes (no fixed FRED metric) — pulled from CNBC + verified web each day,
    # so the feed diversifies well beyond Fed/rates and stays timely.
    "Social Security & retirement policy — benefits, COLA, claiming age, solvency, what retirees rely on",
    "taxes & retirement rules — IRS limits, Roth vs traditional, RMDs, and legislation affecting savers",
    "consumer credit & household finance — credit-card and loan debt, savings behavior, real wages",
    "business & small business — corporate earnings, hiring, succession, owner finances, commercial credit",
]


def _select_angle(index: Optional[int] = None) -> str:
    if index is None:
        index = datetime.now(timezone.utc).timetuple().tm_yday
    return IBC_ANGLES[index % len(IBC_ANGLES)]


# NXG directive §5 + §20: the CATEGORY of the day's posts follows a weekly rhythm
# (Mon=0 .. Sun=6). Economic angle + income tier still vary per slot for within-day
# distinctness, but the category sets each day's PURPOSE and structure.
NXG_CONTENT_CATEGORIES = {
    0: {"key": "intelligence", "name": "Breaking Financial Intelligence", "question": "What just changed?",
        "guidance": "Decode a real, current development (Fed, inflation, Treasury yields, Social "
                    "Security, taxes, banking, pensions, retirement regulations): what happened, what "
                    "it means in plain English, who it affects. Attention + authority."},
    1: {"key": "problem", "name": "Retirement Problem", "question": "What could go wrong?",
        "guidance": "Surface ONE real retirement risk (longevity, inflation, sequence-of-returns, "
                    "income gap, taxes, healthcare, Social Security timing, over-concentration) — the "
                    "mistake people discover too late. Educate on WHY it happens. Never fear-monger, "
                    "never pitch a product."},
    2: {"key": "education", "name": "Retirement Education", "question": "How does this actually work?",
        "guidance": "Teach ONE concept clearly (401k, 403b, IRA, Roth, pension, Social Security, "
                    "annuities, life insurance, taxes, sequence risk, longevity, income planning). "
                    "Problem -> options -> tradeoffs -> what to understand before deciding."},
    3: {"key": "scenario", "name": "Scenario / Case Study", "question": "What would this look like?",
        "guidance": "Use a clearly HYPOTHETICAL, anonymized person (age, assets, projected Social "
                    "Security, goal) and walk through the planning QUESTIONS and tradeoffs — NOT "
                    "personalized advice. State plainly that it is illustrative."},
    4: {"key": "business", "name": "Business Owner Intelligence", "question": "How does this affect owners?",
        "guidance": "Speak to business owners (40-65): succession, 'sell someday' as an exit "
                    "assumption vs a real strategy, key-person risk, retirement outside the business, "
                    "taxes, employee retirement (CalSavers). Educate; open a professional conversation."},
    5: {"key": "interactive", "name": "Interactive", "question": "Your turn.",
        "guidance": "A poll, quiz, or ONE sharp question that invites a reply (e.g. 'Your #1 "
                    "retirement concern: running out of money / taxes / market crashes / healthcare?'). "
                    "This is the lead-gen category — the close invites a comment."},
    6: {"key": "recap", "name": "Weekly Intelligence Recap", "question": "What to know before Monday.",
        "guidance": "Recap the week's most important VERIFIED developments — the 3 things that matter "
                    "for retirement and money heading into next week. Tight and scannable."},
}


def _content_category(idx: Optional[int] = None) -> Dict:
    """The day's content category (weekly rhythm), in the posting timezone."""
    if idx is None:
        try:
            from zoneinfo import ZoneInfo
            tzname = getattr(settings, "autopost_timezone", "America/Los_Angeles")
            idx = datetime.now(ZoneInfo(tzname)).weekday()
        except Exception:  # noqa: BLE001
            idx = datetime.utcnow().weekday()
    return NXG_CONTENT_CATEGORIES.get(idx % 7, NXG_CONTENT_CATEGORIES[0])


# Compliance guardrail (NXG directive §24/§25): language that must never appear in
# published copy (unsupported guarantees / hype). Scanned on every compiled post.
_BANNED_PHRASES = [
    "guaranteed return", "guaranteed returns", "guaranteed wealth", "guaranteed retirement",
    "risk-free", "risk free", "foolproof", "get rich", "secret strategy",
    "best investment", "no risk", "can't lose", "cannot lose", "100% safe",
]


def _compliance_scan(text: str) -> List[str]:
    """Return a list of compliance issues found in copy (empty = clean)."""
    low = (text or "").lower()
    issues = [f"banned phrase: '{p}'" for p in _BANNED_PHRASES if p in low]
    t = text or ""
    if "--" in t or "—" in t or "–" in t:
        issues.append("forbidden dash (double hyphen / em dash / en dash)")
    return issues


# --- Rich NXG infographic layouts -------------------------------------------------
# Every NXG post rotates a visual LAYOUT so the Facebook feed varies. A second,
# tightly-scoped model call fills the layout's structure from the SAME verified
# figures; ATHENA renders it over a fresh financial-scene photo. Any failure falls
# back to the photo-hero, so the proven caption/facts path is never at risk.
_ACCENTS = {"red", "blue", "gold", "green", "cyan"}
_ICONS = {"shield", "coins", "bank", "person", "chart", "home"}

# The day's CATEGORY (weekly rhythm) sets the NXG visual LAYOUT so the format matches
# the day's purpose. All of a day's posts share the layout; angle + income tier still
# vary per slot. Any layout that can't be built cleanly falls back to the photo-hero.
_CATEGORY_LAYOUT = {
    "intelligence": "briefing",    # Mon — Breaking Financial Intelligence (attention)
    "problem": "hero",             # Tue — Retirement Problem (pain, human/story)
    "education": "comparison",     # Wed — Retirement Education (how it works, options)
    "scenario": "scenario",        # Thu — Scenario / Case Study (tangible)
    "business": "analysis",        # Fri — Business Owner Intelligence (two-sided)
    "interactive": "interactive",  # Sat — Interactive (poll / question, lead-gen)
    "recap": "news",               # Sun — Weekly Intelligence Recap (headlines)
}


def _nxg_layout_for_category(category_key: Optional[str]) -> str:
    return _CATEGORY_LAYOUT.get(str(category_key or ""), "hero")


def _san_deep(x):
    """Sanitize every string in a nested structure (no long dashes, ATHENA-safe)."""
    if isinstance(x, str):
        return _sanitize_for_athena(x)
    if isinstance(x, list):
        return [_san_deep(i) for i in x]
    if isinstance(x, dict):
        return {k: _san_deep(v) for k, v in x.items()}
    return x


_LAYOUT_SCHEMA = {
    "briefing": (
        'a numbered economic-briefing infographic. JSON: {"heroNumber":"2","heroTitle":'
        '"SHORT UPPERCASE HOOK","heroSub":"WHAT IT MEANS FOR YOU","intro":"one plain sentence",'
        '"sections":[{"accent":"red","title":"SHORT UPPERCASE","stats":[{"value":"+3.4%",'
        '"label":"CPI YoY","unit":"optional","sub":"optional second figure"}],"source":"BLS",'
        '"bottomLine":"one plain takeaway sentence"}],"footerItems":[{"value":"3.4%","label":'
        '"Inflation"}]}. EXACTLY 2 sections; 1-2 stats each; accents from red/blue/gold/green/cyan;'
        ' 3-4 footerItems.'
    ),
    "comparison": (
        'a 4-column financial-tools comparison. JSON: {"columns":[{"icon":"shield","name":'
        '"LIFE INSURANCE","sub":"(Whole, Term, IUL)","pros":["short line","short line"],"cons":'
        '["short line","short line"]}]}. EXACTLY 4 columns covering Life Insurance, Annuities, '
        'Bank Savings, and Retirement (401k/IRA). icon from shield/coins/bank/person/chart/home; '
        '2-3 short pros and 2-3 short cons each. Educator tone: options and tradeoffs, never '
        '"ours is better".'
    ),
    "analysis": (
        'a two-column honest analysis. JSON: {"title":"SHORT UPPERCASE","subtitle":"one plain '
        'line","topStats":[{"value":"4.98%","label":"10-Yr Treasury","sub":"optional"}],'
        '"leftPoints":[{"label":"bold claim","note":"one plain line"}],"rightPoints":[{"label":'
        '"bold claim","note":"one plain line"}],"realValuePoints":["short","short"]}. leftPoints '
        '= where it genuinely helps; rightPoints = where the common story overreaches; 2-3 each; '
        '0-3 topStats; 2-3 realValuePoints.'
    ),
    "news": (
        'a two-headline economic-news card. JSON: {"title":"KEY ECONOMIC HEADLINES","subtitle":'
        '"one plain line","left":{"headline":"SHORT UPPERCASE","body":"one or two plain sentences",'
        '"stats":[{"value":"7,673","label":"S&P 500","delta":"-0.48%"}]},"right":{"headline":'
        '"SHORT UPPERCASE","body":"one or two plain sentences","stats":[{"value":"3.4%","label":'
        '"CPI YoY"}]},"bigPicture":[{"value":"3.4%","label":"Inflation"}]}. 1-2 stats per story; '
        '3-4 bigPicture items.'
    ),
    "scenario": (
        'a clearly HYPOTHETICAL, anonymized retirement case study. JSON: {"title":"SHORT UPPERCASE '
        'QUESTION","personaName":"John","personaMeta":"Age 57 · California","stats":[{"value":"$650k",'
        '"label":"401(k)"},{"value":"$2,800","label":"Est. Social Security"},{"value":"62","label":'
        '"Target Retire Age"}],"questionsTitle":"THE QUESTIONS THAT DECIDE IT","questions":["one plain '
        'planning question","another"],"takeaway":"one plain sentence"}. Invent a realistic but clearly '
        'hypothetical person (first name only); 2-4 stat chips; 3-4 planning questions; never real advice.'
    ),
    "interactive": (
        'a poll / one sharp question that invites a reply. JSON: {"eyebrow":"YOUR TURN","question":'
        '"one sharp, plain question","options":["short option","short option"],"prompt":"Comment your '
        'answer below."}. 0-4 short options (omit or empty for an open question); keep the question tight.'
    ),
}


def _layout_system(layout: str, figures: List[str]) -> str:
    fig_block = ("Use ONLY these verified figures (never invent a number or source): "
                 + "; ".join(str(f) for f in figures)) if figures else \
        "Use ONLY figures explicitly present in the intelligence; never invent a number or source."
    return (
        "You are ORELIUS's visual-content builder for NXG Life Group, a trusted financial and "
        "retirement EDUCATION brand. Build ONLY the JSON for " + _LAYOUT_SCHEMA[layout] + "\n\n"
        + fig_block + "\n\n"
        "HARD RULES: education only, not individualized advice; no guarantees or hype; attribute "
        "real sources; keep every line tight, plain, and scroll-stopping; NEVER use a double hyphen "
        "or any long dash (no '--', no em dash, no en dash), use commas or periods. Return ONLY the "
        "single-line JSON object, all keys present, no markdown, no code fences, no text before or "
        "after; inside strings use \\n for any line break, never a raw newline."
    )


def _parse_layout_json(raw: str) -> Optional[Dict]:
    s = (raw or "").strip()
    if s.startswith("```"):
        s = s.strip("`")
        s = s[s.find("{"):] if "{" in s else s
    a, b = s.find("{"), s.rfind("}")
    if a == -1 or b == -1 or b <= a:
        return None
    try:
        obj = json.loads(s[a:b + 1])
        return obj if isinstance(obj, dict) else None
    except Exception:  # noqa: BLE001
        return None


def _validate_layout(layout: str, obj: Dict) -> Optional[Dict]:
    """Validate + clamp + sanitize the model's layout JSON. Returns the attach dict
    ({"layout":..., <payload key>:...}) or None if the shape is unusable."""
    try:
        o = _san_deep(obj)
        if layout == "briefing":
            secs = [s for s in (o.get("sections") or []) if isinstance(s, dict) and s.get("title") and (s.get("stats") or [])][:2]
            if not secs:
                return None
            for i, s in enumerate(secs):
                if s.get("accent") not in _ACCENTS:
                    s["accent"] = "red" if i == 0 else "blue"
                s["stats"] = [st for st in (s.get("stats") or []) if isinstance(st, dict) and st.get("value")][:2]
            bf = {
                "heroNumber": str(o.get("heroNumber", "") or ""),
                "heroTitle": str(o.get("heroTitle", "") or ""),
                "heroSub": str(o.get("heroSub", "") or ""),
                "intro": str(o.get("intro", "") or ""),
                "sections": secs,
                "footerItems": [f for f in (o.get("footerItems") or []) if isinstance(f, dict) and f.get("value")][:4],
            }
            return {"layout": "briefing", "briefing": bf}
        if layout == "comparison":
            cols = []
            for i, c in enumerate((o.get("columns") or [])[:4]):
                if not isinstance(c, dict) or not c.get("name"):
                    continue
                if c.get("icon") not in _ICONS:
                    c["icon"] = ["shield", "coins", "bank", "person"][i % 4]
                c["pros"] = [str(p) for p in (c.get("pros") or []) if str(p).strip()][:4]
                c["cons"] = [str(p) for p in (c.get("cons") or []) if str(p).strip()][:4]
                if c["pros"] and c["cons"]:
                    cols.append(c)
            if len(cols) < 2:
                return None
            return {"layout": "comparison", "compareColumns": cols}
        if layout == "analysis":
            lp = [p for p in (o.get("leftPoints") or []) if isinstance(p, dict) and p.get("label")][:4]
            rp = [p for p in (o.get("rightPoints") or []) if isinstance(p, dict) and p.get("label")][:4]
            if not lp or not rp:
                return None
            an = {
                "title": str(o.get("title", "") or ""),
                "subtitle": str(o.get("subtitle", "") or ""),
                "topStats": [s for s in (o.get("topStats") or []) if isinstance(s, dict) and s.get("value")][:3],
                "leftTitle": str(o.get("leftTitle", "") or ""),
                "leftPoints": lp,
                "rightTitle": str(o.get("rightTitle", "") or ""),
                "rightPoints": rp,
                "realValueTitle": str(o.get("realValueTitle", "") or ""),
                "realValuePoints": [str(p) for p in (o.get("realValuePoints") or []) if str(p).strip()][:3],
            }
            return {"layout": "analysis", "analysis": an}
        if layout == "news":
            left, right = o.get("left"), o.get("right")
            if not (isinstance(left, dict) and left.get("headline") and isinstance(right, dict) and right.get("headline")):
                return None
            for s in (left, right):
                s["body"] = str(s.get("body", "") or "")
                s["stats"] = [st for st in (s.get("stats") or []) if isinstance(st, dict) and st.get("value")][:3]
            nw = {
                "title": str(o.get("title", "") or ""),
                "subtitle": str(o.get("subtitle", "") or ""),
                "left": left, "right": right,
                "bigPicture": [f for f in (o.get("bigPicture") or []) if isinstance(f, dict) and f.get("value")][:4],
            }
            return {"layout": "news", "news": nw}
        if layout == "scenario":
            qs = [str(q) for q in (o.get("questions") or []) if str(q).strip()][:4]
            if not o.get("personaName") or not qs:
                return None
            sc = {
                "title": str(o.get("title", "") or ""),
                "personaName": str(o.get("personaName", "") or ""),
                "personaMeta": str(o.get("personaMeta", "") or ""),
                "stats": [s for s in (o.get("stats") or []) if isinstance(s, dict) and s.get("value")][:4],
                "questionsTitle": str(o.get("questionsTitle", "") or ""),
                "questions": qs,
                "takeaway": str(o.get("takeaway", "") or ""),
            }
            return {"layout": "scenario", "scenario": sc}
        if layout == "interactive":
            if not str(o.get("question", "")).strip():
                return None
            iv = {
                "eyebrow": str(o.get("eyebrow", "") or ""),
                "question": str(o.get("question", "") or ""),
                "options": [str(x) for x in (o.get("options") or []) if str(x).strip()][:4],
                "prompt": str(o.get("prompt", "") or ""),
            }
            return {"layout": "interactive", "interactive": iv}
    except Exception:  # noqa: BLE001
        return None
    return None


async def _compile_nxg_layout(layout: str, intel: str, figures: List[str], temperature: float) -> Optional[Dict]:
    """One tightly-scoped model call to build a layout's structure. None on any issue."""
    prompt = ("From this compiled economic intelligence, build the layout JSON per your rules:\n\n" + intel)
    for _ in range(2):
        try:
            raw = await claude_client.chat(
                messages=[{"role": "user", "content": prompt}],
                system_prompt=_layout_system(layout, figures),
                stream=False,
                max_tokens=settings.oreilus_report_max_tokens,
                temperature=temperature,
            )
        except Exception as e:  # noqa: BLE001
            logger.error(f"nxg layout compile call failed: {e}")
            continue
        obj = _parse_layout_json(raw)
        if obj:
            cleaned = _validate_layout(layout, obj)
            if cleaned:
                return cleaned
    return None


def _angle_index(rotation: Optional[int]) -> int:
    if rotation is None:
        rotation = datetime.now(timezone.utc).timetuple().tm_yday
    return rotation % len(IBC_ANGLES)


# Per NXG directive §13 (lead ladder) + §43 hierarchy: most posts EDUCATE and spark
# curiosity; only a minority push the funnel. This keeps the feed from feeling salesy
# or desperate for a click. Rotation drives the mix so it varies post to post.
#   curiosity — pure education, ends on a genuine question inviting comments (no link)
#   engage    — micro-commitment: save/share/answer, or an interactive prompt (no link)
#   funnel    — the soft CLARITY invitation (+ optional link) — the warm-lead capture
_CTA_MODES = ["curiosity", "engage", "curiosity", "funnel", "curiosity", "engage"]


def _select_cta(rotation: Optional[int]) -> str:
    if rotation is None:
        rotation = datetime.now(timezone.utc).timetuple().tm_yday
    return _CTA_MODES[rotation % len(_CTA_MODES)]


def _metric_angle(label: str) -> int:
    """Assign a verified metric to EXACTLY ONE angle (indices align to IBC_ANGLES),
    so each day's posts draw from non-overlapping data — no metric appears twice."""
    l = (label or "").lower()
    if "mortgage" in l or "housing" in l:
        return 2  # housing & mortgages
    if "cpi" in l or "pce" in l or "consumer price" in l:
        return 1  # inflation
    if any(k in l for k in ("moody", "corporate bond", "aaa", "baa", "national debt",
                            "avg interest", "fdic", "bank")):
        return 5  # debt & banking (check before treasury so Moody's spread lands here)
    if any(k in l for k in ("s&p", "volatility", "vix")) or "10-year treasury" in l or "10-yr treasury" in l:
        return 4  # markets & yields
    if any(k in l for k in ("federal funds", "2-year treasury", "yield curve", "spread")):
        return 0  # interest rates & the Fed
    if any(k in l for k in ("unemployment", "payroll", "jobless", "industrial production",
                            "retail sales", "gdp", "sentiment", "saving")):
        return 3  # jobs & the broader economy
    return 3  # default: economy bucket


def _figures_for_angle(data_points: Optional[Dict], angle_idx: int, cap: int = 6) -> List[str]:
    """Exact verified data lines belonging to this angle, from the finance engine's
    structured snapshot ({source: [{metric,value,unit,date,change_vs_prior}...]}).
    These are handed to the model as the ONLY numbers it may use — no drift, no
    approximation, no cross-post repeats."""
    out: List[str] = []
    for source, items in (data_points or {}).items():
        for it in items or []:
            label = str(it.get("metric", "")).strip()
            if not label or _metric_angle(label) != angle_idx:
                continue
            val = it.get("value")
            if val in (None, "", "."):
                continue
            unit = (it.get("unit") or "").strip()
            val_str = f"{val}%" if unit == "%" else (f"{val} {unit}".strip())
            line = f"{label}: {val_str}"
            date = it.get("date")
            chg = it.get("change_vs_prior")
            extra = []
            if date:
                extra.append(f"as of {date}")
            if chg is not None:
                extra.append(f"change {chg:+g} vs prior")
            if extra:
                line += " (" + "; ".join(extra) + ")"
            line += f" [{source}]"
            out.append(line)
    return out[:cap]


async def _next_rotation(db: AsyncSession) -> int:
    """A persistent, always-incrementing counter so each post (across slots and days)
    gets a different NXG tier + IBC angle. Survives restarts via AutomationState."""
    key = "content_rotation"
    try:
        row = (await db.execute(
            select(AutomationState).where(AutomationState.key == key)
        )).scalars().first()
        n = (int(row.data.get("n", 0)) if row and isinstance(row.data, dict) else 0) + 1
        if row:
            row.data = {"n": n}
        else:
            db.add(AutomationState(key=key, data={"n": n}))
        await db.flush()
        return n
    except Exception as e:  # noqa: BLE001 - never block a compile on the counter
        logger.debug(f"rotation counter failed: {e}")
        return int(datetime.now(timezone.utc).timestamp()) // 900  # varies over time


def _compile_system(n: int, brand: str = "ibc", tier: Optional[Dict] = None,
                    angle: Optional[str] = None, figures: Optional[List[str]] = None,
                    cta_mode: str = "curiosity", category: Optional[Dict] = None) -> str:
    spec = _brand_specs()[_resolve_brand(brand)]
    kw = getattr(settings, "funnel_optin_keyword", "CLARITY")
    url = getattr(settings, "funnel_quiz_url", "https://nxglifegroup.org/")

    # Weekly content category (the day's PURPOSE) + the non-negotiable trust & compliance
    # rules — prepended to every post so all generated content follows the NXG standard.
    category = category or _content_category()
    category_block = (
        f"TODAY'S CONTENT CATEGORY (weekly rhythm — this sets the post's PURPOSE and shape): "
        f"{category['name']} — \"{category['question']}\"\n{category['guidance']}\n\n"
    )
    trust_rule = (
        "TRUST RULE (never violate): do NOT write 'here's why our product is better.' "
        "Instead — name the PROBLEM, lay out the OPTIONS, the TRADEOFFS, and what someone "
        "should understand BEFORE deciding. You are an educator, not a salesperson.\n"
    )
    compliance_rule = (
        "COMPLIANCE (hard rules): educational only, not individualized advice; never use "
        "unsupported guarantee/hype language (guaranteed returns, risk-free, foolproof, best "
        "investment, get rich, can't lose, 100% safe); attribute real sources; never invent a "
        "figure, statistic, quote, or affiliation; never imply government endorsement; "
        "NEVER use a double hyphen or any long dash (no '--', no em dash, no en dash). "
        "Use commas or periods instead.\n\n"
    )

    # NXG directive: lead with education + curiosity; only a minority of posts push the
    # funnel, so the feed never feels salesy or desperate for a click. This block is the
    # ONLY CTA guidance the model gets for this post — it rotates per `cta_mode`.
    if cta_mode == "funnel":
        cta_block = (
            "CLOSE — SOFT WARM-LEAD INVITATION (this post is one of the few that captures a "
            f"lead, so keep it human, never pushy): after the education lands, invite the "
            f"reader to comment '{kw}' to get a free, no-pressure Retirement/Financial Clarity "
            f"resource (a real person follows up only if they want). You MAY mention the link "
            f"{url} once, softly. Do not stack multiple CTAs; one gentle invitation."
        )
    elif cta_mode == "engage":
        cta_block = (
            "CLOSE — MICRO-COMMITMENT (NO link, NO funnel keyword): end with a light, human "
            "invitation to engage — e.g. 'Save this for when you need it,' 'Send this to "
            "someone planning their retirement,' or a one-line question they can answer in "
            "the comments. The goal is a small, natural action, not a sale."
        )
    else:  # curiosity (the default, most common)
        cta_block = (
            "CLOSE — CURIOSITY & CONVERSATION (NO link, NO funnel keyword, NO pitch): end on "
            "a genuine, open question that makes the reader reflect and want to reply — the "
            "kind of question a trusted advisor would ask, not a marketer. Leave them thinking, "
            "not sold to."
        )

    # Exact verified figures for this post's angle — the ONLY numbers the model may use.
    fig_block = ""
    if figures:
        fig_block = (
            "\n\nVERIFIED FIGURES FOR THIS ANGLE — these are the ONLY numbers you may use. "
            "Use each EXACTLY as written (same value, same rounding). Do NOT invent, "
            "estimate, re-round, or add any figure not in this list, and do NOT reuse a "
            "generic headline number that isn't here:\n" + "\n".join(f"• {f}" for f in figures)
        )

    # NXG is story-first and problem-first, NOT an economic-fact compiler. It uses the
    # economic reality only as quiet context and translates it into a human problem for
    # ONE income tier, then sells CERTAINTY by solving it — never a pitch.
    kw = getattr(settings, "funnel_optin_keyword", "CLARITY")
    url = getattr(settings, "funnel_quiz_url", "https://nxglifegroup.org/")

    if _resolve_brand(brand) == "nxg":
        tier = tier or _select_tier()
        angle = angle or _select_angle()
        return (
            f"You are the content voice of {spec['name']}, a licensed California life-"
            f"insurance & financial-protection agency. You do NOT write dry economic news or "
            f"market analysis. You write raw, human, story-led Facebook posts that EDUCATE and "
            f"make a real person feel understood — that is how NXG earns trust without pitching.\n\n"
            f"{category_block}{trust_rule}{compliance_rule}"
            f"TODAY YOU ARE WRITING FOR THIS PERSON:\n"
            f"- Tier: {tier['label']}\n"
            f"- Who they are: {tier['audience']}\n"
            f"- The worry they carry: {tier['emotional_core']}\n"
            f"- How NXG solves it: {tier['product_angle']}\n"
            f"- What matters to them: {tier['promise']}\n\n"
            f"THIS POST'S TOPIC (so every post today is DISTINCT): {angle}.\n"
            f"Your anchor is ONE specific, verified development for THIS topic: use an exact "
            f"figure from the VERIFIED FIGURES BELOW when listed; if none are listed for this "
            f"topic, anchor on one specific, recent, verified development from the intelligence "
            f"above (a real figure or fact WITH its source, e.g. CNBC, Treasury, BLS, SSA, IRS) "
            f"and never invent one. HARD RULE: do NOT anchor on the Federal Reserve / fed funds "
            f"rate UNLESS this post's topic is literally interest rates & the Fed. The economy is "
            f"much bigger than the Fed — Social Security, taxes and retirement rules, household "
            f"debt, housing, jobs, markets, and business news are all fair game, and the feed "
            f"must NOT sound like the same rate story every day. Two posts must never share the "
            f"same anchor. Weave that single real fact in naturally, in plain human words — the "
            f"spark, not a lecture. Do NOT list multiple stats, and NEVER invent a number.{fig_block}\n\n"
            f"CRITICAL: the FIRST item in your \"facts\" array is used verbatim as the post's "
            f"IMAGE HEADLINE, so it must be that ONE angle-specific development stated as a "
            f"short, punchy, human line (<= 14 words) — never the Fed rate unless this is the "
            f"rates angle, never a generic slogan.\n\n"
            f"You are an EDUCATOR, not a salesperson. This post's job is to make the reader "
            f"feel understood and a little more informed — to earn trust, not to pitch. "
            f"Hierarchy: TRUTH > TRUST > VALUE > CLARITY > ENGAGEMENT. Never sell a product, "
            f"never imply guarantees, never use fear or fake urgency.\n\n"
            f"WRITE a single Facebook post that: (1) opens on a specific, real human moment "
            f"or feeling tied to that development — a scene, not a chart; (2) names the quiet "
            f"question or worry it raises, out loud; (3) shows you genuinely understand it; "
            f"(4) gives ONE real, useful thing to UNDERSTAND about it — plain-English insight "
            f"or a question worth asking, framed as education (NOT 'here's how our product "
            f"fixes it'); (5) closes per the CLOSE instruction below. 110-200 words, short "
            f"paragraphs with line breaks, conversational, first or second person, zero "
            f"jargon, no guarantees, and NEVER a double hyphen or any long dash (no '--', "
            f"no em dash, no en dash); use commas or periods instead.\n\n"
            f"{cta_block}\n"
            f"After the close, end the caption with exactly this on its own line: "
            f"'CA License #4490102 · Educational, not financial advice.'\n\n"
            f"BRAND VOICE (obey):\n{spec['guidelines']}\n\n"
            f"Return ONLY a single-line JSON object with ALL FOUR keys present and non-empty: "
            f"{{\"facts\": [ the ONE specific real development this post is anchored on, "
            f"stated as a short plain-language line (a real figure/change from the intel, or "
            f"a qualitative development — never an invented statistic), optionally plus 1 "
            f"honest grounding truth ], \"caption\": \"the full human post caption\", "
            f"\"hashtags\": \"space-separated warm relevant tags, each starting with #\", "
            f"\"post_idea\": \"one sentence describing the VISUAL SCENE — a real, human, "
            f"emotional image (a family moment), never a data card\"}}. Do NOT wrap the JSON "
            f"in markdown or code fences, and add no text before or after. Inside string "
            f"values use \\n for line breaks — never a raw line break. Output the JSON only."
        )

    # IBC (@ibluezcluezflow) = economic-intelligence media. It publishes a multi-panel
    # BRIEFING GRAPHIC (figure + label + headline + meaning per panel), not a story or a
    # single card. Built entirely from ORELIUS's compiled economic data.
    if _resolve_brand(brand) == "ibc":
        angle = angle or _select_angle()
        return (
            f"You are the economic-intelligence editor for {spec['name']} (@ibluezcluezflow) "
            f"— a premium 'economic intelligence' media brand for financial professionals, "
            f"business owners, and financially serious people. You decode what is happening "
            f"in the economy and what it MEANS for money decisions. You are NOT a consumer "
            f"life-insurance page and you do not write emotional family stories.\n\n"
            f"{category_block}{trust_rule}{compliance_rule}"
            f"THIS POST'S ANGLE (focus the ENTIRE briefing on this theme, so it is distinct "
            f"from other posts today): {angle}.{fig_block}\n\n"
            f"Build a BRIEFING GRAPHIC of the {n} most impactful VERIFIED data points WITHIN "
            f"THAT ANGLE"
            + (", drawn ONLY from the verified figures listed above" if figures else
               ", each a number/level actually present in the compiled intelligence")
            + f". For EACH point give: the hard "
            f"FIGURE (the exact number/percent/level), a short LABEL "
            f"(e.g. 'CPI · YoY', '10-YR TREASURY', 'FED FUNDS'), a punchy HEADLINE (3-6 "
            f"words), and one plain-language line on what it MEANS for the reader's money.\n\n"
            f"Also write: a scroll-stopping TITLE for the graphic (<= 6 words, e.g. 'TOP 3 "
            f"THINGS MOVING YOUR MONEY' or 'KEY ECONOMIC HEADLINES'); an Instagram CAPTION in "
            f"an intelligent, analytical, confident voice that DECODES the data and explains "
            f"why it matters — teaching, not selling (TRUTH > TRUST > VALUE > CLARITY > "
            f"ENGAGEMENT); and relevant HASHTAGS.\n\n"
            f"{cta_block}\n\n"
            f"HARD RULES: use ONLY figures present in the intelligence — never invent a "
            f"number or a source; education, not individualized advice; no promised returns; "
            f"never a double hyphen or any long dash (no '--', no em dash, no en dash); use "
            f"commas or periods instead.\n\n"
            f"BRAND VOICE:\n{spec['guidelines']}\n\n"
            f"Return ONLY a single-line JSON object with ALL keys present and non-empty: "
            f"{{\"title\": \"the graphic title\", \"panels\": [ {{\"figure\": \"e.g. 3.4%\", "
            f"\"label\": \"e.g. CPI · YoY\", \"headline\": \"3-6 words\", \"meaning\": \"one "
            f"plain line\", \"source\": \"the PRIMARY source of THIS figure, taken from the "
            f"intelligence — e.g. Federal Reserve, BLS, Treasury, NY Fed, BEA, Freddie Mac; "
            f"never invented\"}} (exactly {n} of these) ], \"caption\": \"the full IG caption\", "
            f"\"hashtags\": \"space-separated #tags\"}}. Do NOT wrap the JSON in markdown or "
            f"code fences, add no text before or after, and inside string values use \\n for "
            f"any line breaks — never a raw line break. Output the JSON object only."
        )

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
                              intel: Optional[str] = None,
                              rotation: Optional[int] = None,
                              data_points: Optional[Dict] = None) -> Dict:
        """Compile a brand-tailored post package (facts + caption + hashtags + idea).

        `brand`: 'ibc' (ibluezcluezflow reel) or 'nxg' (NXG Facebook post). `intel`
        lets a caller pass the briefing once and reuse it across both brands.
        `rotation` drives per-post variety (NXG income tier + IBC economic angle) so
        every post through the day is distinct; resolved from a persistent counter."""
        brand = _resolve_brand(brand)
        spec = _brand_specs()[brand]
        n = max(1, int(getattr(settings, "hot_topic_facts", 3)))
        if rotation is None:
            rotation = await _next_rotation(db)
        # NXG rotates income tier AND economic angle; IBC rotates economic angle —
        # all by `rotation` so each post through the day carries a DIFFERENT topic +
        # audience. NXG writes story-first (a touch more warmth); the angle keeps
        # every Facebook post anchored on a distinct, fresh, verified development.
        tier = _select_tier(rotation) if brand == "nxg" else None
        angle = _select_angle(rotation) if brand in ("ibc", "nxg") else None
        # Exact verified figures for THIS angle only — non-overlapping across the day,
        # and the sole numbers the model may use (kills cross-post repeats + drift).
        figures = _figures_for_angle(data_points, _angle_index(rotation)) if data_points else []
        cta_mode = _select_cta(rotation)  # curiosity / engage / funnel — mostly education
        category = _content_category()    # weekly rhythm — the day's content category
        temperature = 0.7 if brand == "nxg" else 0.4
        if intel is None:
            intel = await self._latest_intel(db)
        if not intel:
            return {"ok": False, "reason": "no_intel", "brand": brand}

        if brand == "nxg":
            prompt = ("Here is today's economic reality as quiet background context. Do NOT "
                      "report it — translate what it means for the person you're writing "
                      "for, and write the human post per your rules:\n\n" + intel)
        else:
            prompt = ("Here is today's compiled economic intelligence. Compile the package "
                      "per your rules:\n\n" + intel)

        obj: Optional[Dict] = None
        raw = ""
        for attempt in range(2):  # one retry — JSON reliability
            try:
                raw = await claude_client.chat(
                    messages=[{"role": "user", "content": prompt}],
                    system_prompt=_compile_system(n, brand, tier, angle, figures, cta_mode, category),
                    stream=False,
                    max_tokens=settings.oreilus_report_max_tokens,
                    temperature=temperature,
                )
            except Exception as e:  # noqa: BLE001
                logger.error(f"hot-topic compile call failed (attempt {attempt + 1}): {e}")
                continue
            obj = self._parse_json(raw)
            # IBC returns a briefing (panels); everyone else returns facts.
            if isinstance(obj, dict) and (
                (isinstance(obj.get("panels"), list) and obj["panels"])
                or (isinstance(obj.get("facts"), list) and obj["facts"])
            ):
                break
            obj = None

        if obj is None:
            logger.warning(f"hot-topic compile ({brand}): unparseable output: {raw[:300]!r}")
            return {"ok": False, "reason": "compile_failed", "brand": brand}

        # IBC: clean the structured panels; derive facts/post_idea for compatibility.
        clean_panels: list = []
        for p in (obj.get("panels") or [])[:n]:
            if not isinstance(p, dict):
                continue
            clean_panels.append({
                "figure": _sanitize_for_athena(str(p.get("figure", ""))),
                "label": _sanitize_for_athena(str(p.get("label", ""))),
                "headline": _sanitize_for_athena(str(p.get("headline", ""))),
                "meaning": _sanitize_for_athena(str(p.get("meaning", ""))),
                # Primary source per stat (credibility signal on the briefing graphic).
                "source": _sanitize_for_athena(str(p.get("source", ""))),
            })
        facts_src = obj.get("facts") or [
            f"{p['figure']} — {p['headline']}".strip(" —") for p in clean_panels
        ]

        package = {
            "brand": brand,
            "brand_name": spec["name"],
            "format": spec["format"],
            "accounts": spec["accounts"],
            "facts": [_sanitize_for_athena(str(f)) for f in facts_src if str(f).strip()][:n],
            "caption": _sanitize_for_athena(str(obj.get("caption", ""))),
            "hashtags": _sanitize_for_athena(str(obj.get("hashtags", ""))),
            "post_idea": _sanitize_for_athena(str(obj.get("post_idea", obj.get("title", "")))),
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        if clean_panels:  # IBC intelligence-briefing graphic
            package["panels"] = clean_panels
            package["title"] = _sanitize_for_athena(str(obj.get("title", "")))
        if tier:  # NXG: record which income tier this post was written for
            package["tier"] = tier["key"]
            package["tier_label"] = tier["label"]
        if angle:  # record the economic angle so each post's topic is distinct + visible
            package["angle"] = angle
        package["cta_mode"] = cta_mode  # curiosity / engage / funnel (education-first mix)
        package["category"] = category.get("key")
        package["category_name"] = category.get("name")
        # Valid if we have panels (IBC) or facts (others).
        if not package["facts"] and not clean_panels:
            return {"ok": False, "reason": "compile_failed", "brand": brand}

        # NXG rich layout: rotate a visual FORMAT (briefing/comparison/analysis/news) and
        # fill its structure in a separate, tightly-scoped call. On any failure fall back
        # to the photo-hero — the proven caption/facts above are never affected.
        if brand == "nxg":
            layout = _nxg_layout_for_category(category.get("key"))
            attach = None
            if layout != "hero":
                try:
                    attach = await _compile_nxg_layout(layout, intel, figures, temperature)
                except Exception as e:  # noqa: BLE001
                    logger.warning(f"nxg layout '{layout}' failed, using hero: {e}")
            if attach:
                package.update(attach)
                logger.info(f"nxg post layout: {attach.get('layout')}")
            else:
                package["layout"] = "hero"

        # Compliance gate (NXG directive §24/§25): scan the finished copy. Record any flags
        # for the human/audit trail (recordkeeping) and, for NXG, ensure the required CA
        # license + educational disclosure is present. Never hard-blocks autonomy.
        layout_text = json.dumps(
            {k: package.get(k) for k in ("briefing", "compareColumns", "analysis", "news", "scenario", "interactive") if package.get(k)},
            ensure_ascii=False,
        )
        scan_text = " ".join([package.get("caption", ""), " ".join(package.get("facts", [])), layout_text])
        issues = _compliance_scan(scan_text)
        if brand == "nxg" and "4490102" not in package.get("caption", ""):
            package["caption"] = (package["caption"].rstrip()
                                  + "\n\nCA License #4490102 · Educational, not financial advice.")
        if issues:
            package["compliance_flags"] = issues
            logger.warning(f"compliance flags on {brand} post: {issues}")
            try:
                await shared_memory.remember(
                    db, content=f"Compliance flags on a {spec['name']} post: {issues}",
                    kind="compliance_flag", actor="ORELIUS",
                    meta={"brand": brand, "issues": issues, "caption": package.get("caption", "")[:500]},
                )
            except Exception as e:  # noqa: BLE001
                logger.debug(f"compliance flag record failed: {e}")

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
        # Structured verified figures so each post uses EXACT, angle-specific numbers.
        data_points = await finance_intel.data_snapshot()
        # One rotation per compile so this slot's NXG tier + IBC angle differ from the
        # last slot's — every post through the day is distinct.
        rotation = await _next_rotation(db)
        results: Dict[str, Dict] = {}
        for b in seen:
            results[b] = await self.compile_package(db, brand=b, intel=intel,
                                                    rotation=rotation, data_points=data_points)
        ok = any(r.get("ok") for r in results.values())
        return {"ok": ok, "results": results}

    # ------------------------------------------------------------ STEP 2: dispatch
    async def dispatch(self, db: AsyncSession, brand: str = "ibc",
                       solo: Optional[bool] = None) -> Dict:
        """Hand a brand's held package to ATHENA for generation + publish.

        `solo` overrides the brand's solo-reel setting: pass False to emit exactly
        ONE post (used by the scheduled poster so the daily count matches the plan)."""
        if not getattr(settings, "athena_enabled", True):
            return {"ok": False, "reason": "athena_disabled"}

        brand = _resolve_brand(brand)
        stored = await self._load_package(db, brand)
        package = stored if stored.get("facts") else None
        if package is None:
            # Nothing compiled yet — compile on the fly so the dispatch still works.
            res = await self.compile_package(db, brand=brand)
            if not res.get("ok"):
                return {"ok": False, "reason": res.get("reason", "no_package"), "brand": brand}
            package = res["package"]
        return await self.dispatch_package(db, brand, package, solo=solo)

    async def dispatch_package(self, db: AsyncSession, brand: str, package: Dict,
                              solo: Optional[bool] = None) -> Dict:
        """Dispatch a SPECIFIC pre-compiled package to ATHENA (used by the morning
        planner so the posts shown to the Master are the exact ones that publish)."""
        if not getattr(settings, "athena_enabled", True):
            return {"ok": False, "reason": "athena_disabled"}
        brand = _resolve_brand(brand)
        spec = _brand_specs()[brand]
        use_solo = spec["solo"] if solo is None else bool(solo)

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
                # IBC intelligence-briefing graphic (multi-panel). Present for IBC only.
                "panels": package.get("panels", []),
                "title": package.get("title", ""),
                # NXG rich-format routing + structure (ATHENA renders the matching card,
                # else the photo-hero). Only the keys that were compiled are sent.
                **({"layout": package["layout"]} if package.get("layout") else {}),
                **({"briefing": package["briefing"]} if package.get("briefing") else {}),
                **({"compareColumns": package["compareColumns"]} if package.get("compareColumns") else {}),
                **({"analysis": package["analysis"]} if package.get("analysis") else {}),
                **({"news": package["news"]} if package.get("news") else {}),
                **({"scenario": package["scenario"]} if package.get("scenario") else {}),
                **({"interactive": package["interactive"]} if package.get("interactive") else {}),
            },
        }
        if use_solo:
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

    async def dispatch_brands(self, db: AsyncSession, brands: List[str],
                              solo: Optional[bool] = None) -> Dict:
        """Dispatch one or more brands' packages to ATHENA. `solo` overrides the
        per-brand solo-reel setting for every brand (scheduler passes False)."""
        brands = [_resolve_brand(b) for b in brands] or ["ibc"]
        seen: List[str] = []
        for b in brands:
            if b not in seen:
                seen.append(b)
        results: Dict[str, Dict] = {b: await self.dispatch(db, brand=b, solo=solo) for b in seen}
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
