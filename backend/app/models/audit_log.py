"""
Audit Log model for security and compliance tracking
"""
from sqlalchemy import Column, Integer, String, Text, DateTime, JSON, Enum as SQLEnum
from sqlalchemy.sql import func
from enum import Enum
from ..database import Base


class AuditEventType(str, Enum):
    """Audit event types"""
    MESSAGE_SENT = "message_sent"
    MESSAGE_RECEIVED = "message_received"
    TASK_EXECUTED = "task_executed"
    TASK_FAILED = "task_failed"
    AUTH_SUCCESS = "auth_success"
    AUTH_FAILURE = "auth_failure"
    SECURITY_ALERT = "security_alert"
    SYSTEM_CHANGE = "system_change"
    REPORT_GENERATED = "report_generated"
    PROMPT_INJECTION_DETECTED = "prompt_injection_detected"


class AuditSeverity(str, Enum):
    """Audit severity levels"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class AuditLog(Base):
    """Audit log for tracking all system events"""
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    event_type = Column(SQLEnum(AuditEventType), nullable=False, index=True)
    severity = Column(SQLEnum(AuditSeverity), default=AuditSeverity.INFO, index=True)
    user_id = Column(String(255), nullable=True, index=True)
    description = Column(Text, nullable=False)
    event_metadata = Column(JSON, nullable=True)  # Additional event data
    ip_address = Column(String(45), nullable=True)  # IPv4/IPv6
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
