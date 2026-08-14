"""
Message Metrics Model
Per-message behavioral metrics for real-time analysis
"""
from sqlalchemy import Column, Integer, Float, String, ForeignKey
from sqlalchemy.orm import relationship
from ..database import Base

class MessageMetrics(Base):
    """
    Behavioral metrics extracted from each message
    Used for real-time anomaly detection
    """
    __tablename__ = "message_metrics"

    message_id = Column(Integer, ForeignKey("messages.id"), primary_key=True)

    # Typing pattern metrics
    typing_speed_wpm = Column(Float, nullable=True)  # Words per minute (estimated)
    message_length = Column(Integer, nullable=True)  # Character count
    word_count = Column(Integer, nullable=True)  # Word count
    sentence_count = Column(Integer, nullable=True)  # Number of sentences

    # Writing style metrics
    punctuation_count = Column(Integer, default=0)  # Number of punctuation marks
    capitalization_errors = Column(Integer, default=0)  # Incorrect capitalization
    spelling_errors = Column(Integer, default=0)  # Detected typos

    # Vocabulary metrics
    vocabulary_matches = Column(Integer, default=0)  # Words matching fingerprint

    # Emotional metrics
    sentiment_score = Column(Float, nullable=True)  # -1.0 to 1.0
    emotional_state = Column(String(50), nullable=True)  # 'calm', 'stressed', etc.

    # Timing metrics
    timestamp_delta = Column(Float, nullable=True)  # Seconds since last message

    # Anomaly detection
    anomaly_score = Column(Float, default=0.0)  # 0-100, higher = more anomalous

    # Relationship
    message = relationship("Message", back_populates="metrics")

    def __repr__(self):
        return f"<MessageMetrics(message_id={self.message_id}, wpm={self.typing_speed_wpm}, anomaly={self.anomaly_score})>"

    def calculate_typing_speed(self, time_elapsed: float) -> float:
        """
        Calculate typing speed in words per minute
        """
        if time_elapsed > 0 and self.word_count:
            self.typing_speed_wpm = (self.word_count / time_elapsed) * 60
            return self.typing_speed_wpm
        return 0.0

    def is_anomalous(self, threshold: float = 70.0) -> bool:
        """
        Check if anomaly score exceeds threshold
        """
        return self.anomaly_score >= threshold
