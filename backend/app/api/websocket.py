"""
WebSocket handler for real-time chat with O.R.E.I.L.U.S.
"""
from fastapi import WebSocket, WebSocketDisconnect
from typing import Dict
from ..database import AsyncSessionLocal
from ..core import oreilus_engine
from ..models.conversation import MessageSource
from ..utils.logger import logger
import json


class ConnectionManager:
    """Manages WebSocket connections"""

    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}

    async def connect(self, websocket: WebSocket, user_id: str):
        """Accept WebSocket connection"""
        await websocket.accept()
        self.active_connections[user_id] = websocket
        logger.info(f"WebSocket connected: {user_id}")

    def disconnect(self, user_id: str):
        """Remove connection"""
        if user_id in self.active_connections:
            del self.active_connections[user_id]
            logger.info(f"WebSocket disconnected: {user_id}")

    async def send_message(self, user_id: str, message: str):
        """Send message to specific user"""
        if user_id in self.active_connections:
            await self.active_connections[user_id].send_text(message)


manager = ConnectionManager()


async def websocket_endpoint(websocket: WebSocket, user_id: str):
    """
    WebSocket endpoint for real-time chat

    Args:
        websocket: WebSocket connection
        user_id: User identifier
    """
    await manager.connect(websocket, user_id)

    try:
        while True:
            # Receive message from client
            data = await websocket.receive_text()

            try:
                message_data = json.loads(data)
                user_message = message_data.get("message", "")

                if not user_message:
                    await websocket.send_json({"error": "Empty message"})
                    continue

                # Create database session
                async with AsyncSessionLocal() as db:
                    # Process message with O.R.E.I.L.U.S. (streaming)
                    stream_generator = await oreilus_engine.process_message(
                        db=db,
                        user_id=user_id,
                        user_message=user_message,
                        source=MessageSource.WEB,
                        stream=True,
                    )

                    # Send streaming response
                    await websocket.send_json({"type": "start"})

                    async for chunk in stream_generator:
                        await websocket.send_json({
                            "type": "chunk",
                            "content": chunk,
                        })

                    await websocket.send_json({"type": "end"})
                    await db.commit()

            except json.JSONDecodeError:
                await websocket.send_json({"error": "Invalid JSON"})
            except Exception as e:
                logger.error(f"WebSocket message processing error: {e}")
                await websocket.send_json({"error": str(e)})

    except WebSocketDisconnect:
        manager.disconnect(user_id)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        manager.disconnect(user_id)
