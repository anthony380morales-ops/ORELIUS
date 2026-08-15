"""
Claude API Client Wrapper (O.R.E.L.I.U.S. brain)
Model: Claude Haiku 4.5 — cheapest + most efficient Claude model for daily use.
Handles streaming, prompt caching, dynamic output caps, and usage capture.
"""
from anthropic import AsyncAnthropic
from typing import AsyncGenerator, List, Dict, Optional
from ..config import settings
from ..utils.logger import logger
from .token_optimizer import token_optimizer


class ClaudeClient:
    """Wrapper for the Claude API with prompt caching + credit tracking."""

    def __init__(self):
        self.client = AsyncAnthropic(api_key=settings.anthropic_api_key)
        self.model = settings.oreilus_model            # claude-haiku-4-5
        self.max_tokens = settings.oreilus_max_tokens
        self.temperature = settings.oreilus_temperature

    def _build_system(self, system_prompt: str):
        """Return the system field, marking it cacheable so the persona prefix is
        billed at ~0.1x on reuse (huge saving for a daily-use assistant)."""
        if settings.enable_prompt_caching:
            return [
                {
                    "type": "text",
                    "text": system_prompt,
                    "cache_control": {"type": "ephemeral"},
                }
            ]
        return system_prompt

    async def chat(
        self,
        messages: List[Dict[str, str]],
        system_prompt: str,
        stream: bool = False,
        max_tokens: Optional[int] = None,
    ) -> str | AsyncGenerator[str, None]:
        """Send a chat message to Claude (streaming or complete)."""
        try:
            if stream:
                return self._stream_chat(messages, system_prompt, max_tokens)
            return await self._complete_chat(messages, system_prompt, max_tokens)
        except Exception as e:
            logger.error(f"Claude API error: {e}")
            raise

    async def _complete_chat(
        self,
        messages: List[Dict[str, str]],
        system_prompt: str,
        max_tokens: Optional[int],
    ) -> str:
        response = await self.client.messages.create(
            model=self.model,
            max_tokens=max_tokens or self.max_tokens,
            temperature=self.temperature,
            system=self._build_system(system_prompt),
            messages=messages,
        )
        self._record_usage(response.usage)
        if response.content and len(response.content) > 0:
            return response.content[0].text
        return ""

    async def complete_with_tools(
        self,
        messages: List[Dict[str, str]],
        system_prompt: str,
        tools: List[Dict],
        max_tokens: Optional[int] = None,
        tool_choice: Optional[Dict] = None,
    ):
        """Non-streaming call that offers the model `tools`.

        Returns the raw Anthropic response so the caller can inspect `stop_reason`
        and any `tool_use` blocks. Usage is still recorded for credit tracking.
        `tool_choice` can force a specific tool, e.g. {"type": "tool", "name": ...}.
        """
        kwargs = dict(
            model=self.model,
            max_tokens=max_tokens or self.max_tokens,
            temperature=self.temperature,
            system=self._build_system(system_prompt),
            messages=messages,
            tools=tools,
        )
        if tool_choice is not None:
            kwargs["tool_choice"] = tool_choice
        response = await self.client.messages.create(**kwargs)
        self._record_usage(response.usage)
        return response

    async def _stream_chat(
        self,
        messages: List[Dict[str, str]],
        system_prompt: str,
        max_tokens: Optional[int],
    ) -> AsyncGenerator[str, None]:
        async with self.client.messages.stream(
            model=self.model,
            max_tokens=max_tokens or self.max_tokens,
            temperature=self.temperature,
            system=self._build_system(system_prompt),
            messages=messages,
        ) as stream:
            async for text in stream.text_stream:
                yield text
            final = await stream.get_final_message()
            self._record_usage(final.usage)

    def _record_usage(self, usage) -> None:
        """Log tokens + estimated USD cost to the credit tracker."""
        try:
            token_optimizer.usage.record_api_call(
                input_tokens=getattr(usage, "input_tokens", 0) or 0,
                output_tokens=getattr(usage, "output_tokens", 0) or 0,
                cache_read_tokens=getattr(usage, "cache_read_input_tokens", 0) or 0,
                cache_write_tokens=getattr(usage, "cache_creation_input_tokens", 0) or 0,
            )
        except Exception as e:  # noqa: BLE001 - never break a reply over accounting
            logger.debug(f"usage record skipped: {e}")

    def count_tokens(self, text: str) -> int:
        """Rough token estimate (~4 chars/token). Avoids an extra API round-trip."""
        return max(1, len(text) // 4)

    def count_messages_tokens(self, messages: List[Dict[str, str]]) -> int:
        return sum(self.count_tokens(msg.get("content", "")) for msg in messages)

    async def validate_api_key(self) -> bool:
        try:
            await self.client.messages.create(
                model=self.model,
                max_tokens=10,
                messages=[{"role": "user", "content": "test"}],
            )
            return True
        except Exception as e:
            logger.error(f"Claude API key validation failed: {e}")
            return False


# Global Claude client instance
claude_client = ClaudeClient()
