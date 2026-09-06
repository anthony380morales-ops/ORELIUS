"""
O.R.E.L.I.U.S. Daily Financial Intelligence
-------------------------------------------
Pulls hard numbers from OFFICIAL, verified U.S. government sources, then has the
ORELIUS Haiku brain synthesize a factual daily briefing grounded ONLY in those
numbers (no speculation, every figure sourced). Runs on demand or on a daily
schedule (8:00 AM PST) via /api/automation/finance-brief.

Sources (authoritative, primary):
  * FRED  — Federal Reserve Bank of St. Louis (needs a free FRED_API_KEY)
  * U.S. Treasury Fiscal Data — api.fiscaldata.treasury.gov (no key)
  * FDIC  — banks.data.fdic.gov (no key)

Everything is best-effort: a source that fails is simply omitted, and the brief
is written from whatever verified data was retrieved.
"""
from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Optional

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..utils.logger import logger
from .claude_client import claude_client
from .shared_memory import shared_memory

# FRED series we track (id -> human label + unit hint).
_FRED_SERIES = [
    ("FEDFUNDS", "Federal Funds Rate", "%"),
    ("DGS10", "10-Year Treasury Yield", "%"),
    ("T10Y2Y", "10Y-2Y Treasury Spread (yield curve)", "%"),
    ("UNRATE", "Unemployment Rate", "%"),
    ("CPIAUCSL", "CPI (Consumer Price Index, level)", "index"),
    ("MORTGAGE30US", "30-Year Fixed Mortgage Rate", "%"),
]

# Moody's corporate-bond yields — Moody's is the SOURCE; FRED redistributes them
# free. Central to life-insurance analysis (insurers hold huge corporate-bond
# books; credit spreads drive investment income and risk).
_MOODYS_SERIES = [
    ("DAAA", "Moody's Seasoned Aaa Corporate Bond Yield", "%"),
    ("DBAA", "Moody's Seasoned Baa Corporate Bond Yield", "%"),
    ("BAA10Y", "Moody's Baa Corporate Bond Spread over 10-Yr Treasury", "%"),
]

_HTTP_TIMEOUT = 20.0


