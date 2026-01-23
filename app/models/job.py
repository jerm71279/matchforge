"""
MatchForge Job Models
Job listings and match tracking
"""
from sqlalchemy import Column, String, Integer, Boolean, DateTime, JSON, Text, Float
from sqlalchemy.sql import func
from datetime import datetime
import uuid

from app.core.database import Base


class Job(Base):
    """Job listing model"""
    __tablename__ = "jobs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

    # Source tracking
    source = Column(String(50), index=True)  # usajobs, themuse, adzuna, demo
    source_id = Column(String(255), index=True)  # Original ID from source
    source_url = Column(String(1000))

    # Job details
    title = Column(String(500), nullable=False)
    company = Column(String(255))
    location = Column(String(255))
    is_remote = Column(Boolean, default=False)

    # Compensation
    salary_min = Column(Integer)
    salary_max = Column(Integer)
    salary_currency = Column(String(10), default="USD")

    # Description
    description = Column(Text)
    required_skills = Column(JSON, default=list)
    preferred_skills = Column(JSON, default=list)

    # Requirements
    min_experience = Column(Integer)
    max_experience = Column(Integer)
    education_level = Column(String(100))

    # Metadata
    posted_date = Column(DateTime(timezone=True))
    expires_date = Column(DateTime(timezone=True))
    is_active = Column(Boolean, default=True)

    # Company culture data (from The Muse)
    company_culture = Column(JSON)

    # Timestamps
    fetched_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class JobMatch(Base):
    """User-job match tracking"""
    __tablename__ = "job_matches"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), index=True, nullable=False)
    job_id = Column(String(36), index=True, nullable=False)

    # Match scores
    total_score = Column(Integer)  # 0-100
    skills_score = Column(Integer)
    experience_score = Column(Integer)
    salary_score = Column(Integer)
    location_score = Column(Integer)
    title_score = Column(Integer)
    recency_score = Column(Integer)

    # ATS compatibility
    ats_score = Column(Integer)
    ats_issues = Column(JSON, default=list)
    ats_suggestions = Column(JSON, default=list)

    # User interaction
    is_viewed = Column(Boolean, default=False)
    is_saved = Column(Boolean, default=False)
    is_applied = Column(Boolean, default=False)
    is_hidden = Column(Boolean, default=False)

    # Timestamps
    matched_at = Column(DateTime(timezone=True), server_default=func.now())
    viewed_at = Column(DateTime(timezone=True))
    saved_at = Column(DateTime(timezone=True))
    applied_at = Column(DateTime(timezone=True))


class SavedSearch(Base):
    """Saved job search queries"""
    __tablename__ = "saved_searches"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), index=True, nullable=False)

    # Search parameters
    keywords = Column(String(500))
    location = Column(String(255))
    remote_only = Column(Boolean, default=False)
    salary_min = Column(Integer)

    # Alerts
    alert_enabled = Column(Boolean, default=True)
    alert_frequency = Column(String(50), default="daily")  # daily, weekly

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_run = Column(DateTime(timezone=True))
