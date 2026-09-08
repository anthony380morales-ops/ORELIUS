"""
O.R.E.L.I.U.S. Daily Economic Intelligence
------------------------------------------
Every day the automation scans official U.S. sources for NEWLY-RELEASED verified
data (rates, inflation, jobs, growth, credit, markets, banking, fiscal), then has
the Haiku brain condense it into plain-English intelligence — stacked against life
insurance, annuities, and personal/employer retirement accounts, with pros & cons.

Design rules the Master set:
  * VERIFIED ONLY — official data endpoints (the machine-readable form of each
    agency's website). Never fabricate a figure.
  * 2-MONTH BARRIER — never retrieve data older than `finance_lookback_days`.
  * NO REPEATS — a durable memory (AutomationState) records every data point
    already reported; each run surfaces only what is new.

Sources: FRED (Federal Reserve), Moody's corporate-bond yields (via FRED), U.S.
Bureau of Economic Analysis (BEA), U.S. Treasury (Fiscal Data), FDIC.
"""
from __future__ import annotations

import asyncio
import re
from datetime import datetime, timedelta, date
from typing import Dict, List, Optional

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..utils.logger import logger
from .claude_client import claude_client
from .shared_memory import shared_memory
from ..models.automation_state import AutomationState  # noqa: F401  (register table)

_HTTP_TIMEOUT = 20.0
_SEEN_KEY = "finance_seen"

# FRED series — broad economy, not just yields.  (id, label, unit, category)
_FRED_SERIES = [
    ("FEDFUNDS", "Federal Funds Rate", "%", "Rates"),
    ("DGS10", "10-Year Treasury Yield", "%", "Rates"),
    ("DGS2", "2-Year Treasury Yield", "%", "Rates"),
    ("T10Y2Y", "10Y–2Y Treasury Spread (yield curve)", "%", "Rates"),
    ("MORTGAGE30US", "30-Year Fixed Mortgage Rate", "%", "Rates"),
    ("CPIAUCSL", "CPI — Consumer Price Index", "index", "Inflation"),
    ("CPILFESL", "Core CPI (ex food & energy)", "index", "Inflation"),
    ("PCEPI", "PCE Price Index (Fed's gauge)", "index", "Inflation"),
    ("UNRATE", "Unemployment Rate", "%", "Jobs"),
    ("PAYEMS", "Nonfarm Payrolls (total jobs)", "thousands", "Jobs"),
    ("ICSA", "Initial Jobless Claims (weekly)", "count", "Jobs"),
    ("INDPRO", "Industrial Production Index", "index", "Growth"),
    ("RSAFS", "Retail Sales", "$ mil", "Growth"),
    ("UMCSENT", "Consumer Sentiment (U. Michigan)", "index", "Consumer"),
    ("PSAVERT", "Personal Saving Rate", "%", "Consumer"),
    ("HOUST", "Housing Starts", "thousands", "Housing"),
    ("SP500", "S&P 500 Index", "index", "Markets"),
    ("VIXCLS", "Volatility Index (VIX)", "index", "Markets"),
]

# Moody's corporate-bond yields — Moody's is the SOURCE; FRED redistributes free.
_MOODYS_SERIES = [
    ("DAAA", "Moody's Aaa Corporate Bond Yield", "%", "Credit"),
    ("DBAA", "Moody's Baa Corporate Bond Yield", "%", "Credit"),
    ("BAA10Y", "Moody's Baa Spread over 10-Yr Treasury", "%", "Credit"),
]


def _parse_date(s: Optional[str]) -> Optional[date]:
    """Parse the common date shapes these APIs return into a date."""
    if not s:
        return None
    s = str(s).strip()
    m = re.match(r"^(\d{4})-(\d{2})-(\d{2})", s)
    if m:
        try:
            return date(int(m[1]), int(m[2]), int(m[3]))
        except ValueError:
            return None
    m = re.match(r"^(\d{4})Q([1-4])$", s)          # BEA quarterly, e.g. 2026Q1
    if m:
        return date(int(m[1]), int(m[2]) * 3, 28)
    m = re.match(r"^(\d{4})M(\d{2})$", s)           # BEA monthly, e.g. 2026M07
    if m:
        return date(int(m[1]), int(m[2]), 28)
    m = re.match(r"^(\d{4})-(\d{2})$", s)
    if m:
        return date(int(m[1]), int(m[2]), 1)
    return None


