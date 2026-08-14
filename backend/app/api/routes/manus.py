"""
Manus AI API Routes
Endpoints for managing Manus AI tasks and monitoring
"""
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime

from ...database import get_db
from ...services.manus_service import ManusService
from ...services.manus_scheduler import get_manus_scheduler
from ...models.manus import TaskType, TaskStatus
from ...core.auth import get_current_user
from ...utils.logger import logger

router = APIRouter()


# Request/Response Models
class CreateTaskRequest(BaseModel):
    """Request model for creating a Manus AI task"""
    task_type: TaskType
    custom_instructions: Optional[str] = None
    context: Optional[dict] = None


class TaskResponse(BaseModel):
    """Response model for task data"""
    id: int
    manus_task_id: Optional[str]
    task_type: TaskType
    status: TaskStatus
    trigger_type: str
    created_at: datetime
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    error_message: Optional[str]
    response_data: Optional[dict]
    created_by: Optional[str]

    class Config:
        from_attributes = True


class AgentHealthResponse(BaseModel):
    """Response model for agent health data"""
    name: str
    status: str
    success_rate_24h: float
    last_success: Optional[str]
    last_failure: Optional[str]
    is_silent_failure: bool
    avg_response_time_ms: Optional[int]
    success_count: int
    failure_count: int


class TaskMetricsResponse(BaseModel):
    """Response model for task metrics"""
    total: int
    completed: int
    failed: int
    in_progress: int
    success_rate: float


class DashboardMetricsResponse(BaseModel):
    """Response model for dashboard metrics"""
    agents: List[AgentHealthResponse]
    tasks_24h: TaskMetricsResponse
    silent_failures: int


class WebhookPayload(BaseModel):
    """Webhook payload from Manus AI"""
    event: str
    data: dict


class ScheduledJobResponse(BaseModel):
    """Response model for scheduled job info"""
    id: str
    name: str
    next_run: Optional[str]
    trigger: str


# Endpoints
@router.post("/tasks", response_model=TaskResponse)
async def create_task(
    request: CreateTaskRequest,
    db: AsyncSession = Depends(get_db),
    current_user: str = Depends(get_current_user)
):
    """
    Create an on-demand Manus AI task

    Requires valid JWT access token.

    Args:
        request: Task creation request
        db: Database session
        current_user: Authenticated user ID

    Returns:
        Created task data
    """
    try:
        service = ManusService(db)
        task = await service.create_task(
            task_type=request.task_type,
            trigger_type="on_demand",
            created_by=current_user,
            custom_instructions=request.custom_instructions,
            context=request.context
        )

        logger.info(f"On-demand task created: type={request.task_type.value}, user={current_user}")
        return task

    except Exception as e:
        logger.error(f"Failed to create task: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create task: {str(e)}")


@router.get("/tasks", response_model=List[TaskResponse])
async def list_tasks(
    status: Optional[TaskStatus] = None,
    task_type: Optional[TaskType] = None,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
    current_user: str = Depends(get_current_user)
):
    """
    List Manus AI tasks with optional filters

    Requires valid JWT access token.

    Args:
        status: Filter by task status
        task_type: Filter by task type
        limit: Maximum number of tasks (default: 50, max: 100)
        db: Database session
        current_user: Authenticated user ID

    Returns:
        List of tasks
    """
    try:
        # Cap limit at 100
        limit = min(limit, 100)

        service = ManusService(db)
        tasks = await service.list_tasks(
            status=status,
            task_type=task_type,
            limit=limit
        )

        return tasks

    except Exception as e:
        logger.error(f"Failed to list tasks: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to list tasks: {str(e)}")


