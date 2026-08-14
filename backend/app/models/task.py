"""
Task model for automated job tracking
"""
from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, Enum as SQLEnum, JSON
from sqlalchemy.sql import func
from enum import Enum
from ..database import Base


class TaskType(str, Enum):
    """Task types"""
    CONTENT_SCAN = "content_scan"
    GOVERNMENT_INTEL = "government_intel"
    REPORT_GENERATION = "report_generation"
    SYSTEM_MAINTENANCE = "system_maintenance"
    CUSTOM = "custom"


class TaskStatus(str, Enum):
    """Task execution status"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class Task(Base):
    """Task model for scheduled and manual jobs"""
    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    task_type = Column(SQLEnum(TaskType), nullable=False, index=True)
    status = Column(SQLEnum(TaskStatus), default=TaskStatus.PENDING, index=True)
    schedule_time = Column(DateTime(timezone=True), nullable=True)  # Scheduled execution time
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    error_message = Column(Text, nullable=True)
    result_data = Column(JSON, nullable=True)  # Task results
    is_recurring = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
