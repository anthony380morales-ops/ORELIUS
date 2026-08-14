"""
Chat API endpoints for O.R.E.I.L.U.S.
"""
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from typing import Optional
from ...database import get_db
from ...core import oreilus_engine
from ...core.auth import get_current_user  # SECURITY FIX: Add JWT authentication
from ...models.conversation import MessageSource
from ...utils.logger import logger

router = APIRouter()


class ChatRequest(BaseModel):
    """Chat request model"""

    message: str
    source: Optional[str] = "web"
    stream: Optional[bool] = False
    # user_id removed from request body - will come from JWT token for security


class ChatResponse(BaseModel):
    """Chat response model"""

    response: str
    conversation_id: Optional[int] = None


@router.post("/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    db: AsyncSession = Depends(get_db),
    current_user: str = Depends(get_current_user),  # SECURITY FIX: Require JWT authentication
):
    """
    Send a message to O.R.E.I.L.U.S. and get a response

    SECURITY: Requires valid JWT access token

    Args:
        request: Chat request with message
        db: Database session
        current_user: Authenticated user ID from JWT token

    Returns:
        Chat response from O.R.E.I.L.U.S.
    """
    try:
        # Determine source
        source = MessageSource.WEB
        if request.source == "telegram":
            source = MessageSource.TELEGRAM
        elif request.source == "api":
            source = MessageSource.API

        logger.info(f"Chat request from user {current_user} via {source.value}")

        # Process message with O.R.E.I.L.U.S. (use authenticated user_id)
        response = await oreilus_engine.process_message(
            db=db,
            user_id=current_user,  # SECURITY FIX: Use authenticated user_id from JWT
            user_message=request.message,
            source=source,
            stream=False,
        )

        return ChatResponse(response=response)

    except Exception as e:
        logger.error(f"Chat endpoint error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/chat/stream")
async def chat_stream(
    request: ChatRequest,
    db: AsyncSession = Depends(get_db),
    current_user: str = Depends(get_current_user),  # SECURITY FIX: Require JWT authentication
):
    """
    Send a message to O.R.E.I.L.U.S. and get a streaming response

    SECURITY: Requires valid JWT access token

    Args:
        request: Chat request with message
        db: Database session
        current_user: Authenticated user ID from JWT token

    Returns:
        Streaming response from O.R.E.I.L.U.S.
    """
    try:
        # Determine source
        source = MessageSource.WEB
        if request.source == "telegram":
            source = MessageSource.TELEGRAM

        logger.info(f"Streaming chat request from user {current_user} via {source.value}")

        # Process message with O.R.E.I.L.U.S. (streaming, use authenticated user_id)
        stream_generator = await oreilus_engine.process_message(
            db=db,
            user_id=current_user,  # SECURITY FIX: Use authenticated user_id from JWT
            user_message=request.message,
            source=source,
            stream=True,
        )

        return StreamingResponse(
            stream_generator,
            media_type="text/plain",
        )

    except Exception as e:
        logger.error(f"Streaming chat endpoint error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/conversations/{user_id}")
async def get_conversations(
    user_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Get conversation history for a user

    Args:
        user_id: User identifier
        db: Database session

    Returns:
        List of conversations
    """
    from sqlalchemy import select
    from ...models.conversation import Conversation

    try:
        query = (
            select(Conversation)
            .where(Conversation.user_id == user_id)
            .order_by(Conversation.updated_at.desc())
            .limit(20)
        )
        result = await db.execute(query)
        conversations = result.scalars().all()

        return [
            {
                "id": conv.id,
                "title": conv.title,
                "source": conv.source.value,
                "created_at": conv.created_at.isoformat(),
                "updated_at": conv.updated_at.isoformat() if conv.updated_at else None,
            }
            for conv in conversations
        ]

    except Exception as e:
        logger.error(f"Get conversations error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/conversations/{conversation_id}/messages")
async def get_messages(
    conversation_id: int,
    db: AsyncSession = Depends(get_db),
):
    """
    Get messages for a specific conversation

    Args:
        conversation_id: Conversation ID
        db: Database session

    Returns:
        List of messages
    """
    from sqlalchemy import select
    from ...models.conversation import Message

    try:
        query = (
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at.asc())
        )
        result = await db.execute(query)
        messages = result.scalars().all()

        return [
            {
                "id": msg.id,
                "role": msg.role.value,
                "content": msg.content,
                "token_count": msg.token_count,
                "created_at": msg.created_at.isoformat(),
            }
            for msg in messages
        ]

    except Exception as e:
        logger.error(f"Get messages error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