class FinanceIntel:
    """Gathers verified financial data and produces a grounded daily briefing."""

    # ---------------------------------------------------------------- fetchers
    async def _fred_series(self, client: httpx.AsyncClient, series_id: str) -> Optional[Dict]:
        """Latest two observations for a FRED series (value + prior, for a delta)."""
        if not settings.fred_api_key:
            return None
        try:
            r = await client.get(
                "https://api.stlouisfed.org/fred/series/observations",
                params={
                    "series_id": series_id,
                    "api_key": settings.fred_api_key,
                    "file_type": "json",
                    "sort_order": "desc",
                    "limit": 2,
                },
            )
            if r.status_code != 200:
                logger.debug(f"FRED {series_id} -> {r.status_code}")
                return None
            obs = [o for o in r.json().get("observations", []) if o.get("value") not in (".", None)]
            if not obs:
                return None
            latest = obs[0]
            prior = obs[1] if len(obs) > 1 else None
            out = {"date": latest.get("date"), "value": latest.get("value")}
            if prior:
                out["prior_value"] = prior.get("value")
                out["prior_date"] = prior.get("date")
            return out
        except Exception as e:  # noqa: BLE001
            logger.debug(f"FRED {series_id} fetch failed: {e}")
            return None

    async def _treasury(self, client: httpx.AsyncClient) -> Dict:
        """U.S. Treasury Fiscal Data: national debt + average interest rate."""
        out: Dict = {}
        try:
            r = await client.get(
                "https://api.fiscaldata.treasury.gov/services/api/fiscal_service/"
                "v2/accounting/od/debt_to_penny",
                params={"sort": "-record_date", "page[size]": "1", "format": "json"},
            )
            if r.status_code == 200:
                rows = r.json().get("data", [])
                if rows:
                    out["national_debt"] = {
                        "date": rows[0].get("record_date"),
                        "total_debt_usd": rows[0].get("tot_pub_debt_out_amt"),
                    }
        except Exception as e:  # noqa: BLE001
            logger.debug(f"Treasury debt fetch failed: {e}")
        try:
            r = await client.get(
                "https://api.fiscaldata.treasury.gov/services/api/fiscal_service/"
                "v2/accounting/od/avg_interest_rates",
                params={"sort": "-record_date", "page[size]": "1", "format": "json"},
            )
            if r.status_code == 200:
                rows = r.json().get("data", [])
                if rows:
                    out["avg_interest_rate"] = {
                        "date": rows[0].get("record_date"),
                        "security": rows[0].get("security_desc"),
                        "avg_rate_pct": rows[0].get("avg_interest_rate_amt"),
                    }
        except Exception as e:  # noqa: BLE001
            logger.debug(f"Treasury rates fetch failed: {e}")
        return out

    async def _fdic(self, client: httpx.AsyncClient) -> Dict:
        """FDIC banking-health signals: active-institution count + recent failures.

        Uses the BankFind Suite API (no key). The institutions count is reliably
        populated; failures are sparse (few per year) so they may be empty.
        """
        out: Dict = {}

        # Active FDIC-insured institutions (industry footprint) — meta.total.
        try:
            r = await client.get(
                "https://banks.data.fdic.gov/api/institutions",
                params={"filters": "ACTIVE:1", "fields": "NAME", "limit": "1", "format": "json"},
            )
            if r.status_code == 200:
                total = ((r.json() or {}).get("meta") or {}).get("total")
                if total is not None:
                    out["active_insured_institutions"] = total
            else:
                logger.debug(f"FDIC institutions -> {r.status_code}")
        except Exception as e:  # noqa: BLE001
            logger.debug(f"FDIC institutions fetch failed: {e}")

        # Most recent bank failures (year-to-date signal).
        try:
            r = await client.get(
                "https://banks.data.fdic.gov/api/failures",
                params={
                    "fields": "NAME,PSTALP,FAILDATE,COST,RESTYPE",
                    "sort_by": "FAILDATE",
                    "sort_order": "DESC",
                    "limit": "3",
                    "format": "json",
                },
            )
            if r.status_code == 200:
                rows = (r.json() or {}).get("data", []) or []
                failures = [(row.get("data") if isinstance(row.get("data"), dict) else row) for row in rows]
                out["recent_bank_failures"] = failures
            else:
                logger.debug(f"FDIC failures -> {r.status_code}")
        except Exception as e:  # noqa: BLE001
            logger.debug(f"FDIC failures fetch failed: {e}")

        return out

    async def _bea(self, client: httpx.AsyncClient) -> Dict:
        """U.S. Bureau of Economic Analysis (BEA) — real GDP growth. Needs BEA_API_KEY."""
        if not settings.bea_api_key:
            return {}
        try:
            years = ",".join(str(datetime.utcnow().year - i) for i in range(0, 2))
            r = await client.get(
                "https://apps.bea.gov/api/data",
                params={
                    "UserID": settings.bea_api_key,
                    "method": "GetData",
                    "datasetname": "NIPA",
                    "TableName": "T10101",  # percent change from preceding period, real GDP
                    "Frequency": "Q",
                    "Year": years,
                    "ResultFormat": "JSON",
                },
            )
            if r.status_code != 200:
                logger.debug(f"BEA -> {r.status_code}")
                return {}
            results = ((r.json() or {}).get("BEAAPI") or {}).get("Results") or {}
            rows = results.get("Data") if isinstance(results, dict) else None
            if not rows and isinstance(results, list) and results:
                rows = results[0].get("Data")
            if not rows:
                return {}
            # Line 1 = Gross domestic product; take the latest quarter present.
            gdp_rows = [d for d in rows if str(d.get("LineNumber")) == "1"]
            if not gdp_rows:
                return {}
            latest = sorted(gdp_rows, key=lambda d: str(d.get("TimePeriod")))[-1]
            return {
                "real_gdp_growth": {
                    "period": latest.get("TimePeriod"),
                    "pct_change_annualized": latest.get("DataValue"),
                    "measure": latest.get("LineDescription") or "Real GDP, % change (annualized)",
                }
            }
        except Exception as e:  # noqa: BLE001
            logger.debug(f"BEA fetch failed: {e}")
            return {}

    async def gather_data(self) -> Dict:
        """Collect all verified figures into one structured payload."""
        data: Dict = {"as_of": datetime.utcnow().isoformat() + "Z", "sources": {}}
        async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT) as client:
            # FRED — core macro (rates, inflation, jobs, mortgages)
            fred: Dict = {}
            for series_id, label, unit in _FRED_SERIES:
                obs = await self._fred_series(client, series_id)
                if obs:
                    fred[series_id] = {"label": label, "unit": unit, **obs}
            if fred:
                data["sources"]["FRED (Federal Reserve, St. Louis)"] = fred

            # Moody's — corporate bond yields / credit spreads (via FRED redistribution)
            moodys: Dict = {}
            for series_id, label, unit in _MOODYS_SERIES:
                obs = await self._fred_series(client, series_id)
                if obs:
                    moodys[series_id] = {"label": label, "unit": unit, **obs}
            if moodys:
                data["sources"]["Moody's (corporate bond yields)"] = moodys

            # BEA — output/growth
            bea = await self._bea(client)
            if bea:
                data["sources"]["U.S. Bureau of Economic Analysis (BEA)"] = bea

            # U.S. Treasury — fiscal
            treasury = await self._treasury(client)
            if treasury:
                data["sources"]["U.S. Treasury (Fiscal Data)"] = treasury

            # FDIC — banking health
            fdic = await self._fdic(client)
            if fdic:
                data["sources"]["FDIC"] = fdic
        return data

    # ---------------------------------------------------------------- synthesis
    def _system_prompt(self) -> str:
        return (
            "You are ORELIUS, delivering the Master's daily U.S. economic "
            "intelligence briefing, focused through the lens of the LIFE INSURANCE "
            "industry. You are given ONLY verified figures pulled live from official "
            "sources: Federal Reserve/FRED, Moody's (corporate bond yields), U.S. "
            "Bureau of Economic Analysis (BEA), U.S. Treasury, and FDIC.\n\n"
            "HARD RULES (never break):\n"
            "1. Use ONLY the numbers provided in the data below. Never invent, "
            "estimate, or add any figure not present.\n"
            "2. For every number, name its source (FRED, Moody's, BEA, Treasury, or "
            "FDIC) and its date.\n"
            "3. Where a prior value is given, state the change (up/down) plainly.\n"
            "4. If a source is missing, say so — never fabricate to fill a gap.\n\n"
            "YOUR JOB — gather, then compress into a cohesive understanding. Structure:\n"
            "• **Economy Snapshot** — the key verified figures (rates, credit spreads, "
            "growth, jobs, inflation, fiscal, banking), each sourced and dated.\n"
            "• **Life-Insurance Read** — stack that economy against the U.S. life "
            "insurance business: how these exact numbers affect insurers' investment "
            "income and bond portfolios (Moody's Aaa/Baa yields and spreads, 10-Yr "
            "Treasury), product pricing and crediting rates, annuity/IUL demand, "
            "credit and reinvestment risk, and capital. Tie each point to a figure "
            "above. Factor in standing U.S. tax treatment where relevant (IRS rules "
            "you already know — e.g. §7702 definition of life insurance and tax-"
            "deferred inside build-up, §1035 exchanges, §7702B for LTC riders, the "
            "§7520 valuation rate). Label these clearly as standing tax rules, not "
            "live figures.\n"
            "• **Cohesive Summary** — 2-4 tight sentences condensing everything into "
            "one clear read for the Master: what today's data means for the life "
            "insurance opportunity, stated plainly.\n\n"
            "Be disciplined and concise. Address the reader as 'Master'."
        )

    async def generate_brief(self, db: AsyncSession) -> Dict:
        """Fetch data, synthesize the grounded briefing, persist it, return it."""
        data = await self.gather_data()

        if not data.get("sources"):
            msg = (
                "Master, I could not retrieve any verified financial data this cycle "
                "(all official sources were unreachable or no FRED key is set). No "
                "briefing was fabricated. I will retry on the next run."
            )
            await self._record(db, msg, data, ok=False)
            return {"ok": False, "summary": msg, "data": data}

        import json as _json
        user_msg = (
            "Here is today's verified data. Write the daily financial intelligence "
            "briefing using ONLY these figures, citing source + date for each:\n\n"
            + _json.dumps(data["sources"], indent=2)
        )
        try:
            brief = await claude_client.chat(
                messages=[{"role": "user", "content": user_msg}],
                system_prompt=self._system_prompt(),
                stream=False,
                max_tokens=settings.oreilus_report_max_tokens,
            )
        except Exception as e:  # noqa: BLE001
            logger.error(f"finance brief synthesis failed: {e}")
            brief = "Master, verified data was retrieved but synthesis failed this cycle."

        await self._record(db, brief, data, ok=True)
        return {"ok": True, "summary": brief, "data": data}

    async def _record(self, db: AsyncSession, summary: str, data: Dict, ok: bool) -> None:
        """Persist the briefing as a Report and push it into shared memory."""
        # Store a Report row (durable, dashboard-readable).
        try:
            from ..models.report import Report, ReportType
            report = Report(
                title=f"Daily Financial Intelligence — {datetime.utcnow():%Y-%m-%d}",
                report_type=ReportType.BANKING_INTELLIGENCE,
                report_date=datetime.utcnow(),
                content=data,
                summary=summary,
            )
            db.add(report)
            await db.flush()
        except Exception as e:  # noqa: BLE001 - never let persistence break the run
            logger.debug(f"finance report persist skipped: {e}")

        # Push into shared memory so it surfaces in ORELIUS chat + LUCIUS/ATHENA.
        try:
            await shared_memory.remember(
                db,
                content=summary[:4000],
                kind="finance_brief",
                actor="ORELIUS",
                meta={"ok": ok, "sources": list(data.get("sources", {}).keys())},
            )
        except Exception as e:  # noqa: BLE001
            logger.debug(f"finance brief shared-memory write skipped: {e}")


# Global instance
finance_intel = FinanceIntel()
