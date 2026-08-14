"""
Session Authentication Model
Tracks each session's authentication confidence and anomaly flags
"""
from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, ForeignKey, JSON, Enum as SQLEnum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from ..database import Base
import enum

class SessionSource(str, enum.Enum):
    TELEGRAM = "telegram"
    WEB = "web"
    API = "api"

class AuthStatus(str, enum.Enum):
    AUTHENTICATED = "authenticated"
    CHALLENGED = "challenged"
    REJECTED = "rejected"

class SessionAuthentication(Base):
    """
    Authentication record for each session
    Tracks confidence scores, anomalies, and lockout events
    """
    __tablename__ = "session_authentication"

    id = Column(Integer, primary_key=True, autoincrement=True)
    profile_id = Column(Integer, ForeignKey("master_profile.id"), nullable=False)

    # Session identification
    session_id = Column(String(255), nullable=False, unique=True, index=True)
    started_at = Column(DateTime(timezone=True), server_default=func.now())
    ended_at = Column(DateTime(timezone=True), nullable=True)

    # Source information
    source = Column(SQLEnum(SessionSource), nullable=False)
    ip_address = Column(String(45), nullable=True)  # IPv4 or IPv6
    device_fingerprint = Column(String(255), nullable=True)

    # Authentication metrics
    confidence_score = Column(Float, nullable=True)  # 0-100
    anomaly_flags = Column(JSON, nullable=True)  # List of detected anomalies
    auth_status = Column(SQLEnum(AuthStatus), default=AuthStatus.AUTHENTICATED)

    # Challenge-response
    challenge_type = Column(String(50), nullable=True)  # 'keyword', 'totp', 'security_question'
    challenge_result = Column(Boolean, nullable=True)

    # Lockout
    lockout_triggered = Column(Boolean, default=False)
    alert_sent = Column(Boolean, default=False)

    # Relationships
    profile = relationship("MasterProfile", back_populates="sessions")
    challenges = relationship("SecurityChallenge", back_populates="session", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<SessionAuthentication(id={self.id}, confidence={self.confidence_score}, status='{self.auth_status}')>"

    def is_suspicious(self, threshold: float = 85.0) -> bool:
        """
        Check if confidence score is below suspicious threshold
        """
        return self.confidence_score is not None and self.confidence_score < threshold

    def should_lockout(self, threshold: float = 70.0) -> bool:
        """
        Check if confidence score warrants immediate lockout
        """
        return self.confidence_score is not None and self.confidence_score < threshold
