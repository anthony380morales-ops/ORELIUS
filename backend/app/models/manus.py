"""
Manus AI integration models
Track Manus tasks and agent health metrics
"""
from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, Enum as SQLEnum, JSON
from sqlalchemy.sql import func
from enum import Enum
from datetime import datetime
from ..database import Base


class TaskType(str, Enum):
    """Types of Manus AI tasks"""
    CONTENT_TRENDS = "content_trends"
    MARKET_INTEL = "market_intel"
    LEAD_GEN = "lead_gen"
    SOCIAL_MONITORING = "social_monitoring"
    DATA_EXTRACTION = "data_extraction"
    REPORTING = "reporting"


class TaskStatus(str, Enum):
    """Manus task execution status"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ManusTask(Base):
    """
    Track Manus AI tasks
    Stores both local task tracking and Manus API task IDs
    """
    __tablename__ = "manus_tasks"

    id = Column(Integer, primary_key=True, index=True)
    manus_task_id = Column(String(255), unique=True, index=True, nullable=True)  # ID from Manus API
    task_type = Column(SQLEnum(TaskType), nullable=False, index=True)
    status = Column(SQLEnum(TaskStatus), default=TaskStatus.PENDING, index=True)

    # Scheduling
    trigger_type = Column(String(50))  # "scheduled" or "on_demand"
    scheduled_time = Column(DateTime(timezone=True), nullable=True)

    # Execution tracking
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    # Request/Response data
    request_payload = Column(JSON, nullable=True)  # What we sent to Manus
    response_data = Column(JSON, nullable=True)    # What we got back

    # Error handling
    error_message = Column(Text, nullable=True)
    retry_count = Column(Integer, default=0)

    # Metadata
    created_by = Column(String(255), nullable=True)  # user_id for on-demand tasks
    project_id = Column(String(255), nullable=True)  # Manus project ID

    def __repr__(self):
        return f"<ManusTask(id={self.id}, type={self.task_type}, status={self.status})>"


class ManusAgentHealth(Base):
    """
    Track health metrics for Manus AI agents
    Used for monitoring and silent failure detection
    """
    __tablename__ = "manus_agent_health"

    id = Column(Integer, primary_key=True, index=True)
    agent_name = Column(String(255), unique=True, index=True, nullable=False)  # e.g., "content_trends"

    # Health metrics
    status = Column(String(50), default="unknown")  # "healthy", "degraded", "down", "unknown"
    last_success_at = Column(DateTime(timezone=True), nullable=True)
    last_failure_at = Column(DateTime(timezone=True), nullable=True)

    # Performance metrics (rolling 24h)
    success_count_24h = Column(Integer, default=0)
    failure_count_24h = Column(Integer, default=0)
    avg_response_time_ms = Column(Integer, nullable=True)

    # Silent failure detection
    expected_frequency_hours = Column(Integer, default=24)  # How often should this agent run
    last_expected_run = Column(DateTime(timezone=True), nullable=True)
    is_silent_failure = Column(Boolean, default=False, index=True)

    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    def __repr__(self):
        return f"<ManusAgentHealth(agent={self.agent_name}, status={self.status}, silent_failure={self.is_silent_failure})>"
