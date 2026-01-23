"""
MatchForge Feedback Schemas
Request/response models for feedback tracking
"""
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class ViewFeedback(BaseModel):
    """Record job view"""
    job_id: str
    duration_seconds: int = 0


class SaveFeedback(BaseModel):
    """Record job save/unsave"""
    job_id: str
    saved: bool = True


class ApplyFeedback(BaseModel):
    """Record job application"""
    job_id: str


class NotInterestedFeedback(BaseModel):
    """Record not interested"""
    job_id: str
    reason: Optional[str] = None  # salary, location, skills, company, other


class OutcomeFeedback(BaseModel):
    """Record application outcome"""
    job_id: str
    outcome: str  # response, interview, offer, rejection
    notes: Optional[str] = None


class RatingFeedback(BaseModel):
    """Rate a job match"""
    job_id: str
    rating: int = Field(..., ge=1, le=5)


class FeedbackMetricsResponse(BaseModel):
    """Feedback metrics by score bucket"""
    score_bucket: str
    total_shown: int
    click_through_rate: float
    save_rate: float
    apply_rate: float
    response_rate: Optional[float]
    avg_view_duration: float


class CoachSessionCreate(BaseModel):
    """Book coaching session"""
    coach_id: Optional[str] = None  # None = any available coach
    session_type: str = "chat"  # chat, video
    scheduled_start: datetime


class CoachSessionResponse(BaseModel):
    """Coaching session details"""
    id: str
    user_id: str
    coach_id: Optional[str]
    session_type: str
    scheduled_start: datetime
    scheduled_end: datetime
    status: str
    join_url: Optional[str]

    class Config:
        from_attributes = True


class CoachSessionFeedback(BaseModel):
    """Rate coaching session"""
    session_id: str
    rating: int = Field(..., ge=1, le=5)
    feedback: Optional[str] = None
