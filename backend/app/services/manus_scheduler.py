"""
Manus AI Task Scheduler
Handles scheduled execution of Manus AI tasks
"""
import logging
import asyncio
from datetime import datetime
import pytz
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from typing import Callable
from .manus_service import ManusService
from ..models.manus import TaskType

logger = logging.getLogger(__name__)


class ManusScheduler:
    """Handles scheduled execution of Manus AI tasks"""

    def __init__(self):
        self.scheduler = AsyncIOScheduler(
            timezone=pytz.timezone('America/Los_Angeles')
        )
        self.db_session_factory = None
        self.is_running = False

    async def setup(self, db_session_factory: Callable):
        """
        Initialize scheduler with database session factory

        Args:
            db_session_factory: Async session factory for database access
        """
        self.db_session_factory = db_session_factory

        # Schedule daily tasks at 8 AM PST
        self.scheduler.add_job(
            self._run_daily_tasks,
            CronTrigger(hour=8, minute=0, timezone='America/Los_Angeles'),
            id="daily_manus_tasks",
            name="Daily Manus AI Tasks",
            replace_existing=True
        )
        logger.info("Scheduled daily Manus tasks at 8:00 AM PST")

        # Schedule silent failure checks every 30 minutes
        self.scheduler.add_job(
            self._check_silent_failures,
            'interval',
            minutes=30,
            id="silent_failure_check",
            name="Silent Failure Detection",
            replace_existing=True
        )
        logger.info("Scheduled silent failure checks every 30 minutes")

        # Schedule 24h metric reset at midnight PST
        self.scheduler.add_job(
            self._reset_daily_metrics,
            CronTrigger(hour=0, minute=0, timezone='America/Los_Angeles'),
            id="reset_daily_metrics",
            name="Reset Daily Metrics",
            replace_existing=True
        )
        logger.info("Scheduled daily metrics reset at midnight PST")

        self.scheduler.start()
        self.is_running = True
        logger.info("Manus scheduler started successfully")

    async def _run_daily_tasks(self):
        """Execute all scheduled daily tasks"""
        logger.info("Starting daily Manus AI tasks execution")

        if not self.db_session_factory:
            logger.error("Database session factory not initialized")
            return

        async with self.db_session_factory() as session:
            service = ManusService(session)

            # Define which tasks run daily at 8 AM PST
            daily_tasks = [
                TaskType.CONTENT_TRENDS,
                TaskType.MARKET_INTEL,
                TaskType.LEAD_GEN,
            ]

            tasks_created = 0
            tasks_failed = 0

            for task_type in daily_tasks:
                try:
                    task = await service.create_task(
                        task_type=task_type,
                        trigger_type="scheduled"
                    )
                    logger.info(f"Scheduled task created: {task_type.value}, id={task.id}")
                    tasks_created += 1
                except Exception as e:
                    logger.error(f"Failed to create scheduled task {task_type.value}: {e}")
                    tasks_failed += 1

            logger.info(
                f"Daily tasks execution completed: "
                f"{tasks_created} created, {tasks_failed} failed"
            )

    async def _check_silent_failures(self):
        """Check for agents that haven't reported in expected time"""
        logger.debug("Checking for silent failures")

        if not self.db_session_factory:
            logger.error("Database session factory not initialized")
            return

        try:
            async with self.db_session_factory() as session:
                service = ManusService(session)
                await service.check_silent_failures()
            logger.debug("Silent failure check completed")
        except Exception as e:
            logger.error(f"Error during silent failure check: {e}")

    async def _reset_daily_metrics(self):
        """Reset 24-hour counters"""
        logger.info("Resetting daily metrics")

        if not self.db_session_factory:
            logger.error("Database session factory not initialized")
            return

        try:
            async with self.db_session_factory() as session:
                service = ManusService(session)
                await service.reset_daily_metrics()
            logger.info("Daily metrics reset completed")
        except Exception as e:
            logger.error(f"Error resetting daily metrics: {e}")

    def shutdown(self):
        """Stop scheduler gracefully"""
        if self.is_running:
            logger.info("Shutting down Manus scheduler...")
            self.scheduler.shutdown(wait=True)
            self.is_running = False
            logger.info("Manus scheduler shut down successfully")
        else:
            logger.debug("Manus scheduler already stopped")

    def get_scheduled_jobs(self):
        """
        Get list of scheduled jobs

        Returns:
            List of job information dictionaries
        """
        if not self.is_running:
            return []

        jobs = []
        for job in self.scheduler.get_jobs():
            next_run = job.next_run_time
            jobs.append({
                "id": job.id,
                "name": job.name,
                "next_run": next_run.isoformat() if next_run else None,
                "trigger": str(job.trigger)
            })
        return jobs


# Global singleton instance
_scheduler_instance = None


def get_manus_scheduler() -> ManusScheduler:
    """Get the global ManusScheduler instance"""
    global _scheduler_instance
    if _scheduler_instance is None:
        _scheduler_instance = ManusScheduler()
    return _scheduler_instance
