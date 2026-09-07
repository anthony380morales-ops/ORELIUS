"""
O.R.E.L.I.U.S. — NXG Life Group funnel intelligence
---------------------------------------------------
Every morning ORELIUS analyzes the NXG Life Group site (the "Life Funnel", hosted
on Netlify) and briefs the Master on:

  • LEADS — every new lead captured since the last briefing, pulled straight from
    the same Supabase project the private admin dashboard reads. If there are no
    new leads (or none at all), it says so plainly, and still gives the standing
    pipeline snapshot.
  • TRAFFIC — how many people and what devices visited the site, from a lightweight
    `page_views` table in the same Supabase project (with an optional Netlify
    Analytics fallback). If no traffic source is connected yet, it says exactly
    that and how to turn it on — it never fabricates numbers.

This is a SEPARATE automation from the daily Financial Intelligence engine and the
conversational personality layer. It has its own data sources, its own system
prompt, and its own durable state. Verified data only — every figure comes from a
real Supabase/Netlify row; ORELIUS never invents a lead or a visitor count.

Runs daily at 8 AM PST via the same external cron that runs the finance brief,
hitting POST /api/automation/nxg-brief.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..utils.logger import logger
from .claude_client import claude_client
from .shared_memory import shared_memory
from ..models.automation_state import AutomationState  # noqa: F401  (register table)

try:
    from zoneinfo import ZoneInfo
    _PACIFIC = ZoneInfo("America/Los_Angeles")
except Exception:  # noqa: BLE001 - fallback if tzdata missing
    _PACIFIC = timezone(timedelta(hours=-8))

_HTTP_TIMEOUT = 20.0
_STATE_KEY = "nxg_state"

# Columns pulled for a full lead detail line (the private dashboard's fields).
_LEAD_DETAIL_COLS = (
    "id,created_at,first_name,last_name,email,phone,primary_concern,primary_concern_label,"
    "pipeline_stage,call_status,call_outcome,tags"
)

# Speakable version of each quiz "primary concern" — the lead's critical savings
# point. Mirrors the labels the funnel itself uses (trigger-retell-call.mjs), so
# ORELIUS can fill one in even when the stored label is blank.
_CONCERN_LABELS = {
    "taxes": "being tax-smart with your money",
    "retirement_income": "reliable retirement income",
    "protect_family": "protecting your family",
    "grow_safely": "growing your money safely",
    "legacy": "leaving a legacy for your loved ones",
}


def _concern_of(row: Dict) -> str:
    """The lead's critical savings point, plain-English, with sensible fallbacks."""
    label = (row.get("primary_concern_label") or "").strip()
    if label:
        return label
    code = (row.get("primary_concern") or "").strip()
    if code:
        return _CONCERN_LABELS.get(code, code.replace("_", " "))
    return "not specified in the quiz"


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _pt_day_start(now_utc: datetime) -> datetime:
    """Start of *today* in Pacific time, returned as a UTC datetime."""
    now_pt = now_utc.astimezone(_PACIFIC)
    midnight_pt = now_pt.replace(hour=0, minute=0, second=0, microsecond=0)
    return midnight_pt.astimezone(timezone.utc)


