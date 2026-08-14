"""
Behavioral Baseline Model
Stores statistical baselines for Anthony's typing speed, vocabulary, timing patterns
"""
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from ..database import Base

class BehavioralBaseline(Base):
    """
    Statistical baselines for behavioral biometric authentication
    Each row represents one metric (typing_speed, vocabulary_diversity, etc.)
    """
    __tablename__ = "behavioral_baseline"

    id = Column(Integer, primary_key=True, autoincrement=True)
    profile_id = Column(Integer, ForeignKey("master_profile.id"), nullable=False)

    # Metric identification
    metric_type = Column(String(50), nullable=False)  # 'typing_speed_wpm', 'vocab_diversity', etc.

    # Statistical values
    avg_value = Column(Float, nullable=False)  # Average (mean)
    stddev = Column(Float, nullable=False)  # Standard deviation
    min_value = Column(Float, nullable=False)  # Minimum observed value
    max_value = Column(Float, nullable=False)  # Maximum observed value

    # Metadata
    sample_size = Column(Integer, nullable=False)  # Number of messages analyzed
    confidence = Column(Float, nullable=False)  # 0.0 to 1.0 confidence in this baseline
    last_updated = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationship
    profile = relationship("MasterProfile", back_populates="behavioral_baselines")

    def __repr__(self):
        return f"<BehavioralBaseline(metric='{self.metric_type}', avg={self.avg_value}, stddev={self.stddev})>"

    def is_anomalous(self, value: float, threshold_stddev: float = 2.5) -> bool:
        """
        Check if a value is anomalous (beyond threshold standard deviations)
        """
        deviation = abs(value - self.avg_value) / self.stddev if self.stddev > 0 else 0
        return deviation > threshold_stddev

    def get_z_score(self, value: float) -> float:
        """
        Calculate Z-score for a given value
        """
        return (value - self.avg_value) / self.stddev if self.stddev > 0 else 0.0
