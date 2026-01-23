"""
MatchForge Feedback Models
Track user interactions and outcomes for algorithm improvement
"""
from sqlalchemy import Column, String, Integer, Boolean, DateTime, JSON, Text, Float
from sqlalchemy.sql import func
import uuid

from app.core.database import Base


class MatchFeedback(Base):
    """
    Feedback on job matches for algorithm improvement.
    Tracks implicit signals (views, time spent) and explicit outcomes.
    """
    __tablename__ = "match_feedback"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), index=True, nullable=False)
    job_id = Column(String(36), index=True, nullable=False)
    match_score = Column(Integer)  # Score at time of interaction

    # Implicit signals (no user action required)
    viewed = Column(Boolean, default=False)
    view_count = Column(Integer, default=0)
    view_duration_seconds = Column(Integer, default=0)  # Total time viewing
    saved = Column(Boolean, default=False)
    applied = Column(Boolean, default=False)

    # Explicit negative signal
    not_interested = Column(Boolean, default=False)
    not_interested_reason = Column(String(255))  # salary, location, skills, company, other

    # Explicit rating (optional)
    user_rating = Column(Integer)  # 1-5 stars

    # Outcome tracking (if user reports)
    got_response = Column(Boolean)
    got_interview = Column(Boolean)
    got_offer = Column(Boolean)
    outcome_notes = Column(Text)

    # Timestamps
    first_viewed_at = Column(DateTime(timezone=True))
    last_viewed_at = Column(DateTime(timezone=True))
    saved_at = Column(DateTime(timezone=True))
    applied_at = Column(DateTime(timezone=True))
    outcome_reported_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class FeedbackMetrics(Base):
    """
    Aggregated feedback metrics by match score bucket.
    Used for algorithm validation and tuning.
    """
    __tablename__ = "feedback_metrics"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

    # Score bucket (e.g., "90-100", "80-89", etc.)
    score_bucket = Column(String(20), index=True, nullable=False)

    # Date for daily aggregation
    metric_date = Column(DateTime(timezone=True), index=True)

    # Counts
    total_shown = Column(Integer, default=0)
    total_viewed = Column(Integer, default=0)
    total_saved = Column(Integer, default=0)
    total_applied = Column(Integer, default=0)
    total_not_interested = Column(Integer, default=0)

    # Outcomes (subset of applied)
    total_responses = Column(Integer, default=0)
    total_interviews = Column(Integer, default=0)
    total_offers = Column(Integer, default=0)

    # Calculated rates
    click_through_rate = Column(Float)  # viewed / shown
    save_rate = Column(Float)  # saved / viewed
    apply_rate = Column(Float)  # applied / viewed
    response_rate = Column(Float)  # responses / applied

    # Average view duration
    avg_view_duration = Column(Float)

    # Timestamp
    calculated_at = Column(DateTime(timezone=True), server_default=func.now())


class CoachSession(Base):
    """Coach session tracking"""
    __tablename__ = "coach_sessions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), index=True, nullable=False)
    coach_id = Column(String(36), index=True)

    # Session details
    session_type = Column(String(50), default="chat")  # chat, video
    scheduled_start = Column(DateTime(timezone=True))
    scheduled_end = Column(DateTime(timezone=True))

    # Status
    status = Column(String(50), default="scheduled")  # scheduled, in_progress, completed, cancelled, no_show

    # Actual times
    actual_start = Column(DateTime(timezone=True))
    actual_end = Column(DateTime(timezone=True))
    duration_minutes = Column(Integer)

    # Feedback
    user_rating = Column(Integer)  # 1-5
    user_feedback = Column(Text)
    coach_notes = Column(Text)

    # Topics discussed (for analytics)
    topics = Column(JSON, default=list)  # resume, interview, salary, career_change, etc.

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
