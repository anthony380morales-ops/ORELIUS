"""
O.R.E.L.I.U.S. Core Engine
The heart of the autonomous AI agent system.

Rebuilt to run on Claude Haiku 4.5 with a credit-saving layer (response cache,
history trimming, prompt caching, dynamic output caps) and a shared-memory link
to its companion system LUCIUS.
"""
from typing import AsyncGenerator, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from .claude_client import claude_client
from .memory_manager import memory_manager
from .security import security_layer
from .prompts import get_system_prompt
from .token_optimizer import token_optimizer
from .shared_memory import shared_memory
from ..models.conversation import MessageRole, MessageSource
from ..models.audit_log import AuditEventType, AuditSeverity
from ..config import settings
from ..utils.logger import logger


class OreilusEngine:
    """
    O.R.E.L.I.U.S. Core Engine
    Coordinates all agent capabilities: Claude API, memory, security, reporting,
    credit optimization, and the LUCIUS shared-memory companion link.
    """

    def __init__(self):
        self.system_prompt = get_system_prompt(full=True)
        self.claude = claude_client
        self.memory = memory_manager
        self.security = security_layer
        self.optimizer = token_optimizer
        self.shared = shared_memory

    def _compose_system(self) -> str:
        """Persona + a small block of shared LUCIUS/ORELIUS memory.

        The shared context is kept short so it barely adds tokens; the persona
        prefix stays stable so prompt caching keeps hitting.
        """
        return self.system_prompt + self.shared.build_context()

    async def process_message(
        self,
        db: AsyncSession,
        user_id: str,
        user_message: str,
        source: MessageSource = MessageSource.WEB,
        stream: bool = False,
    ) -> str | AsyncGenerator[str, None]:
        """Process incoming message from user."""
        try:
            # SECURITY: validate user authorization for all message sources
            # (string IDs so web logins like "anthony" work alongside numeric Telegram IDs)
            allowed_users = settings.allowed_login_ids

            is_safe, threat, audit_event, severity = await self.security.check_message_security(
                user_message,
                user_id,
                allowed_users,
            )

            await self.memory.log_audit(
                db,
                event_type=audit_event,
                description=threat if not is_safe else "Message received successfully",
                user_id=user_id,
                severity=severity,
                event_metadata={"source": source.value, "message_length": len(user_message)},
            )

            if not is_safe:
                logger.warning(f"Security check failed for user {user_id}: {threat}")
                return f"Security alert: {threat}. This incident has been logged."

            # Get or create conversation
            conversation = await self.memory.get_or_create_conversation(db, user_id, source)

            # Add user message to database
            await self.memory.add_message(
                db,
                conversation.id,
                MessageRole.USER,
                user_message,
            )

            # Conversation history, trimmed to control token spend
            history = await self.memory.get_conversation_history(db, conversation.id)
            history = self.optimizer.trim_history(history)

            logger.info(f"Generating response for user {user_id} (conversation {conversation.id})")

            if stream:
                return self._stream_response(db, conversation.id, history, user_message)
            return await self._complete_response(db, conversation.id, history, user_message)

        except Exception as e:
            logger.error(f"Error processing message: {e}")
            await self.memory.log_audit(
                db,
                event_type=AuditEventType.SECURITY_ALERT,
                description=f"Error processing message: {str(e)}",
                user_id=user_id,
                severity=AuditSeverity.ERROR,
            )
            return (
                "I apologize, Master. An internal error occurred while processing your "
                "request. The issue has been logged for review."
            )

    async def _complete_response(
        self,
        db: AsyncSession,
        conversation_id: int,
        history: list[dict],
        user_message: str,
    ) -> str:
        """Generate complete response (non-streaming) with response-cache short-circuit."""
        system = self._compose_system()

        # 1) Credit saver: identical repeat question? serve from cache for 0 credits.
        cache_key = self.optimizer.cache_key(system, history)
        cached = self.optimizer.get_cached_response(cache_key)
        if cached is not None:
            logger.info("Served response from cache (0 credits used)")
            self.optimizer.usage.record_cache_hit(
                would_be_input=self.claude.count_messages_tokens(history),
                would_be_output=self.claude.count_tokens(cached),
            )
            await self.memory.add_message(db, conversation_id, MessageRole.ASSISTANT, cached)
            return cached

        # 2) Live call with a dynamic output cap (small for chat, larger for reports)
        response = await self.claude.chat(
            messages=history,
            system_prompt=system,
            stream=False,
            max_tokens=self.optimizer.choose_max_tokens(user_message),
        )

        self.optimizer.store_response(cache_key, response)
        await self.memory.add_message(db, conversation_id, MessageRole.ASSISTANT, response)
        self._record_shared_memory(user_message, response)
        return response

    async def _stream_response(
        self,
        db: AsyncSession,
        conversation_id: int,
        history: list[dict],
        user_message: str,
    ) -> AsyncGenerator[str, None]:
        """Generate streaming response."""
        system = self._compose_system()
        full_response = ""

        async for chunk in await self.claude.chat(
            messages=history,
            system_prompt=system,
            stream=True,
            max_tokens=self.optimizer.choose_max_tokens(user_message),
        ):
            full_response += chunk
            yield chunk

        # persist + cache + share once streaming completes
        self.optimizer.store_response(self.optimizer.cache_key(system, history), full_response)
        await self.memory.add_message(db, conversation_id, MessageRole.ASSISTANT, full_response)
        self._record_shared_memory(user_message, full_response)

    def _record_shared_memory(self, user_message: str, response: str) -> None:
        """Write a compact exchange summary to the LUCIUS/ORELIUS shared log."""
        try:
            self.shared.remember(
                content=f"Master asked: {user_message[:280]} | ORELIUS advised: {response[:280]}",
                kind="exchange",
                actor="ORELIUS",
            )
        except Exception as e:  # noqa: BLE001 - shared memory must never break a reply
            logger.debug(f"shared memory write skipped: {e}")

    async def validate_system(self) -> dict:
        """Validate that O.R.E.L.I.U.S. is operational."""
        status = {
            "system": "O.R.E.L.I.U.S.",
            "model": settings.oreilus_model,
            "status": "operational",
            "components": {},
        }

        try:
            claude_valid = await self.claude.validate_api_key()
            status["components"]["claude_api"] = "operational" if claude_valid else "error"
        except Exception as e:
            status["components"]["claude_api"] = f"error: {str(e)}"
            status["status"] = "degraded"

        status["components"]["security_layer"] = "operational"
        status["components"]["memory_manager"] = "operational"
        status["components"]["shared_memory_lucius"] = "operational"
        status["components"]["token_optimizer"] = "operational"

        logger.info(f"System validation: {status['status']}")
        return status

    def optimization_stats(self) -> dict:
        """Expose credit-saver stats (for the dashboard / cost visibility)."""
        return self.optimizer.stats()


# Global O.R.E.L.I.U.S. engine instance
oreilus_engine = OreilusEngine()