def _num(v) -> Optional[float]:
    try:
        return float(str(v).replace(",", ""))
    except (TypeError, ValueError):
        return None


class FinanceIntel:
    """Scans verified sources for newly-released data and briefs on it."""

    # ---------------------------------------------------------------- fetchers
    async def _fred_items(self, client: httpx.AsyncClient, series, source_label: str) -> List[Dict]:
        """One item per series — its latest observation, with change vs prior.

        Series are fetched concurrently so the whole set finishes in ~one call's
        time (keeps the run well within free-tier request limits).
        """
        if not settings.fred_api_key:
            return []

        async def one(series_id, label, unit, category) -> Optional[Dict]:
            try:
                r = await client.get(
                    "https://api.stlouisfed.org/fred/series/observations",
                    params={
                        "series_id": series_id,
                        "api_key": settings.fred_api_key,
                        "file_type": "json",
                        "sort_order": "desc",
                        "limit": 6,
                    },
                )
                if r.status_code != 200:
                    return None
                obs = [o for o in r.json().get("observations", []) if o.get("value") not in (".", None, "")]
                if not obs:
                    return None
                latest = obs[0]
                prior = obs[1] if len(obs) > 1 else None
                cur, prev = _num(latest.get("value")), (_num(prior.get("value")) if prior else None)
                change = round(cur - prev, 4) if (cur is not None and prev is not None) else None
                return {
                    "key": f"fred:{series_id}:{latest.get('date')}",
                    "source": source_label, "category": category, "label": label,
                    "unit": unit, "date": latest.get("date"),
                    "value": latest.get("value"), "change_vs_prior": change,
                }
            except Exception as e:  # noqa: BLE001
                logger.debug(f"FRED {series_id} failed: {e}")
                return None

        results = await asyncio.gather(*(one(*s) for s in series))
        return [it for it in results if it]

    async def _treasury_items(self, client: httpx.AsyncClient) -> List[Dict]:
        items: List[Dict] = []
        base = "https://api.fiscaldata.treasury.gov/services/api/fiscal_service/"
        try:
            r = await client.get(base + "v2/accounting/od/debt_to_penny",
                                 params={"sort": "-record_date", "page[size]": "1", "format": "json"})
            if r.status_code == 200 and r.json().get("data"):
                row = r.json()["data"][0]
                items.append({
                    "key": f"treasury:debt:{row.get('record_date')}",
                    "source": "U.S. Treasury", "category": "Fiscal",
                    "label": "National Debt", "unit": "$", "date": row.get("record_date"),
                    "value": row.get("tot_pub_debt_out_amt"), "change_vs_prior": None,
                })
        except Exception as e:  # noqa: BLE001
            logger.debug(f"Treasury debt failed: {e}")
        try:
            r = await client.get(base + "v2/accounting/od/avg_interest_rates",
                                 params={"sort": "-record_date", "page[size]": "1", "format": "json"})
            if r.status_code == 200 and r.json().get("data"):
                row = r.json()["data"][0]
                items.append({
                    "key": f"treasury:avgrate:{row.get('record_date')}",
                    "source": "U.S. Treasury", "category": "Fiscal",
                    "label": f"Avg interest rate on federal debt ({row.get('security_desc')})",
                    "unit": "%", "date": row.get("record_date"),
                    "value": row.get("avg_interest_rate_amt"), "change_vs_prior": None,
                })
        except Exception as e:  # noqa: BLE001
            logger.debug(f"Treasury rates failed: {e}")
        return items

    async def _fdic_items(self, client: httpx.AsyncClient) -> List[Dict]:
        items: List[Dict] = []
        try:
            r = await client.get("https://banks.data.fdic.gov/api/institutions",
                                 params={"filters": "ACTIVE:1", "fields": "NAME", "limit": "1", "format": "json"})
            if r.status_code == 200:
                total = ((r.json() or {}).get("meta") or {}).get("total")
                if total is not None:
                    items.append({
                        "key": f"fdic:institutions:{total}",
                        "source": "FDIC", "category": "Banking",
                        "label": "Active FDIC-insured institutions", "unit": "count",
                        "date": datetime.utcnow().strftime("%Y-%m-%d"),
                        "value": total, "change_vs_prior": None,
                    })
        except Exception as e:  # noqa: BLE001
            logger.debug(f"FDIC institutions failed: {e}")
        try:
            r = await client.get("https://banks.data.fdic.gov/api/failures",
                                 params={"fields": "NAME,PSTALP,FAILDATE,COST", "sort_by": "FAILDATE",
                                         "sort_order": "DESC", "limit": "5", "format": "json"})
            if r.status_code == 200:
                for row in (r.json() or {}).get("data", []) or []:
                    d = row.get("data") if isinstance(row.get("data"), dict) else row
                    fd = str(d.get("FAILDATE", ""))[:10]
                    items.append({
                        "key": f"fdic:failure:{d.get('NAME')}:{fd}",
                        "source": "FDIC", "category": "Banking",
                        "label": f"Bank failure: {d.get('NAME')} ({d.get('PSTALP')})",
                        "unit": "", "date": fd, "value": "failed", "change_vs_prior": None,
                    })
        except Exception as e:  # noqa: BLE001
            logger.debug(f"FDIC failures failed: {e}")
        return items

    async def _bea_items(self, client: httpx.AsyncClient) -> List[Dict]:
        if not settings.bea_api_key:
            return []
        try:
            years = ",".join(str(datetime.utcnow().year - i) for i in range(0, 2))
            r = await client.get("https://apps.bea.gov/api/data", params={
                "UserID": settings.bea_api_key, "method": "GetData", "datasetname": "NIPA",
                "TableName": "T10101", "Frequency": "Q", "Year": years, "ResultFormat": "JSON"})
            if r.status_code != 200:
                return []
            results = ((r.json() or {}).get("BEAAPI") or {}).get("Results") or {}
            rows = results.get("Data") if isinstance(results, dict) else (
                results[0].get("Data") if isinstance(results, list) and results else None)
            gdp = [d for d in (rows or []) if str(d.get("LineNumber")) == "1"]
            if not gdp:
                return []
            latest = sorted(gdp, key=lambda d: str(d.get("TimePeriod")))[-1]
            return [{
                "key": f"bea:gdp:{latest.get('TimePeriod')}",
                "source": "U.S. Bureau of Economic Analysis (BEA)", "category": "Growth",
                "label": "Real GDP growth (annualized, % change)", "unit": "%",
                "date": latest.get("TimePeriod"), "value": latest.get("DataValue"),
                "change_vs_prior": None,
            }]
        except Exception as e:  # noqa: BLE001
            logger.debug(f"BEA failed: {e}")
            return []

    # ------------------------------------------------------------ gather + filter
    async def _gather_all(self) -> List[Dict]:
        async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT) as client:
            # All sources concurrently — the run takes ~one slow call, not the sum.
            fred, moodys, bea, treasury, fdic = await asyncio.gather(
                self._fred_items(client, _FRED_SERIES, "FRED (Federal Reserve)"),
                self._fred_items(client, _MOODYS_SERIES, "Moody's"),
                self._bea_items(client),
                self._treasury_items(client),
                self._fdic_items(client),
            )
            return fred + moodys + bea + treasury + fdic

    def _filter_new(self, items: List[Dict], seen: Dict[str, str], since: date) -> List[Dict]:
        """Keep only items within the lookback window that we haven't reported."""
        fresh: List[Dict] = []
        for it in items:
            d = _parse_date(it.get("date"))
            if d is None or d < since:      # 2-month barrier — never reach past it
                continue
            if it["key"] in seen:           # already informed — no repeats
                continue
            fresh.append(it)
        return fresh

    # ---------------------------------------------------------------- synthesis
    def _news_system_prompt(self) -> str:
        """News-led brief: real economic developments, stacked against the Master's world."""
        return (
            "You are ORELIUS, delivering the Master's daily U.S. economic intelligence, "
            "stacked against his life-insurance and retirement business.\n\n"
            "You have WEB SEARCH. Use it to find the LATEST verified economic developments "
            "(roughly the last two weeks) from reputable outlets and official agencies: Fed "
            "policy and rate decisions, inflation (CPI/PCE), jobs, GDP/growth, interest rates "
            "and yields, markets, credit conditions, and anything materially affecting life "
            "insurance, annuities, or retirement savings. You are ALSO given official numeric "
            "data below to corroborate and quantify what you find.\n\n"
            "HARD RULES:\n"
            "1. Base EVERY factual claim and figure on your web-search results (cite the outlet) "
            "or the official numeric data provided. NEVER invent a number or a development. If "
            "search surfaces nothing new, say the stretch was quiet — do not fabricate.\n"
            "2. Prefer primary/official sources (Federal Reserve, BLS, Treasury, BEA) and major "
            "financial press (Reuters, AP, WSJ, CNBC, Bloomberg).\n"
            "3. Plain English, for a sharp life-insurance professional — not an economist.\n\n"
            "STRUCTURE:\n"
            "• **What's Moving** — the 3–6 most important verified developments right now, one "
            "tight line each WITH its source outlet. Lead with what changed (Fed, inflation, "
            "jobs, rates, markets).\n"
            "• **Stacked Against Your World — Pros & Cons** — for the themes that moved, explain "
            "plainly how each could HELP or HURT, with explicit PROS and CONS for each of:\n"
            "   – Life insurance policies (whole/term/IUL) and the insurers behind them\n"
            "   – Annuities (fixed, indexed, income)\n"
            "   – Individuals' bank savings (savings, CDs, money-market)\n"
            "   – Employer/retirement accounts (401(k), IRA, pensions)\n"
            "Tie every point to a development or figure above. Use the IRS as a STANDING "
            "reference beacon (irs.gov) — §7702 tax-deferred build-up, §1035 exchanges, §7520 "
            "rate, 401(k)/IRA/RMD rules — to reinforce WHY it matters. Label IRS references as "
            "standing rules, never as freshly-pulled figures, and never invent an IRS dollar "
            "limit (state it qualitatively and note the Master can confirm at irs.gov).\n"
            "• **Bottom Line** — 2–4 tight sentences: what today's picture means for the Master "
            "and his clients, plainly.\n\n"
            "Address the reader as 'Master'."
        )

    def _system_prompt(self) -> str:
        return (
            "You are ORELIUS, delivering the Master's daily U.S. economic intelligence. "
            "You are given ONLY newly-released, verified figures from official sources "
            "(Federal Reserve/FRED, Moody's, BEA, U.S. Treasury, FDIC). You also hold the "
            "IRS (irs.gov) as a STANDING REFERENCE AUTHORITY — a beacon of official U.S. "
            "tax rules you use to corroborate and frame the data. The IRS is not a daily "
            "feed; treat its rules as standing reference, never as freshly-pulled figures. "
            "Everything in the data below is NEW since your last briefing.\n\n"
            "HARD RULES:\n"
            "1. Use ONLY the numbers provided. Never invent or estimate a figure.\n"
            "2. Cite each figure's source and date.\n"
            "3. Write in SIMPLE, plain terms a non-expert can follow. No jargon without "
            "a plain-English gloss.\n\n"
            "STRUCTURE:\n"
            "• **What's New Today** — the newly-released figures, grouped simply "
            "(rates, inflation, jobs, growth, credit, markets, banking, fiscal). One "
            "short line each, sourced + dated, with the change if given.\n"
            "• **Weigh-Ins — Pros & Cons** — for the themes that moved, explain in plain "
            "terms how this data could AFFECT or BENEFIT each of these, with explicit "
            "PROS and CONS for each:\n"
            "   – Life insurance policies (whole/term/IUL) and the insurers behind them\n"
            "   – Annuities (fixed, indexed, income)\n"
            "   – Individuals' bank savings (savings, CDs, money-market)\n"
            "   – Employer/retirement accounts (401(k), IRA, pensions)\n"
            "Tie every point to a figure above. Use the IRS as your corroborating beacon: "
            "cite the well-established IRS rules that support your read (§7702 tax-deferred "
            "build-up, §1035 exchanges, §7520 valuation rate, 401(k)/IRA contribution and "
            "RMD rules, tax-deferred growth) to reinforce WHY the data matters for each "
            "vehicle. Label every IRS reference as a standing rule at irs.gov. Never "
            "present an IRS figure as freshly pulled, and if unsure of an exact IRS dollar "
            "limit, state the rule qualitatively and note the Master can confirm the "
            "current figure at irs.gov — do not invent a number.\n"
            "• **Bottom Line** — 2–4 tight sentences in simple terms: what today's data "
            "means for the Master, plainly.\n\n"
            "Address the reader as 'Master'."
        )

    def _group_by_source(self, items: List[Dict]) -> Dict[str, list]:
        by_source: Dict[str, list] = {}
        for it in items:
            by_source.setdefault(it["source"], []).append({
                "metric": it["label"], "category": it["category"], "value": it["value"],
                "unit": it["unit"], "date": it["date"], "change_vs_prior": it["change_vs_prior"],
            })
        return by_source

    @staticmethod
    def _sources_footer(sources: List[Dict[str, str]]) -> str:
        if not sources:
            return ""
        cited = "; ".join(f"[{s.get('title') or s.get('url')}]({s.get('url')})" for s in sources[:8])
        return f"\n\n**Sources:** {cited}"

    async def _news_and_stack(self, numeric_payload: Dict, live: bool = False):
        """News-led synthesis via web search + the official numeric data as support."""
        import json as _json
        if live:
            intro = ("Search now for the LATEST verified U.S. economic developments and brief "
                     "the Master per your rules. Use the official numbers below to quantify.")
        else:
            intro = ("Search for the latest verified U.S. economic developments, then brief the "
                     "Master per your rules, weaving in the official numbers below as corroboration.")
        user_text = intro + "\n\nOfficial numeric data (may be empty):\n" + _json.dumps(numeric_payload, indent=2)
        return await claude_client.chat_with_web_search(
            user_text=user_text,
            system_prompt=self._news_system_prompt(),
            allowed_domains=list(getattr(settings, "finance_news_domains", []) or []),
            max_uses=int(getattr(settings, "web_search_max_uses", 5)),
            max_tokens=settings.oreilus_report_max_tokens,
        )

    async def _fallback_numeric_brief(self, by_source: Dict, fresh: List[Dict], lookback: int) -> str:
        """Data-only brief when web search is off/unavailable (never fabricates news)."""
        if not fresh:
            return (
                "Master, no newly-released verified figures have appeared across the tracked "
                f"official sources within the last {lookback} days that I haven't already "
                "briefed you on, and live news search is unavailable this cycle. Nothing to "
                "repeat — I will report the moment new data or news lands."
            )
        import json as _json
        user_msg = ("Here is TODAY'S newly-released verified data (already filtered to new "
                    "items only). Brief the Master per your rules:\n\n" + _json.dumps(by_source, indent=2))
        try:
            return await claude_client.chat(
                messages=[{"role": "user", "content": user_msg}],
                system_prompt=self._system_prompt(),
                stream=False,
                max_tokens=settings.oreilus_report_max_tokens,
            )
        except Exception as e:  # noqa: BLE001
            logger.error(f"finance numeric synthesis failed: {e}")
            return "Master, new data was retrieved but synthesis failed this cycle."

    async def generate_brief(self, db: AsyncSession) -> Dict:
        lookback = max(1, int(getattr(settings, "finance_lookback_days", 60)))
        since = (datetime.utcnow() - timedelta(days=lookback)).date()

        seen = await self._load_seen(db)
        try:
            items = await self._gather_all()
        except Exception as e:  # noqa: BLE001
            logger.error(f"finance gather failed: {e}")
            items = []

        # No-repeat still applies to the NUMERIC figures (so we never relist the same
        # ones); the NEWS narrative below is fresh every day via web search.
        fresh = self._filter_new(items, seen, since)
        by_source = self._group_by_source(fresh)

        data = {"as_of": datetime.utcnow().isoformat() + "Z", "lookback_days": lookback,
                "new_items": len(fresh), "sources": by_source,
                "reference_sources": ["IRS (irs.gov) — standing tax rules & limits, corroborating authority"]}

        brief = ""
        if getattr(settings, "web_search_enabled", True):
            try:
                brief, news_sources = await self._news_and_stack(by_source, live=False)
                if brief:
                    data["news_sources"] = news_sources[:20]
                    brief += self._sources_footer(news_sources)
            except Exception as e:  # noqa: BLE001
                logger.warning(f"finance web-search brief failed, using numeric fallback: {e}")
                brief = ""
        if not brief:
            brief = await self._fallback_numeric_brief(by_source, fresh, lookback)

        # Remember the numeric figures we surfaced, and prune past the barrier.
        import json as _json  # noqa: F401
        for it in fresh:
            seen[it["key"]] = it["date"] or datetime.utcnow().strftime("%Y-%m-%d")
        seen = {k: v for k, v in seen.items() if (_parse_date(v) or since) >= since}
        await self._save_seen(db, seen)

        await self._record(db, brief, data, ok=True)
        return {"ok": True, "summary": brief, "data": data}

    async def live_briefing(self) -> str:
        """On-demand economic-news briefing for chat — live, cited, never stale.

        Pulls a current numeric snapshot (no no-repeat filter — this is a live look,
        not the daily de-duped feed) and lets web search surface the real news.
        """
        try:
            items = await self._gather_all()
        except Exception as e:  # noqa: BLE001
            logger.debug(f"live briefing gather failed: {e}")
            items = []
        by_source = self._group_by_source(items)

        if getattr(settings, "web_search_enabled", True):
            try:
                text, sources = await self._news_and_stack(by_source, live=True)
                if text:
                    return text + self._sources_footer(sources)
            except Exception as e:  # noqa: BLE001
                logger.warning(f"live economic briefing failed: {e}")
        return ("Master, I could not retrieve live economic news this moment — the search "
                "service didn't respond. The official data feeds are still tracked; try me "
                "again shortly and I'll have the latest developments stacked for you.")

    # ---------------------------------------------------------------- persistence
    async def _load_seen(self, db: AsyncSession) -> Dict[str, str]:
        try:
            from ..models.automation_state import AutomationState
            row = (await db.execute(
                select(AutomationState).where(AutomationState.key == _SEEN_KEY)
            )).scalars().first()
            if row and isinstance(row.data, dict):
                return dict(row.data.get("keys", {}))
        except Exception as e:  # noqa: BLE001
            logger.debug(f"load seen failed: {e}")
        return {}

    async def _save_seen(self, db: AsyncSession, seen: Dict[str, str]) -> None:
        try:
            from ..models.automation_state import AutomationState
            row = (await db.execute(
                select(AutomationState).where(AutomationState.key == _SEEN_KEY)
            )).scalars().first()
            if row:
                row.data = {"keys": seen}
            else:
                db.add(AutomationState(key=_SEEN_KEY, data={"keys": seen}))
            await db.flush()
        except Exception as e:  # noqa: BLE001
            logger.debug(f"save seen failed: {e}")

    async def _record(self, db: AsyncSession, summary: str, data: Dict, ok: bool) -> None:
        try:
            from ..models.report import Report, ReportType
            report = Report(
                title=f"Daily Economic Intelligence — {datetime.utcnow():%Y-%m-%d}",
                report_type=ReportType.BANKING_INTELLIGENCE,
                report_date=datetime.utcnow(),
                content=data,
                summary=summary,
            )
            db.add(report)
            await db.flush()
        except Exception as e:  # noqa: BLE001
            logger.debug(f"finance report persist skipped: {e}")
        try:
            await shared_memory.remember(
                db, content=summary[:4000], kind="finance_brief", actor="ORELIUS",
                meta={"ok": ok, "new_items": data.get("new_items"),
                      "sources": list((data.get("sources") or {}).keys())},
            )
        except Exception as e:  # noqa: BLE001
            logger.debug(f"finance shared-memory write skipped: {e}")


# Global instance
finance_intel = FinanceIntel()
