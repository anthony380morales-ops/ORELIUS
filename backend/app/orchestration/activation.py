"""
Production activation (directive §15, §46) — the ONLY path from simulation to live,
per provider and credential-gated.

Going live is deliberately hard: it requires (1) real credentials configured for at
least one provider, (2) an explicit typed confirmation from the owner, and (3) a
passing end-to-end acceptance run (§69). Only then is the durable RUN_LIVE override
set. Reverting to simulation is always allowed and instant — a single call, no gate —
so the safe state is one step away at any moment.

This module never hard-codes or logs secrets; it only checks whether the configured
values are non-empty. The kill switches still gate every real action after activation.
"""
from __future__ import annotations

from typing import Dict, List

from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..utils.logger import logger
from .flags import flags, SocialMode
from .acceptance import acceptance_harness
from .adapters import lucius_adapter

CONFIRM_PHRASE = "ACTIVATE LIVE"

# Each provider: the config keys that must be non-empty to be "ready", and the kill
# switch that still gates it after activation.
PROVIDERS: Dict[str, Dict] = {
    "meta": {
        "settings": ["meta_app_id", "meta_app_secret", "meta_access_token"],
        "pause_flag": "PUBLISHING_PAUSE",
        "desc": "Meta Graph API — Facebook/Instagram publishing.",
    },
    "manychat": {
        "settings": ["manychat_api_token"],
        "pause_flag": "MESSAGING_PAUSE",
        "desc": "ManyChat — permitted messaging automation.",
    },
    "athena": {
        "settings": ["athena_base_url", "athena_api_token"],
        "pause_flag": "ATHENA_PAUSE",
        "desc": "ATHENA social-ops executor (localhost via the shared-memory bridge).",
    },
    "lucius": {
        "settings": ["lucius_api_url"],
        "pause_flag": None,
        "desc": "LUCIUS owner interface (alerts mirror).",
    },
}


def _configured(keys: List[str]) -> Dict:
    missing = [k for k in keys if not str(getattr(settings, k, "") or "").strip()]
    return {"configured": len(missing) == 0, "missing": missing}


class Activation:
    async def readiness(self, db: AsyncSession) -> Dict:
        """Per-provider credential readiness (no secrets echoed — only presence)."""
        providers = {}
        for name, spec in PROVIDERS.items():
            r = _configured(spec["settings"])
            providers[name] = {
                "configured": r["configured"], "missing": r["missing"],
                "pause_flag": spec["pause_flag"], "desc": spec["desc"],
                "paused": (await flags.get(db, spec["pause_flag"]))
                if spec["pause_flag"] else False,
            }
        ready = [n for n, p in providers.items() if p["configured"]]
        return {"providers": providers, "ready": ready, "any_ready": bool(ready)}

    async def status(self, db: AsyncSession) -> Dict:
        mode = await flags.mode(db)
        return {
            "mode": mode.value,
            "run_live_flag": await flags.get(db, "RUN_LIVE"),
            "system_paused": await flags.get(db, "SYSTEM_PAUSE"),
            "confirm_phrase": CONFIRM_PHRASE,
            "readiness": await self.readiness(db),
        }

    async def activate(self, db: AsyncSession, confirm: str, actor: str = "owner",
                       run_acceptance: bool = True) -> Dict:
        """Flip to live — only if confirmation, credentials, and the acceptance gate
        all pass. Returns a structured refusal otherwise (nothing changes)."""
        if (confirm or "").strip() != CONFIRM_PHRASE:
            return {"ok": False, "activated": False, "reason": "confirmation_required",
                    "hint": f"send confirm='{CONFIRM_PHRASE}'"}

        ready = await self.readiness(db)
        if not ready["any_ready"]:
            return {"ok": False, "activated": False, "reason": "no_provider_ready",
                    "readiness": ready}

        acceptance = None
        if run_acceptance:
            acceptance = await acceptance_harness.run(db)
            if not acceptance["ok"]:
                failed = [c["name"] for c in acceptance["checks"] if not c["ok"]]
                return {"ok": False, "activated": False, "reason": "acceptance_failed",
                        "failed_checks": failed}

        await flags.set(db, "RUN_LIVE", True)
        logger.info(f"PRODUCTION ACTIVATION by {actor} — live for {ready['ready']}")
        await lucius_adapter.notify(
            db, title="Production activation: ecosystem is now LIVE",
            body=f"Live providers: {', '.join(ready['ready'])}. Kill switches still "
                 f"gate every action. Revert any time with deactivate.",
            urgency="critical", kind="activation")
        return {"ok": True, "activated": True, "mode": SocialMode.LIVE.value,
                "live_providers": ready["ready"],
                "acceptance_passed": (acceptance["passed"] if acceptance else None)}

    async def deactivate(self, db: AsyncSession, actor: str = "owner") -> Dict:
        """Return to simulation immediately — always allowed, no gate."""
        await flags.set(db, "RUN_LIVE", False)
        logger.info(f"deactivated to simulation by {actor}")
        await lucius_adapter.notify(
            db, title="Reverted to SIMULATION", body="No real outbound actions.",
            urgency="high", kind="activation")
        return {"ok": True, "activated": False, "mode": (await flags.mode(db)).value}


activation = Activation()
