"""
Claude API Client Wrapper
Handles all communication with Anthropic's Claude API
"""
from anthropic import AsyncAnthropic
from typing import AsyncGenerator, List, Dict, Optional
from ..config import settings
from ..utils.logger import logger
import tiktoken


class ClaudeClient:
    """
    Wrapper for Claude API with streaming support and token management
    """

    def __init__(self):
        self.client = AsyncAnthropic(api_key=settings.anthropic_api_key)
        self.model = "claude-sonnet-4-5-20250929"  # Claude Sonnet 4.5
        self.max_tokens = 16000  # Max tokens for response (doubled for longer responses)
        self.temperature = 0.7

    async def chat(
        self,
        messages: List[Dict[str, str]],
        system_prompt: str,
        stream: bool = False,
    ) -> str | AsyncGenerator[str, None]:
        """
        Send a chat message to Claude

        Args:
            messages: List of message dicts with 'role' and 'content'
            system_prompt: System prompt to set context
            stream: If True, return streaming generator

        Returns:
            Full response text or streaming generator
        """
        try:
            if stream:
                return self._stream_chat(messages, system_prompt)
            else:
                return await self._complete_chat(messages, system_prompt)
        except Exception as e:
            logger.error(f"Claude API error: {e}")
            raise

    async def _complete_chat(
        self,
        messages: List[Dict[str, str]],
        system_prompt: str,
    ) -> str:
        """Get complete chat response (non-streaming)"""
        response = await self.client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            temperature=self.temperature,
            system=system_prompt,
            messages=messages,
        )

        # Extract text from response
        if response.content and len(response.content) > 0:
            return response.content[0].text
        return ""

    async def _stream_chat(
        self,
        messages: List[Dict[str, str]],
        system_prompt: str,
    ) -> AsyncGenerator[str, None]:
        """Get streaming chat response"""
        async with self.client.messages.stream(
            model=self.model,
            max_tokens=self.max_tokens,
            temperature=self.temperature,
            system=system_prompt,
            messages=messages,
        ) as stream:
            async for text in stream.text_stream:
                yield text

    def count_tokens(self, text: str) -> int:
        """
        Estimate token count for text

        Args:
            text: Input text

        Returns:
            Estimated token count
        """
        try:
            # Use tiktoken for estimation (Claude uses similar tokenization)
            encoding = tiktoken.get_encoding("cl100k_base")
            return len(encoding.encode(text))
        except Exception as e:
            logger.warning(f"Token counting failed: {e}")
            # Fallback: rough estimate (1 token ≈ 4 characters)
            return len(text) // 4

    def count_messages_tokens(self, messages: List[Dict[str, str]]) -> int:
        """
        Count total tokens in message list

        Args:
            messages: List of message dicts

        Returns:
            Total token count
        """
        total = 0
        for msg in messages:
            total += self.count_tokens(msg.get("content", ""))
        return total

    async def validate_api_key(self) -> bool:
        """
        Validate that the Claude API key is working

        Returns:
            True if valid, False otherwise
        """
        try:
            # Send a simple test message
            response = await self.client.messages.create(
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
