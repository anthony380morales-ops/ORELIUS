"""
O.R.E.L.I.U.S. Token & Credit Optimizer
------------------------------------------------
The credit saver. Because ORELIUS is called on daily, this module keeps the
Anthropic bill low and long-lasting through four levers:

  1. Response cache  - identical repeat questions are served from memory (0 API credits)
  2. History trimming - only the most recent, relevant turns are sent to the model
  3. Prompt caching   - the persona prefix is marked cacheable (~90% cheaper on reuse)
  4. Usage tracking   - every call's tokens + estimated USD cost are logged so spend is visible

Model: Claude Haiku 4.5 ($1 / 1M input, $5 / 1M output) — the cheapest efficient Claude model.
"""
from __future__ import annotations

import hashlib
import json
import os
import threading
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from ..config import settings
from ..utils.logger import logger

# Claude Haiku 4.5 list pricing (USD per 1M tokens)
PRICE_INPUT_PER_M = 1.00
PRICE_OUTPUT_PER_M = 5.00
PRICE_CACHE_WRITE_PER_M = 1.25   # ~1.25x input
PRICE_CACHE_READ_PER_M = 0.10    # ~0.10x input


def _now() -> float:
    return time.time()


def _hash(*parts: str) -> str:
    h = hashlib.sha256()
    for p in parts:
        h.update(p.encode("utf-8", "ignore"))
        h.update(b"\x00")
    return h.hexdigest()


@dataclass
class _CacheEntry:
    value: str
    expires_at: float


class ResponseCache:
    """Tiny in-process TTL cache. Repeat questions cost 0 credits."""

    def __init__(self, ttl: int, max_items: int):
        self.ttl = ttl
        self.max_items = max_items
        self._store: Dict[str, _CacheEntry] = {}
        self._lock = threading.Lock()
        self.hits = 0
        self.misses = 0

    def _evict_if_needed(self) -> None:
        if len(self._store) <= self.max_items:
            return
        # drop oldest-expiring entries first
        for key, _ in sorted(self._store.items(), key=lambda kv: kv[1].expires_at)[
            : len(self._store) - self.max_items
        ]:
            self._store.pop(key, None)

    def get(self, key: str) -> Optional[str]:
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                self.misses += 1
                return None
            if entry.expires_at < _now():
                self._store.pop(key, None)
                self.misses += 1
                return None
            self.hits += 1
            return entry.value

    def set(self, key: str, value: str) -> None:
        with self._lock:
            self._store[key] = _CacheEntry(value=value, expires_at=_now() + self.ttl)
            self._evict_if_needed()


@dataclass
class UsageTotals:
    requests: int = 0
    cached_responses: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0
    est_cost_usd: float = 0.0
    est_savings_usd: float = 0.0

    def as_dict(self) -> dict:
        return {
            "requests": self.requests,
            "cached_responses": self.cached_responses,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "cache_read_tokens": self.cache_read_tokens,
            "cache_write_tokens": self.cache_write_tokens,
            "est_cost_usd": round(self.est_cost_usd, 6),
            "est_savings_usd": round(self.est_savings_usd, 6),
        }


