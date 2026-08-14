"""
Vocabulary Fingerprint Model
Tracks Anthony's top 500 most-used words for impersonation detection
"""
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from ..database import Base

class VocabularyFingerprint(Base):
    """
    Tracks Anthony's unique vocabulary patterns
    Used to detect impersonation through vocabulary differences
    """
    __tablename__ = "vocabulary_fingerprint"

    id = Column(Integer, primary_key=True, autoincrement=True)
    profile_id = Column(Integer, ForeignKey("master_profile.id"), nullable=False)

    # Word data
    word = Column(String(100), nullable=False, index=True)
    frequency = Column(Integer, nullable=False, default=1)  # Times word was used
    rank = Column(Integer, nullable=True)  # 1-500 most common words

    # Categorization
    category = Column(String(50), nullable=True)  # 'common', 'technical', 'emotion', 'unique'

    # Timestamps
    first_seen = Column(DateTime(timezone=True), server_default=func.now())
    last_seen = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationship
    profile = relationship("MasterProfile", back_populates="vocabulary_fingerprints")

    def __repr__(self):
        return f"<VocabularyFingerprint(word='{self.word}', frequency={self.frequency}, rank={self.rank})>"

    def increment_frequency(self):
        """
        Increment word usage frequency
        """
        self.frequency += 1
