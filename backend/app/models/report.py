"""
Report model for storing daily intelligence reports
"""
from sqlalchemy import Column, Integer, String, Text, DateTime, Enum as SQLEnum, JSON
from sqlalchemy.sql import func
from enum import Enum
from ..database import Base


class ReportType(str, Enum):
    """Report types"""
    CONTENT_TRENDS = "content_trends"
    BANKING_INTELLIGENCE = "banking_intelligence"
    CONTENT_SUGGESTIONS = "content_suggestions"
    MASTER_OPTIMIZATION = "master_optimization"
    BUSINESS_EXPANSION = "business_expansion"
    SYSTEMS_OPTIMIZATION = "systems_optimization"
    OREILUS_EVOLUTION = "oreilus_evolution"


class Report(Base):
    """Report model for daily and ad-hoc reports"""
    __tablename__ = "reports"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=False)
    report_type = Column(SQLEnum(ReportType), nullable=False, index=True)
    report_date = Column(DateTime(timezone=True), index=True)  # Date the report covers
    content = Column(JSON, nullable=False)  # Structured report data
    summary = Column(Text, nullable=True)  # AI-generated summary
    google_sheet_url = Column(String(500), nullable=True)  # Link to Google Sheet
    created_at = Column(DateTime(timezone=True), server_default=func.now())
