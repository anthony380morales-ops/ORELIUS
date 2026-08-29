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

    async def _fdic_failures(self, client: httpx.AsyncClient) -> List[Dict]:
        """Most recent FDIC bank failures (systemic-health signal)."""
        try:
            r = await client.get(
                "https://banks.data.fdic.gov/api/failures",
                params={
                    "fields": "NAME,CITYST,FAILDATE,COST,RESTYPE",
                    "sort_by": "FAILDATE",
                    "sort_order": "DESC",
                    "limit": "3",
                    "format": "json",
                },
            )
            if r.status_code == 200:
                return [d.get("data", d) for d in r.json().get("data", [])]
        except Exception as e:  # noqa: BLE001
            logger.debug(f"FDIC failures fetch failed: {e}")
        return []

    async def gather_data(self) -> Dict:
        """Collect all verified figures into one structured payload."""
        data: Dict = {"as_of": datetime.utcnow().isoformat() + "Z", "sources": {}}
        async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT) as client:
            fred: Dict = {}
            for series_id, label, unit in _FRED_SERIES:
                obs = await self._fred_series(client, series_id)
                if obs:
                    fred[series_id] = {"label": label, "unit": unit, **obs}
            if fred:
                data["sources"]["FRED (Federal Reserve, St. Louis)"] = fred
            treasury = await self._treasury(client)
            if treasury:
                data["sources"]["U.S. Treasury (Fiscal Data)"] = treasury
            fdic = await self._fdic_failures(client)
            if fdic:
                data["sources"]["FDIC"] = {"recent_bank_failures": fdic}
        return data

    # ---------------------------------------------------------------- synthesis
    def _system_prompt(self) -> str:
        return (
            "You are ORELIUS, delivering the Master's daily U.S. financial "
            "intelligence briefing. You will be given ONLY verified figures pulled "
            "live from official government sources (Federal Reserve/FRED, U.S. "
            "Treasury, FDIC). Rules, without exception:\n"
            "1. Use ONLY the numbers provided below. Never invent, estimate, or add "
            "any figure that is not in the data.\n"
            "2. For every number you cite, name its source (FRED, U.S. Treasury, or "
            "FDIC) and its date.\n"
            "3. Where a prior value is given, note the change (up/down) plainly.\n"
            "4. If the data is thin, say so — do not pad with speculation.\n"
            "5. Be concise and factual: a short 'Key Rates' section, a 'Fiscal & "
            "Banking' section, and a 2-3 sentence 'What it means' read-out that only "
            "interprets the given numbers.\n"
            "Address the reader as 'Master'."
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
