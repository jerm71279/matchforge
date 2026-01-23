"""
MatchForge Feedback API
Track user interactions for algorithm improvement
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user_id
from app.schemas.feedback import (
    ViewFeedback, SaveFeedback, ApplyFeedback,
    NotInterestedFeedback, OutcomeFeedback, RatingFeedback,
    FeedbackMetricsResponse
)
from app.services.feedback import FeedbackService

router = APIRouter(prefix="/feedback", tags=["Feedback"])


@router.post("/view")
async def record_view(
    feedback: ViewFeedback,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db)
):
    """
    Record that user viewed a job.
    Call when user opens job detail page.
    """
    service = FeedbackService(db)
    await service.record_view(
        user_id=user_id,
        job_id=feedback.job_id,
        match_score=0,  # Would get from job match
        duration_seconds=feedback.duration_seconds
    )
    return {"success": True}


@router.post("/save")
async def record_save(
    feedback: SaveFeedback,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db)
):
    """Record that user saved/unsaved a job."""
    service = FeedbackService(db)
    await service.record_save(
        user_id=user_id,
        job_id=feedback.job_id,
        match_score=0,
        saved=feedback.saved
    )
    return {"success": True}


@router.post("/apply")
async def record_apply(
    feedback: ApplyFeedback,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db)
):
    """Record that user applied to a job."""
    service = FeedbackService(db)
    await service.record_apply(
        user_id=user_id,
        job_id=feedback.job_id,
        match_score=0
    )
    return {"success": True}


@router.post("/not-interested")
async def record_not_interested(
    feedback: NotInterestedFeedback,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db)
):
    """
    Record that user marked job as not interested.
    Helps identify matching issues.
    """
    service = FeedbackService(db)
    await service.record_not_interested(
        user_id=user_id,
        job_id=feedback.job_id,
        match_score=0,
        reason=feedback.reason
    )
    return {"success": True}


@router.post("/outcome")
async def record_outcome(
    feedback: OutcomeFeedback,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db)
):
    """
    Record application outcome (if user reports it).

    Valid outcomes: response, interview, offer, rejection

    This is the most valuable feedback for validating
    that higher match scores lead to better outcomes.
    """
    service = FeedbackService(db)
    result = await service.record_outcome(
        user_id=user_id,
        job_id=feedback.job_id,
        outcome=feedback.outcome,
        notes=feedback.notes
    )

    if not result:
        raise HTTPException(status_code=404, detail="No feedback record found for this job")

    return {"success": True}


@router.post("/rating")
async def record_rating(
    feedback: RatingFeedback,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db)
):
    """Rate a job match (1-5 stars)."""
    service = FeedbackService(db)
    result = await service.record_rating(
        user_id=user_id,
        job_id=feedback.job_id,
        rating=feedback.rating
    )

    if not result:
        raise HTTPException(status_code=404, detail="No feedback record found")

    return {"success": True}


@router.get("/metrics", response_model=dict)
async def get_metrics(
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db)
):
    """
    Get aggregated feedback metrics by match score bucket.

    Used to validate algorithm effectiveness:
    - Higher scores should correlate with higher engagement
    - If 90-100 scores have lower CTR than 80-89, algorithm needs tuning

    Returns:
        Metrics for score buckets: 90-100, 80-89, 70-79, 60-69, <60
    """
    service = FeedbackService(db)
    metrics = await service.compute_metrics()
    return metrics
