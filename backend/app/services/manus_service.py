"""
Manus AI Service Layer
Business logic for Manus AI integration
"""
import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
from .manus_client import get_manus_client
from ..models.manus import ManusTask, ManusAgentHealth, TaskType, TaskStatus

logger = logging.getLogger(__name__)


class ManusService:
    """Business logic for Manus AI integration"""

    # Task type configurations
    TASK_CONFIGS = {
        TaskType.CONTENT_TRENDS: {
            "instructions": "Analyze current content trends across social media platforms (X/Twitter, Instagram, Facebook, LinkedIn, TikTok). Focus on AI, automation, finance, and business topics. Identify viral patterns, engagement metrics, and trending hashtags.",
            "expected_frequency_hours": 24
        },
        TaskType.MARKET_INTEL: {
            "instructions": "Gather market intelligence from government sources (Federal Reserve, FDIC, OCC, CFPB). Analyze banking regulations, financial policy changes, and industry impacts. Identify business opportunities in the banking and IBC education space.",
            "expected_frequency_hours": 24
        },
        TaskType.LEAD_GEN: {
            "instructions": "Identify and qualify potential leads based on specified criteria. Research prospects, validate contact information, assess fit for services, and compile lead profiles with engagement recommendations.",
            "expected_frequency_hours": 24
        },
        TaskType.SOCIAL_MONITORING: {
            "instructions": "Monitor social media platforms for brand mentions, sentiment analysis, competitor activity, and industry discussions. Track engagement metrics and identify influencer opportunities.",
            "expected_frequency_hours": 12
        },
        TaskType.DATA_EXTRACTION: {
            "instructions": "Extract and structure data from specified sources. Parse documents, scrape websites, process spreadsheets, and transform unstructured data into actionable insights.",
            "expected_frequency_hours": 168  # Weekly
        },
        TaskType.REPORTING: {
            "instructions": "Generate comprehensive reports from collected data. Create visualizations, summarize findings, identify trends, and provide actionable recommendations for business strategy.",
            "expected_frequency_hours": 168  # Weekly
        }
    }

    def __init__(self, db: AsyncSession):
        self.db = db
        self.manus_client = get_manus_client()

    async def create_task(
        self,
        task_type: TaskType,
        trigger_type: str,
        created_by: Optional[str] = None,
        custom_instructions: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> ManusTask:
        """
        Create and submit a task to Manus AI

        Args:
            task_type: Type of task to create
            trigger_type: "scheduled" or "on_demand"
            created_by: User ID who created the task
            custom_instructions: Override default instructions
            context: Additional context data

        Returns:
            Created ManusTask record
        """
        config = self.TASK_CONFIGS.get(task_type, {})
        instructions = custom_instructions or config.get("instructions", "")

        # Create local record first
        db_task = ManusTask(
            task_type=task_type,
            trigger_type=trigger_type,
            created_by=created_by,
            status=TaskStatus.PENDING,
            request_payload={
                "instructions": instructions,
                "context": context or {}
            }
        )

        self.db.add(db_task)
        await self.db.flush()  # Get ID without committing

        try:
            # Submit to Manus AI
            logger.info(f"Submitting task to Manus AI: type={task_type.value}, trigger={trigger_type}")
            manus_response = await self.manus_client.create_task(
                task_type=task_type.value,
                instructions=instructions,
                context=context
            )

            # Update with Manus task ID
            db_task.manus_task_id = manus_response.get("id")
            db_task.status = TaskStatus.IN_PROGRESS
            db_task.started_at = datetime.utcnow()

            await self.db.commit()
            logger.info(f"Task created successfully: id={db_task.id}, manus_id={db_task.manus_task_id}")
            return db_task

        except Exception as e:
            logger.error(f"Failed to create Manus task: {e}")
            db_task.status = TaskStatus.FAILED
            db_task.error_message = str(e)
            await self.db.commit()
            raise

    async def handle_webhook(self, webhook_payload: Dict[str, Any]):
        """
        Process webhook notification from Manus AI

        Args:
            webhook_payload: Webhook payload from Manus
        """
        event_type = webhook_payload.get("event")
        task_data = webhook_payload.get("data", {})
        manus_task_id = task_data.get("id")

        logger.info(f"Processing Manus webhook: event={event_type}, task_id={manus_task_id}")

        # Find our task record
        result = await self.db.execute(
            select(ManusTask).where(ManusTask.manus_task_id == manus_task_id)
        )
        task = result.scalar_one_or_none()

        if not task:
            logger.warning(f"Received webhook for unknown task: {manus_task_id}")
            return

        # Update based on event
        if event_type == "task.completed":
            task.status = TaskStatus.COMPLETED
            task.completed_at = datetime.utcnow()
            task.response_data = task_data.get("result", {})

            # Update agent health metrics
            execution_time = None
            if task.started_at:
                execution_time = int((datetime.utcnow() - task.started_at).total_seconds() * 1000)

            await self._update_agent_health(
                task.task_type.value,
                success=True,
                response_time_ms=execution_time
            )

            logger.info(f"Task completed: id={task.id}")

        elif event_type == "task.failed":
            task.status = TaskStatus.FAILED
            task.completed_at = datetime.utcnow()
            task.error_message = task_data.get("error", "Unknown error")

            # Update agent health metrics
            await self._update_agent_health(
                task.task_type.value,
                success=False
            )

            logger.error(f"Task failed: id={task.id}, error={task.error_message}")

        elif event_type == "task.cancelled":
            task.status = TaskStatus.CANCELLED
            task.completed_at = datetime.utcnow()
            logger.info(f"Task cancelled: id={task.id}")

        await self.db.commit()

    async def _update_agent_health(
        self,
        agent_name: str,
        success: bool,
        response_time_ms: Optional[int] = None
    ):
        """
        Update agent health metrics

        Args:
            agent_name: Name of the agent
            success: Whether the task succeeded
            response_time_ms: Task execution time in milliseconds
        """
        # Get or create health record
        result = await self.db.execute(
            select(ManusAgentHealth).where(ManusAgentHealth.agent_name == agent_name)
        )
        health = result.scalar_one_or_none()

        if not health:
            # Create new health record
            task_type = TaskType(agent_name)
            config = self.TASK_CONFIGS.get(task_type, {})
            health = ManusAgentHealth(
                agent_name=agent_name,
                expected_frequency_hours=config.get("expected_frequency_hours", 24)
            )
            self.db.add(health)
            await self.db.flush()

        # Update metrics
        now = datetime.utcnow()
        if success:
            health.last_success_at = now
            health.success_count_24h += 1
            health.status = "healthy"
            health.is_silent_failure = False
        else:
            health.last_failure_at = now
            health.failure_count_24h += 1

            # Determine status based on failure rate
            total = health.success_count_24h + health.failure_count_24h
            if total > 0:
                failure_rate = health.failure_count_24h / total
                health.status = "degraded" if failure_rate < 0.5 else "down"

        if response_time_ms:
            # Moving average for response time
            if health.avg_response_time_ms:
                health.avg_response_time_ms = int(
                    (health.avg_response_time_ms * 0.8) + (response_time_ms * 0.2)
                )
            else:
                health.avg_response_time_ms = response_time_ms

        await self.db.commit()
        logger.info(f"Agent health updated: {agent_name}, status={health.status}")

    async def check_silent_failures(self):
        """
        Detect agents that haven't run when expected
        Checks if agents have reported in their expected timeframes
        """
        result = await self.db.execute(select(ManusAgentHealth))
        agents = result.scalars().all()

        now = datetime.utcnow()
        silent_failures_detected = 0

        for agent in agents:
            if not agent.last_success_at:
                # Agent has never run successfully
                agent.is_silent_failure = True
                agent.status = "down"
                silent_failures_detected += 1
                continue

            expected_interval = timedelta(hours=agent.expected_frequency_hours)
            time_since_success = now - agent.last_success_at

            # Mark as silent failure if overdue by 50%
            if time_since_success > expected_interval * 1.5:
                if not agent.is_silent_failure:
                    logger.warning(
                        f"Silent failure detected: {agent.agent_name}, "
                        f"last success was {time_since_success.total_seconds() / 3600:.1f} hours ago"
                    )
                    silent_failures_detected += 1
                agent.is_silent_failure = True
                agent.status = "down"
            else:
                # Agent is reporting within expected timeframe
                if agent.is_silent_failure:
                    logger.info(f"Silent failure resolved: {agent.agent_name}")
                agent.is_silent_failure = False
                # Don't override status if it's already set to degraded/healthy

        await self.db.commit()

        if silent_failures_detected > 0:
            logger.warning(f"Total silent failures detected: {silent_failures_detected}")

    async def get_dashboard_metrics(self) -> Dict[str, Any]:
        """
        Get comprehensive metrics for dashboard

        Returns:
            Dictionary containing agents list and task metrics
        """
        # Get all agent health records
        result = await self.db.execute(select(ManusAgentHealth))
        agents = result.scalars().all()

        # Get recent tasks (last 24 hours)
        cutoff = datetime.utcnow() - timedelta(hours=24)
        result = await self.db.execute(
            select(ManusTask).where(ManusTask.created_at >= cutoff)
        )
        recent_tasks = result.scalars().all()

        # Calculate task metrics
        total_tasks = len(recent_tasks)
        completed = sum(1 for t in recent_tasks if t.status == TaskStatus.COMPLETED)
        failed = sum(1 for t in recent_tasks if t.status == TaskStatus.FAILED)
        in_progress = sum(1 for t in recent_tasks if t.status == TaskStatus.IN_PROGRESS)
        success_rate = (completed / max(1, total_tasks)) * 100

        # Format agent data
        agents_data = []
        for agent in agents:
            total_agent_tasks = agent.success_count_24h + agent.failure_count_24h
            agent_success_rate = (
                (agent.success_count_24h / max(1, total_agent_tasks)) * 100
                if total_agent_tasks > 0 else 0
            )

            agents_data.append({
                "name": agent.agent_name,
                "status": agent.status,
                "success_rate_24h": round(agent_success_rate, 1),
                "last_success": agent.last_success_at.isoformat() if agent.last_success_at else None,
                "last_failure": agent.last_failure_at.isoformat() if agent.last_failure_at else None,
                "is_silent_failure": agent.is_silent_failure,
                "avg_response_time_ms": agent.avg_response_time_ms,
                "success_count": agent.success_count_24h,
                "failure_count": agent.failure_count_24h
            })

        return {
            "agents": agents_data,
            "tasks_24h": {
                "total": total_tasks,
                "completed": completed,
                "failed": failed,
                "in_progress": in_progress,
                "success_rate": round(success_rate, 1)
            },
            "silent_failures": sum(1 for a in agents if a.is_silent_failure)
        }

    async def reset_daily_metrics(self):
        """
        Reset 24-hour counters
        Should be called daily at midnight
        """
        await self.db.execute(
            update(ManusAgentHealth).values(
                success_count_24h=0,
                failure_count_24h=0
            )
        )
        await self.db.commit()
        logger.info("Daily metrics reset completed")

    async def get_task_by_id(self, task_id: int) -> Optional[ManusTask]:
        """
        Get a task by its ID

        Args:
            task_id: Local task ID

        Returns:
            ManusTask or None if not found
        """
        result = await self.db.execute(
            select(ManusTask).where(ManusTask.id == task_id)
        )
        return result.scalar_one_or_none()

    async def list_tasks(
        self,
        status: Optional[TaskStatus] = None,
        task_type: Optional[TaskType] = None,
        limit: int = 50
    ) -> List[ManusTask]:
        """
        List tasks with optional filters

        Args:
            status: Filter by status
            task_type: Filter by task type
            limit: Maximum number of tasks to return

        Returns:
            List of ManusTask records
        """
        query = select(ManusTask).order_by(ManusTask.created_at.desc()).limit(limit)

        if status:
            query = query.where(ManusTask.status == status)
        if task_type:
            query = query.where(ManusTask.task_type == task_type)

        result = await self.db.execute(query)
        return result.scalars().all()