class NXGIntel:
    """Reads the NXG funnel's Supabase (leads + page_views) and briefs the Master."""

    # ----------------------------------------------------------- supabase helpers
    def _supa_ready(self) -> bool:
        return bool(settings.nxg_supabase_url and settings.nxg_supabase_service_key)

    def _supa_headers(self) -> Dict[str, str]:
        key = settings.nxg_supabase_service_key
        return {"apikey": key, "Authorization": f"Bearer {key}", "Accept": "application/json"}

    async def _supa_select(
        self, client: httpx.AsyncClient, table: str, query: str
    ) -> Tuple[Optional[List[Dict]], Optional[str]]:
        """GET rows from a Supabase table. Returns (rows, error). A missing table
        (PostgREST 404/relation error) comes back as (None, 'missing')."""
        url = f"{settings.nxg_supabase_url.rstrip('/')}/rest/v1/{table}?{query}"
        try:
            r = await client.get(url, headers=self._supa_headers())
        except Exception as e:  # noqa: BLE001
            logger.debug(f"supabase {table} request failed: {e}")
            return None, "request_failed"
        if r.status_code == 200:
            try:
                data = r.json()
                return (data if isinstance(data, list) else []), None
            except Exception:  # noqa: BLE001
                return [], None
        if r.status_code == 404 or (r.status_code == 400 and "does not exist" in r.text.lower()):
            return None, "missing"
        logger.debug(f"supabase {table} -> {r.status_code}: {r.text[:200]}")
        return None, f"http_{r.status_code}"

    # ----------------------------------------------------------------- leads
    async def _fetch_leads(
        self, client: httpx.AsyncClient, since: datetime
    ) -> Dict:
        """New leads since `since` + all-time totals, today's count, and pipeline mix."""
        out: Dict = {"available": False, "new": [], "total": 0, "today": 0,
                     "pipeline": {}, "error": None}

        # New leads (full detail) since the last briefing.
        new_rows, err = await self._supa_select(
            client, "leads",
            f"select={_LEAD_DETAIL_COLS}&created_at=gte.{since.strftime('%Y-%m-%dT%H:%M:%SZ')}"
            "&order=created_at.desc&limit=200",
        )
        if err == "missing":
            out["error"] = "no_leads_table"
            return out
        if new_rows is None:
            out["error"] = err or "unavailable"
            return out
        out["available"] = True
        out["new"] = new_rows

        # Slim pull of every lead for totals + pipeline breakdown (funnel volume is small).
        all_rows, _ = await self._supa_select(
            client, "leads", "select=id,created_at,pipeline_stage&limit=10000",
        )
        all_rows = all_rows or []
        out["total"] = len(all_rows)
        day_start = _pt_day_start(datetime.now(timezone.utc)).strftime("%Y-%m-%dT%H:%M:%SZ")
        pipeline: Dict[str, int] = {}
        today = 0
        for row in all_rows:
            stage = (row.get("pipeline_stage") or "unknown")
            pipeline[stage] = pipeline.get(stage, 0) + 1
            if str(row.get("created_at") or "") >= day_start:
                today += 1
        out["pipeline"] = pipeline
        out["today"] = today
        return out

    # ------------------------------------------------- on-demand live lookup
    async def recent_leads(self, db: AsyncSession, limit: int = 15) -> Dict:
        """Live Supabase lookup for the chat command 'give me the new leads'.

        Returns the newest leads with just what the Master needs on a call — the
        name and their critical savings point (quiz concern) — plus a recency flag
        so brand-new leads stand out. Queried live every time, so a lead that just
        came in shows immediately (no stale automation cache).
        """
        if not self._supa_ready():
            return {"ok": False, "reason": "unconfigured"}
        async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT) as client:
            rows, err = await self._supa_select(
                client, "leads",
                f"select={_LEAD_DETAIL_COLS}&order=created_at.desc&limit={int(limit)}",
            )
        if rows is None:
            return {"ok": False, "reason": err or "unavailable"}

        cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
        leads: List[Dict] = []
        stages: Dict[str, int] = {}
        for r in rows:
            name = " ".join(x for x in [r.get("first_name"), r.get("last_name")] if x) or "(no name given)"
            created = self._parse_dt(r.get("created_at"))
            stage = r.get("pipeline_stage") or "new"
            stages[stage] = stages.get(stage, 0) + 1
            leads.append({
                "name": name,
                "concern": _concern_of(r),
                "stage": stage,
                "created_at": r.get("created_at"),
                "is_new": bool(created and created >= cutoff),
            })
        return {"ok": True, "leads": leads, "stages": stages}

    # --------------------------------------------------------------- traffic
    async def _fetch_traffic(self, client: httpx.AsyncClient, since: datetime) -> Dict:
        """Visitors + devices from the page_views table (or Netlify fallback)."""
        since_iso = since.strftime("%Y-%m-%dT%H:%M:%SZ")
        rows, err = await self._supa_select(
            client, "page_views",
            f"select=visitor_hash,device,path,created_at&created_at=gte.{since_iso}&limit=100000",
        )
        if rows is not None:
            people = {r.get("visitor_hash") for r in rows if r.get("visitor_hash")}
            devices: Dict[str, int] = {}
            pages: Dict[str, int] = {}
            for r in rows:
                dev = (r.get("device") or "unknown")
                devices[dev] = devices.get(dev, 0) + 1
                p = (r.get("path") or "/")
                pages[p] = pages.get(p, 0) + 1
            top_pages = sorted(pages.items(), key=lambda kv: kv[1], reverse=True)[:5]
            return {"available": True, "source": "supabase_page_views",
                    "views": len(rows), "people": len(people), "devices": devices,
                    "top_pages": [{"path": p, "views": v} for p, v in top_pages]}

        if err == "missing":
            # No tracker yet — try Netlify Analytics if configured, else report clearly.
            netlify = await self._fetch_netlify(client)
            if netlify is not None:
                return netlify
            return {"available": False, "source": None, "reason": "no_page_views_table"}

        netlify = await self._fetch_netlify(client)
        if netlify is not None:
            return netlify
        return {"available": False, "source": None, "reason": err or "unavailable"}

    async def _fetch_netlify(self, client: httpx.AsyncClient) -> Optional[Dict]:
        """Best-effort Netlify Analytics (paid add-on; undocumented API)."""
        if not (settings.netlify_api_token and settings.netlify_site_id):
            return None
        try:
            now = datetime.now(timezone.utc)
            frm = int((now - timedelta(days=1)).timestamp() * 1000)
            to = int(now.timestamp() * 1000)
            base = f"https://analytics.services.netlify.com/v2/{settings.netlify_site_id}"
            headers = {"Authorization": f"Bearer {settings.netlify_api_token}"}
            r = await client.get(f"{base}/pages", headers=headers,
                                 params={"from": frm, "to": to, "timezone": "-08:00"})
            if r.status_code != 200:
                return None
            data = r.json() if r.content else {}
            views = data.get("total") or sum(d.get("count", 0) for d in data.get("data", []) or [])
            rv = await client.get(f"{base}/ranking/pages", headers=headers,
                                  params={"from": frm, "to": to})
            visitors = None
            try:
                vr = await client.get(f"{base}/visitors", headers=headers,
                                     params={"from": frm, "to": to})
                if vr.status_code == 200:
                    vd = vr.json()
                    visitors = vd.get("total") if isinstance(vd, dict) else None
            except Exception:  # noqa: BLE001
                pass
            return {"available": True, "source": "netlify_analytics",
                    "views": views, "people": visitors, "devices": {},
                    "top_pages": [], "note": "Netlify Analytics gives no device breakdown."}
        except Exception as e:  # noqa: BLE001
            logger.debug(f"netlify analytics failed: {e}")
            return None

    # --------------------------------------------------------------- synthesis
    def _system_prompt(self) -> str:
        return (
            "You are ORELIUS, delivering the Master's daily NXG Life Group funnel "
            "briefing. You are given ONLY real data pulled from the site's own "
            "systems (Supabase leads the admin dashboard reads, and a page_views "
            "table / Netlify analytics for traffic). Everything is factual — never "
            "invent a lead, a name, a number, or a visitor count.\n\n"
            "HARD RULES:\n"
            "1. Use ONLY the data provided. If a section says it's unavailable, report "
            "that plainly and do NOT make up numbers.\n"
            "2. Lead names/emails/phones are the Master's own business data — present "
            "them directly and cleanly.\n"
            "3. Plain, confident, brief. This is a morning stand-up, not an essay.\n\n"
            "STRUCTURE:\n"
            "• **New Leads** — if there are new leads since yesterday, list each: name, "
            "the concern they came in for, pipeline stage / call outcome, and when. If "
            "there are none, say so in one clear line (e.g. 'No new leads since "
            "yesterday.').\n"
            "• **Pipeline Snapshot** — total leads and the breakdown by stage, so the "
            "Master sees the whole board at a glance.\n"
            "• **Traffic** — how many people visited and the device breakdown (e.g. "
            "mobile vs desktop), plus total page views and top pages if given. If "
            "traffic tracking isn't connected yet, say exactly that in one line.\n"
            "• **Read** — 1–3 tight sentences: what today's numbers mean and the one "
            "thing worth the Master's attention (a hot lead to call, a traffic spike, "
            "or a quiet day).\n\n"
            "Address the reader as 'Master'."
        )

    async def generate_brief(self, db: AsyncSession) -> Dict:
        now = datetime.now(timezone.utc)

        if not self._supa_ready():
            msg = (
                "Master, the NXG funnel briefing isn't fully wired yet: the Supabase "
                "service key for the Life Funnel project isn't set. Add "
                "NXG_SUPABASE_SERVICE_KEY (and confirm NXG_SUPABASE_URL) in Render → "
                "Environment and I'll begin the daily 8 AM briefing."
            )
            await self._record(db, msg, {"as_of": _iso(now), "configured": False}, ok=False)
            return {"ok": False, "summary": msg, "data": {"configured": False}}

        state = await self._load_state(db)
        last_run = self._parse_dt(state.get("last_run_at")) or (now - timedelta(days=1))
        seen_ids = set(state.get("seen_lead_ids") or [])

        async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT) as client:
            leads = await self._fetch_leads(client, last_run)
            traffic = await self._fetch_traffic(client, _pt_day_start(now))

        # No-repeat: drop any "new" lead already reported in a prior run.
        if leads.get("available"):
            leads["new"] = [l for l in leads["new"] if l.get("id") not in seen_ids]

        data = {
            "as_of": _iso(now),
            "window_since": _iso(last_run),
            "leads": leads,
            "traffic": traffic,
        }

        summary = await self._synthesize(data)

        # Persist state: advance the window and remember reported lead ids (bounded).
        new_ids = [l.get("id") for l in (leads.get("new") or []) if l.get("id")]
        merged = (new_ids + list(seen_ids))[:500]
        await self._save_state(db, {"last_run_at": _iso(now), "seen_lead_ids": merged})

        await self._record(db, summary, data, ok=True)
        return {"ok": True, "summary": summary, "data": data}

    async def _synthesize(self, data: Dict) -> str:
        import json as _json
        user_msg = (
            "Here is today's NXG Life Group funnel data (already filtered — leads under "
            "'leads.new' are new since the last briefing). Brief the Master per your "
            "rules:\n\n" + _json.dumps(data, indent=2, default=str)
        )
        try:
            return await claude_client.chat(
                messages=[{"role": "user", "content": user_msg}],
                system_prompt=self._system_prompt(),
                stream=False,
                max_tokens=settings.oreilus_report_max_tokens,
            )
        except Exception as e:  # noqa: BLE001
            logger.error(f"NXG synthesis failed: {e}")
            # Deterministic fallback so the Master still gets the facts.
            return self._plain_fallback(data)

    def _plain_fallback(self, data: Dict) -> str:
        leads = data.get("leads") or {}
        traffic = data.get("traffic") or {}
        lines = ["Master, your NXG funnel briefing:"]
        if not leads.get("available"):
            lines.append("- Leads: dashboard source unavailable this run.")
        else:
            new = leads.get("new") or []
            if new:
                lines.append(f"- New leads since last briefing: {len(new)}")
                for l in new[:20]:
                    name = " ".join(x for x in [l.get("first_name"), l.get("last_name")] if x) or "(no name)"
                    lines.append(f"    • {name} — {l.get('primary_concern_label') or 'n/a'} "
                                 f"[{l.get('pipeline_stage') or 'new'}] {l.get('created_at') or ''}")
            else:
                lines.append("- No new leads since yesterday.")
            lines.append(f"- Total leads: {leads.get('total', 0)} (today: {leads.get('today', 0)})")
        if traffic.get("available"):
            ppl = traffic.get("people")
            lines.append(f"- Traffic: {ppl if ppl is not None else '—'} people, "
                         f"{traffic.get('views', 0)} views; devices: {traffic.get('devices') or '—'}")
        else:
            lines.append("- Traffic: tracking not connected yet.")
        return "\n".join(lines)

    # --------------------------------------------------------------- persistence
    @staticmethod
    def _parse_dt(s: Optional[str]) -> Optional[datetime]:
        if not s:
            return None
        try:
            return datetime.fromisoformat(str(s).replace("Z", "+00:00"))
        except Exception:  # noqa: BLE001
            return None

    async def _load_state(self, db: AsyncSession) -> Dict:
        try:
            row = (await db.execute(
                select(AutomationState).where(AutomationState.key == _STATE_KEY)
            )).scalars().first()
            if row and isinstance(row.data, dict):
                return dict(row.data)
        except Exception as e:  # noqa: BLE001
            logger.debug(f"nxg load state failed: {e}")
        return {}

    async def _save_state(self, db: AsyncSession, state: Dict) -> None:
        try:
            row = (await db.execute(
                select(AutomationState).where(AutomationState.key == _STATE_KEY)
            )).scalars().first()
            if row:
                row.data = state
            else:
                db.add(AutomationState(key=_STATE_KEY, data=state))
            await db.flush()
        except Exception as e:  # noqa: BLE001
            logger.debug(f"nxg save state failed: {e}")

    async def _record(self, db: AsyncSession, summary: str, data: Dict, ok: bool) -> None:
        try:
            from ..models.report import Report, ReportType
            report = Report(
                title=f"NXG Funnel Briefing — {datetime.utcnow():%Y-%m-%d}",
                report_type=ReportType.BUSINESS_EXPANSION,
                report_date=datetime.utcnow(),
                content=data,
                summary=summary,
            )
            db.add(report)
            await db.flush()
        except Exception as e:  # noqa: BLE001
            logger.debug(f"nxg report persist skipped: {e}")
        try:
            leads = data.get("leads") or {}
            await shared_memory.remember(
                db, content=summary[:4000], kind="nxg_brief", actor="ORELIUS",
                meta={"ok": ok, "new_leads": len(leads.get("new") or []),
                      "total_leads": leads.get("total"),
                      "traffic_connected": bool((data.get("traffic") or {}).get("available"))},
            )
        except Exception as e:  # noqa: BLE001
            logger.debug(f"nxg shared-memory write skipped: {e}")


# Global instance
nxg_intel = NXGIntel()
