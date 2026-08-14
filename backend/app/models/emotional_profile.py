"""
Emotional Profile Model
Daily emotional snapshots for tracking Anthony's mood and stress over time
"""
from sqlalchemy import Column, Integer, String, Float, Date, Text, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from ..database import Base

class EmotionalProfile(Base):
    """
    Daily emotional snapshot for Anthony
    Used for proactive check-ins and communication style adaptation
    """
    __tablename__ = "emotional_profile"

    id = Column(Integer, primary_key=True, autoincrement=True)
    profile_id = Column(Integer, ForeignKey("master_profile.id"), nullable=False)

    # Date of snapshot (one record per day)
    date = Column(Date, nullable=False, unique=True, index=True)

    # Emotional state
    dominant_emotion = Column(String(50), nullable=True)  # 'calm', 'stressed', 'excited', 'frustrated', 'focused'
    sentiment_score = Column(Float, nullable=True)  # -1.0 (negative) to 1.0 (positive)
    stress_indicators = Column(Integer, default=0)  # 0-10 scale
    energy_level = Column(String(20), nullable=True)  # 'low', 'medium', 'high'

    # Communication patterns
    topics_discussed = Column(JSON, nullable=True)  # List of topics: ['finance', 'business', 'technical']
    session_count = Column(Integer, default=0)  # Number of interactions that day

    # Claude's observations
    notes = Column(Text, nullable=True)  # Free-form notes about the day's emotional state

    # Timestamp
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationship
    profile = relationship("MasterProfile", back_populates="emotional_profiles")

    def __repr__(self):
        return f"<EmotionalProfile(date={self.date}, emotion='{self.dominant_emotion}', stress={self.stress_indicators})>"

    def is_stressed(self, threshold: int = 7) -> bool:
        """
        Check if stress level exceeds threshold
        """
        return self.stress_indicators >= threshold

    def get_sentiment_category(self) -> str:
        """
        Categorize sentiment score
        """
        if self.sentiment_score is None:
            return "unknown"
        elif self.sentiment_score >= 0.5:
            return "positive"
        elif self.sentiment_score >= 0.0:
            return "neutral"
        elif self.sentiment_score >= -0.5:
            return "slightly_negative"
        else:
            return "negative"
