"""
Master Profile Model
Stores Anthony Morales' core identity and security configuration
"""
from sqlalchemy import Column, Integer, String, DateTime, Enum as SQLEnum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from ..database import Base
import enum

class SecurityMode(str, enum.Enum):
    LEARNING = "learning"
    MONITORING = "monitoring"
    ENFORCING = "enforcing"

class MasterProfile(Base):
    """
    Single-user profile for Anthony Morales
    Always id=1 (only one Master in the system)
    """
    __tablename__ = "master_profile"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False, default="Anthony Morales")
    telegram_user_id = Column(String(50), nullable=False)

    # Learning phase tracking
    enrollment_started_at = Column(DateTime(timezone=True), server_default=func.now())
    baseline_established_at = Column(DateTime(timezone=True), nullable=True)

    # Security mode: learning → monitoring → enforcing
    security_mode = Column(SQLEnum(SecurityMode), default=SecurityMode.LEARNING, nullable=False)

    # TOTP secret (encrypted)
    totp_secret = Column(String(255), nullable=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    behavioral_baselines = relationship("BehavioralBaseline", back_populates="profile", cascade="all, delete-orphan")
    vocabulary_fingerprints = relationship("VocabularyFingerprint", back_populates="profile", cascade="all, delete-orphan")
    emotional_profiles = relationship("EmotionalProfile", back_populates="profile", cascade="all, delete-orphan")
    sessions = relationship("SessionAuthentication", back_populates="profile", cascade="all, delete-orphan")
    dynamic_keywords = relationship("DynamicKeyword", back_populates="profile", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<MasterProfile(id={self.id}, name='{self.name}', mode='{self.security_mode}')>"
