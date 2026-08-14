"""
Security Challenges Model
Tracks challenge-response authentication attempts
"""
from sqlalchemy import Column, Integer, String, Float, Boolean, Text, DateTime, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from ..database import Base

class SecurityChallenge(Base):
    """
    Challenge-response authentication records
    Used when behavioral confidence is low
    """
    __tablename__ = "security_challenges"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(255), ForeignKey("session_authentication.session_id"), nullable=False)

    # Challenge details
    challenge_type = Column(String(50), nullable=False)  # 'keyword', 'totp', 'question'
    challenge_question = Column(Text, nullable=True)  # The question asked
    expected_answer_hash = Column(String(255), nullable=False)  # SHA-256 hash of correct answer

    # User response
    user_response = Column(Text, nullable=True)  # Encrypted user response
    response_time_seconds = Column(Float, nullable=True)  # Time taken to respond

    # Result
    success = Column(Boolean, nullable=False, default=False)
    attempt_number = Column(Integer, default=1)  # 1st, 2nd, 3rd attempt

    # Context
    triggered_by = Column(String(100), nullable=True)  # What anomaly triggered the challenge

    # Timestamp
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationship
    session = relationship("SessionAuthentication", back_populates="challenges")

    def __repr__(self):
        return f"<SecurityChallenge(type='{self.challenge_type}', success={self.success}, attempt={self.attempt_number})>"

    def is_slow_response(self, threshold_seconds: float = 120.0) -> bool:
        """
        Check if response time indicates uncertainty or lookup
        """
        return self.response_time_seconds is not None and self.response_time_seconds > threshold_seconds