class UsageTracker:
    """Accumulates token usage + estimated cost and persists a daily snapshot to disk."""

    def __init__(self, path: str):
        self.path = path
        self.totals = UsageTotals()
        self._lock = threading.Lock()
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        self._load()

    def _load(self) -> None:
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                data = json.load(f)
            t = data.get("totals", {})
            self.totals = UsageTotals(**{k: t.get(k, 0) for k in UsageTotals().as_dict()})
        except (FileNotFoundError, json.JSONDecodeError, TypeError):
            self.totals = UsageTotals()

    def _persist(self) -> None:
        try:
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump({"updated_at": _now(), "totals": self.totals.as_dict()}, f, indent=2)
        except OSError as e:
            logger.warning(f"UsageTracker persist failed: {e}")

    def record_api_call(
        self,
        input_tokens: int,
        output_tokens: int,
        cache_read_tokens: int = 0,
        cache_write_tokens: int = 0,
    ) -> float:
        cost = (
            (input_tokens / 1_000_000) * PRICE_INPUT_PER_M
            + (output_tokens / 1_000_000) * PRICE_OUTPUT_PER_M
            + (cache_read_tokens / 1_000_000) * PRICE_CACHE_READ_PER_M
            + (cache_write_tokens / 1_000_000) * PRICE_CACHE_WRITE_PER_M
        )
        # savings from serving cached prefix at read-rate instead of full input-rate
        savings = (cache_read_tokens / 1_000_000) * (PRICE_INPUT_PER_M - PRICE_CACHE_READ_PER_M)
        with self._lock:
            self.totals.requests += 1
            self.totals.input_tokens += input_tokens
            self.totals.output_tokens += output_tokens
            self.totals.cache_read_tokens += cache_read_tokens
            self.totals.cache_write_tokens += cache_write_tokens
            self.totals.est_cost_usd += cost
            self.totals.est_savings_usd += savings
            self._persist()
        return cost

    def record_cache_hit(self, would_be_input: int, would_be_output: int) -> None:
        """A response served from ResponseCache — full call cost avoided."""
        avoided = (would_be_input / 1_000_000) * PRICE_INPUT_PER_M + (
            would_be_output / 1_000_000
        ) * PRICE_OUTPUT_PER_M
        with self._lock:
            self.totals.cached_responses += 1
            self.totals.est_savings_usd += avoided
            self._persist()

    def snapshot(self) -> dict:
        with self._lock:
            return self.totals.as_dict()


class TokenOptimizer:
    """Front-door for every optimization lever ORELIUS uses per request."""

    def __init__(self):
        self.response_cache = ResponseCache(
            ttl=settings.response_cache_ttl,
            max_items=settings.response_cache_max_items,
        )
        self.usage = UsageTracker(settings.usage_log_path)

    # --- history trimming ------------------------------------------------
    @staticmethod
    def _estimate_tokens(text: str) -> int:
        # ~4 chars per token; good enough for trimming decisions without an API call
        return max(1, len(text) // 4)

    def trim_history(self, history: List[Dict[str, str]]) -> List[Dict[str, str]]:
        """Keep the most recent turns within the message + token budget.

        Sending the whole conversation on every turn is the #1 hidden cost.
        We keep the last N messages and cap total tokens, preserving user/assistant
        pairing by simply slicing from the end.
        """
        if not history:
            return history
        trimmed = history[-settings.max_history_messages :]
        # enforce token ceiling from the newest end backwards
        budget = settings.max_history_tokens
        kept: List[Dict[str, str]] = []
        for msg in reversed(trimmed):
            cost = self._estimate_tokens(msg.get("content", ""))
            if budget - cost < 0 and kept:
                break
            budget -= cost
            kept.append(msg)
        kept.reverse()
        # the first message sent to the API must be a user turn
        while kept and kept[0].get("role") != "user":
            kept.pop(0)
        return kept or history[-1:]

    # --- response cache --------------------------------------------------
    def cache_key(self, system_prompt: str, history: List[Dict[str, str]]) -> str:
        # key on persona + last user message; short histories reuse well for FAQs
        last_user = ""
        for msg in reversed(history):
            if msg.get("role") == "user":
                last_user = msg.get("content", "")
                break
        return _hash(settings.oreilus_model, system_prompt[:512], last_user.strip().lower())

    def get_cached_response(self, key: str) -> Optional[str]:
        if not settings.enable_response_cache:
            return None
        return self.response_cache.get(key)

    def store_response(self, key: str, response: str) -> None:
        if settings.enable_response_cache and response:
            self.response_cache.set(key, response)

    # --- dynamic output cap ---------------------------------------------
    @staticmethod
    def choose_max_tokens(user_message: str) -> int:
        """Small cap for chat; larger only when a full report/plan is asked for."""
        triggers = ("report", "plan", "blueprint", "strategy", "breakdown", "outline", "analysis")
        low = user_message.lower()
        if any(t in low for t in triggers):
            return settings.oreilus_report_max_tokens
        return settings.oreilus_max_tokens

    def stats(self) -> dict:
        return {
            "model": settings.oreilus_model,
            "response_cache": {
                "hits": self.response_cache.hits,
                "misses": self.response_cache.misses,
                "enabled": settings.enable_response_cache,
            },
            "prompt_caching_enabled": settings.enable_prompt_caching,
            "usage": self.usage.snapshot(),
        }


# Global optimizer instance
token_optimizer = TokenOptimizer()
