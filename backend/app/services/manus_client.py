"""
Manus AI API Client
Singleton client for interacting with Manus AI API
"""
import httpx
import logging
from typing import Optional, Dict, Any, List
import os

logger = logging.getLogger(__name__)


class ManusClient:
    """
    Singleton client for Manus AI API interactions
    Follows the singleton pattern used by claude_client
    """

    _instance: Optional['ManusClient'] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if not hasattr(self, 'initialized'):
            self.base_url = "https://api.manus.ai/v1"
            self.api_key = os.getenv("MANUS_API_KEY")

            if not self.api_key:
                logger.warning("MANUS_API_KEY not found in environment")

            self.client = httpx.AsyncClient(
                timeout=httpx.Timeout(60.0),  # Manus tasks can take time
                headers={
                    "X-API-Key": self.api_key,
                    "Content-Type": "application/json"
                }
            )
            self.initialized = True
            logger.info("Manus AI client initialized")

    async def create_task(
        self,
        task_type: str,
        instructions: str,
        context: Optional[Dict[str, Any]] = None,
        files: Optional[List[str]] = None,
        project_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create a new task in Manus AI

        Args:
            task_type: Type of task to create
            instructions: Task instructions
            context: Additional context data
            files: List of file IDs to attach
            project_id: Manus project ID

        Returns:
            Task data from Manus API
        """
        payload = {
            "type": task_type,
            "instructions": instructions,
            "context": context or {},
        }

        if files:
            payload["files"] = files

        if project_id:
            payload["project_id"] = project_id

        try:
            logger.info(f"Creating Manus task: type={task_type}")
            response = await self.client.post(
                f"{self.base_url}/tasks",
                json=payload
            )
            response.raise_for_status()
            data = response.json()
            logger.info(f"Manus task created: id={data.get('id')}")
            return data
        except httpx.HTTPError as e:
            logger.error(f"Failed to create Manus task: {e}")
            raise

    async def get_task(self, task_id: str) -> Dict[str, Any]:
        """
        Get task status and results

        Args:
            task_id: Manus task ID

        Returns:
            Task data including status and results
        """
        try:
            response = await self.client.get(f"{self.base_url}/tasks/{task_id}")
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            logger.error(f"Failed to get Manus task {task_id}: {e}")
            raise

    async def list_tasks(
        self,
        status: Optional[str] = None,
        task_type: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        List tasks with optional filters

        Args:
            status: Filter by status
            task_type: Filter by task type
            limit: Maximum number of tasks to return

        Returns:
            List of task data
        """
        params = {"limit": limit}
        if status:
            params["status"] = status
        if task_type:
            params["type"] = task_type

        try:
            response = await self.client.get(
                f"{self.base_url}/tasks",
                params=params
            )
            response.raise_for_status()
            data = response.json()
            # Manus API may return data in different formats
            if isinstance(data, list):
                return data
            elif isinstance(data, dict) and 'tasks' in data:
                return data['tasks']
            return []
        except httpx.HTTPError as e:
            logger.error(f"Failed to list Manus tasks: {e}")
            raise

    async def register_webhook(
        self,
        webhook_url: str,
        events: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Register webhook for task notifications

        Args:
            webhook_url: URL to receive webhook notifications
            events: List of events to subscribe to

        Returns:
            Webhook registration data
        """
        if events is None:
            events = ["task.completed", "task.failed", "task.cancelled"]

        payload = {
            "url": webhook_url,
            "events": events
        }

        try:
            logger.info(f"Registering Manus webhook: url={webhook_url}, events={events}")
            response = await self.client.post(
                f"{self.base_url}/webhooks",
                json=payload
            )
            response.raise_for_status()
            data = response.json()
            logger.info(f"Manus webhook registered: id={data.get('id')}")
            return data
        except httpx.HTTPError as e:
            logger.warning(f"Failed to register Manus webhook: {e}")
            # Don't raise - webhook registration failure shouldn't prevent startup
            return {}

    async def validate_api_key(self) -> bool:
        """
        Validate the Manus API key

        Returns:
            True if API key is valid
        """
        if not self.api_key:
            return False

        try:
            # Try to list tasks as a validation check
            await self.list_tasks(limit=1)
            logger.info("Manus API key validated successfully")
            return True
        except Exception as e:
            logger.error(f"Manus API key validation failed: {e}")
            return False

    async def close(self):
        """Cleanup on shutdown"""
        await self.client.aclose()
        logger.info("Manus AI client closed")


# Global singleton instance
_manus_client_instance = None


def get_manus_client() -> ManusClient:
    """Get the global ManusClient instance"""
    global _manus_client_instance
    if _manus_client_instance is None:
        _manus_client_instance = ManusClient()
    return _manus_client_instance