@router.get("/tasks/{task_id}", response_model=TaskResponse)
async def get_task(
    task_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: str = Depends(get_current_user)
):
    """
    Get details of a specific task

    Requires valid JWT access token.

    Args:
        task_id: Task ID
        db: Database session
        current_user: Authenticated user ID

    Returns:
        Task data
    """
    try:
        service = ManusService(db)
        task = await service.get_task_by_id(task_id)

        if not task:
            raise HTTPException(status_code=404, detail="Task not found")

        return task

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get task {task_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get task: {str(e)}")


@router.get("/dashboard/metrics", response_model=DashboardMetricsResponse)
async def get_dashboard_metrics(
    db: AsyncSession = Depends(get_db),
    current_user: str = Depends(get_current_user)
):
    """
    Get real-time dashboard metrics

    Requires valid JWT access token.

    Returns agent health, task metrics, and silent failure count.

    Args:
        db: Database session
        current_user: Authenticated user ID

    Returns:
        Dashboard metrics data
    """
    try:
        service = ManusService(db)
        metrics = await service.get_dashboard_metrics()

        return metrics

    except Exception as e:
        logger.error(f"Failed to get dashboard metrics: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get metrics: {str(e)}")


@router.post("/webhooks/manus")
async def manus_webhook(
    payload: WebhookPayload,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    """
    Webhook endpoint for Manus AI notifications

    This endpoint does not require authentication as it receives callbacks from Manus AI.
    Webhook signature validation should be implemented in production.

    Args:
        payload: Webhook payload from Manus
        background_tasks: FastAPI background tasks
        db: Database session

    Returns:
        Acknowledgment response
    """
    try:
        logger.info(f"Received Manus webhook: event={payload.event}")

        # Process webhook in background to respond quickly
        service = ManusService(db)
        background_tasks.add_task(service.handle_webhook, payload.dict())

        return {"status": "accepted", "event": payload.event}

    except Exception as e:
        logger.error(f"Error processing webhook: {e}")
        # Return 200 anyway to prevent Manus from retrying
        return {"status": "error", "message": str(e)}


@router.post("/tasks/{task_id}/retry", response_model=TaskResponse)
async def retry_task(
    task_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: str = Depends(get_current_user)
):
    """
    Retry a failed task

    Creates a new task with the same parameters as the failed task.

    Requires valid JWT access token.

    Args:
        task_id: ID of failed task to retry
        db: Database session
        current_user: Authenticated user ID

    Returns:
        Newly created task data
    """
    try:
        service = ManusService(db)
        task = await service.get_task_by_id(task_id)

        if not task:
            raise HTTPException(status_code=404, detail="Task not found")

        if task.status != TaskStatus.FAILED:
            raise HTTPException(
                status_code=400,
                detail=f"Only failed tasks can be retried. Current status: {task.status.value}"
            )

        # Create new task with same parameters
        new_task = await service.create_task(
            task_type=task.task_type,
            trigger_type="on_demand",
            created_by=current_user,
            custom_instructions=task.request_payload.get("instructions") if task.request_payload else None,
            context=task.request_payload.get("context") if task.request_payload else None
        )

        # Update old task retry count
        task.retry_count += 1
        await db.commit()

        logger.info(f"Task {task_id} retried as new task {new_task.id}")
        return new_task

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to retry task {task_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to retry task: {str(e)}")


@router.get("/scheduler/jobs", response_model=List[ScheduledJobResponse])
async def get_scheduled_jobs(
    current_user: str = Depends(get_current_user)
):
    """
    Get list of scheduled jobs

    Requires valid JWT access token.

    Args:
        current_user: Authenticated user ID

    Returns:
        List of scheduled jobs
    """
    try:
        scheduler = get_manus_scheduler()
        jobs = scheduler.get_scheduled_jobs()
        return jobs

    except Exception as e:
        logger.error(f"Failed to get scheduled jobs: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get jobs: {str(e)}")


@router.get("/health")
async def manus_health_check():
    """
    Health check endpoint for Manus integration

    Does not require authentication.

    Returns:
        Health status
    """
    scheduler = get_manus_scheduler()

    return {
        "status": "healthy",
        "scheduler_running": scheduler.is_running,
        "timestamp": datetime.utcnow().isoformat()
    }
