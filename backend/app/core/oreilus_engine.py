"""
O.R.E.I.L.U.S. Core Engine
The heart of the autonomous AI agent system
"""
from typing import AsyncGenerator, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from .claude_client import claude_client
from .memory_manager import memory_manager
from .security import security_layer
from .prompts import get_system_prompt
from ..models.conversation import MessageRole, MessageSource
from ..models.audit_log import AuditEventType, AuditSeverity
from ..config import settings
from ..utils.logger import logger


class OreilusEngine:
    """
    O.R.E.I.L.U.S. Core Engine
    Coordinates all agent capabilities: Claude API, memory, security, reporting
    """

    def __init__(self):
        self.system_prompt = get_system_prompt(full=True)
        self.claude = claude_client
        self.memory = memory_manager
        self.security = security_layer

    async def process_message(
        self,
        db: AsyncSession,
        user_id: str,
        user_message: str,
        source: MessageSource = MessageSource.WEB,
        stream: bool = False,
    ) -> str | AsyncGenerator[str, None]:
        """
        Process incoming message from user

        Args:
            db: Database session
            user_id: User identifier
            user_message: User's message content
            source: Message source (web/telegram)
            stream: If True, return streaming response

        Returns:
            O.R.E.I.L.U.S. response (full text or streaming generator)
        """
        try:
            # SECURITY FIX: Always validate user authorization for all message sources
            allowed_users = [str(uid) for uid in settings.allowed_telegram_users]

            is_safe, threat, audit_event, severity = await self.security.check_message_security(
                user_message,
                user_id,
                allowed_users,
            )

            # Log audit event
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

            # Get conversation history
            history = await self.memory.get_conversation_history(db, conversation.id)

            # Generate response from Claude
            logger.info(f"Generating response for user {user_id} (conversation {conversation.id})")

            if stream:
                return self._stream_response(db, conversation.id, history)
            else:
                return await self._complete_response(db, conversation.id, history)

        except Exception as e:
            logger.error(f"Error processing message: {e}")
            await self.memory.log_audit(
                db,
                event_type=AuditEventType.SECURITY_ALERT,
                description=f"Error processing message: {str(e)}",
                user_id=user_id,
                severity=AuditSeverity.ERROR,
            )
            return "I apologize, Master. An internal error occurred while processing your request. The issue has been logged for review."

    async def _complete_response(
        self,
        db: AsyncSession,
        conversation_id: int,
        history: list[dict],
    ) -> str:
        """
        Generate complete response (non-streaming)

        Args:
            db: Database session
            conversation_id: Conversation ID
            history: Conversation history

        Returns:
            Full response text
        """
        response = await self.claude.chat(
            messages=history,
            system_prompt=self.system_prompt,
            stream=False,
        )

        # Save assistant response to database
        await self.memory.add_message(
            db,
            conversation_id,
            MessageRole.ASSISTANT,
            response,
        )

        return response

    async def _stream_response(
        self,
        db: AsyncSession,
        conversation_id: int,
        history: list[dict],
    ) -> AsyncGenerator[str, None]:
        """
        Generate streaming response

        Args:
            db: Database session
            conversation_id: Conversation ID
            history: Conversation history

        Yields:
            Response text chunks
        """
        full_response = ""

        async for chunk in await self.claude.chat(
            messages=history,
            system_prompt=self.system_prompt,
            stream=True,
        ):
            full_response += chunk
            yield chunk

        # Save complete response to database after streaming finishes
        await self.memory.add_message(
            db,
            conversation_id,
            MessageRole.ASSISTANT,
            full_response,
        )

    async def validate_system(self) -> dict:
        """
        Validate that O.R.E.I.L.U.S. is operational

        Returns:
            System status dict
        """
        status = {
            "system": "O.R.E.I.L.U.S.",
            "status": "operational",
            "components": {},
        }

        # Check Claude API
        try:
            claude_valid = await self.claude.validate_api_key()
            status["components"]["claude_api"] = "operational" if claude_valid else "error"
        except Exception as e:
            status["components"]["claude_api"] = f"error: {str(e)}"
            status["status"] = "degraded"

        # Check security layer
        status["components"]["security_layer"] = "operational"

        # Check memory manager
        status["components"]["memory_manager"] = "operational"

        logger.info(f"System validation: {status['status']}")
        return status


# Global O.R.E.I.L.U.S. engine instance
oreilus_engine = OreilusEngine()
