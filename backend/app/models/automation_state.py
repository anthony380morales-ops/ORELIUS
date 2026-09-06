"""
Automation state — durable, baked-in memory for scheduled jobs.

Used by the daily financial intelligence engine to remember which data points it
has ALREADY reported, so it never re-mentions previously-informed data and never
reaches back further than the configured lookback window.
"""
from sqlalchemy import Column, Integer, String, JSON, DateTime
from datetime import datetime
from ..database import Base


class AutomationState(Base):
    __tablename__ = "automation_state"

    id = Column(Integer, primary_key=True, index=True)
    key = Column(String(128), unique=True, index=True, nullable=False)
    data = Column(JSON, default=dict)   # arbitrary per-automation JSON state
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
