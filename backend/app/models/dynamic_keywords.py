"""
Dynamic Keywords Model
O.R.E.I.L.U.S.-generated keywords for emergency authentication
"""
from sqlalchemy import Column, Integer, String, Boolean, Text, DateTime, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from ..database import Base

class DynamicKeyword(Base):
    """
    Dynamically generated keywords for authentication override
    O.R.E.I.L.U.S. generates these based on recent conversation context
    """
    __tablename__ = "dynamic_keywords"

    id = Column(Integer, primary_key=True, autoincrement=True)
    profile_id = Column(Integer, ForeignKey("master_profile.id"), nullable=False)

    # Keyword data (hashed for security)
    keyword_hash = Column(String(255), nullable=False, unique=True)  # SHA-256 hash

    # Context
    context = Column(Text, nullable=True)  # Why O.R.E.I.L.U.S. chose this keyword

    # Status
    active = Column(Boolean, default=True, index=True)  # Currently valid

    # Timestamps
    generated_at = Column(DateTime(timezone=True), server_default=func.now())
    expires_at = Column(DateTime(timezone=True), nullable=True)  # Optional expiration

    # Usage tracking
    times_used = Column(Integer, default=0)

    # Relationship
    profile = relationship("MasterProfile", back_populates="dynamic_keywords")

    def __repr__(self):
        return f"<DynamicKeyword(id={self.id}, active={self.active}, times_used={self.times_used})>"

    def increment_usage(self):
        """
        Increment usage counter
        """
        self.times_used += 1

    def is_expired(self) -> bool:
        """
        Check if keyword has expired
        """
        if self.expires_at is None:
            return False
        from datetime import datetime, timezone
        return datetime.now(timezone.utc) > self.expires_at

    def deactivate(self):
        """
        Deactivate this keyword (after use or expiration)
        """
        self.active = False
