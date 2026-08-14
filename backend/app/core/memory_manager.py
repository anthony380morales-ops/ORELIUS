"""
Memory Manager for O.R.E.I.L.U.S.
Handles conversation context and memory management
"""
from typing import List, Dict, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from ..models.conversation import Conversation, Message, MessageRole, MessageSource
from ..models.audit_log import AuditLog, AuditEventType, AuditSeverity
from ..utils.logger import logger
from .claude_client import claude_client


class MemoryManager:
    """
    Manages conversation memory and context for O.R.E.I.L.U.S.
    """

    def __init__(self, max_context_tokens: int = 200000):
        """
        Initialize memory manager

        Args:
            max_context_tokens: Maximum tokens to keep in context (Claude has 200k context)
        """
        self.max_context_tokens = max_context_tokens

    async def get_or_create_conversation(
        self,
        db: AsyncSession,
        user_id: str,
        source: MessageSource,
    ) -> Conversation:
        """
        Get existing conversation or create new one

        Args:
            db: Database session
            user_id: User identifier
            source: Message source (web/telegram)

        Returns:
            Conversation object
        """
        # Try to get latest conversation for user
        query = (
            select(Conversation)
            .where(Conversation.user_id == user_id)
            .where(Conversation.source == source)
            .order_by(Conversation.updated_at.desc())
            .limit(1)
        )
        result = await db.execute(query)
        conversation = result.scalar_one_or_none()

        if not conversation:
            # Create new conversation
            conversation = Conversation(
                user_id=user_id,
                source=source,
                title="New Conversation",
            )
            db.add(conversation)
            await db.flush()
            logger.info(f"Created new conversation {conversation.id} for user {user_id}")

        return conversation

    async def add_message(
        self,
        db: AsyncSession,
        conversation_id: int,
        role: MessageRole,
        content: str,
    ) -> Message:
        """
        Add a message to the conversation

        Args:
            db: Database session
            conversation_id: Conversation ID
            role: Message role (user/assistant)
            content: Message content

        Returns:
            Created message
        """
        token_count = claude_client.count_tokens(content)

        message = Message(
            conversation_id=conversation_id,
            role=role,
            content=content,
            token_count=token_count,
        )
        db.add(message)
        await db.flush()

        logger.info(f"Added {role} message to conversation {conversation_id} ({token_count} tokens)")

        return message

    async def get_conversation_history(
        self,
        db: AsyncSession,
        conversation_id: int,
        max_messages: Optional[int] = None,
    ) -> List[Dict[str, str]]:
        """
        Get conversation history formatted for Claude API

        Args:
            db: Database session
            conversation_id: Conversation ID
            max_messages: Maximum number of messages to retrieve

        Returns:
            List of message dicts for Claude API
        """
        query = (
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .where(Message.role != MessageRole.SYSTEM)  # Don't include system messages
            .order_by(Message.created_at.desc())
        )

        if max_messages:
            query = query.limit(max_messages)

        result = await db.execute(query)
        messages = result.scalars().all()

        # Reverse to get chronological order
        messages = list(reversed(messages))

        # Trim to token limit
        messages = self._trim_to_token_limit(messages)

        # Convert to Claude format
        claude_messages = []
        for msg in messages:
            claude_messages.append({
                "role": msg.role.value,
                "content": msg.content,
            })

        return claude_messages

    def _trim_to_token_limit(self, messages: List[Message]) -> List[Message]:
        """
        Trim messages to stay within token limit

        Args:
            messages: List of messages

        Returns:
            Trimmed list of messages
        """
        total_tokens = sum(msg.token_count for msg in messages)

        if total_tokens <= self.max_context_tokens:
            return messages

        # Keep trimming oldest messages until we're under limit
        trimmed_messages = messages.copy()
        while total_tokens > self.max_context_tokens and len(trimmed_messages) > 1:
            removed_msg = trimmed_messages.pop(0)
            total_tokens -= removed_msg.token_count
            logger.warning(f"Trimmed message from context (token limit exceeded)")

        return trimmed_messages

    async def log_audit(
        self,
        db: AsyncSession,
        event_type: AuditEventType,
        description: str,
        user_id: Optional[str] = None,
        severity: AuditSeverity = AuditSeverity.INFO,
        event_metadata: Optional[Dict] = None,
    ):
        """
        Log an audit event

        Args:
            db: Database session
            event_type: Type of audit event
            description: Event description
            user_id: User ID (optional)
            severity: Event severity
            event_metadata: Additional metadata
        """
        audit_log = AuditLog(
            event_type=event_type,
            severity=severity,
            user_id=user_id,
            description=description,
            event_metadata=event_metadata,
        )
        db.add(audit_log)
        await db.flush()

        logger.info(f"Audit log: {event_type.value} - {description}")


# Global memory manager instance
memory_manager = MemoryManager()
