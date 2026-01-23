"""
MatchForge Feedback Service
Track user interactions to measure and improve match quality
"""
from datetime import datetime
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, func

from app.models.feedback import MatchFeedback, FeedbackMetrics


class FeedbackService:
    """
    Collects and analyzes match feedback to improve algorithm.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def record_view(
        self,
        user_id: str,
        job_id: str,
        match_score: int,
        duration_seconds: int = 0
    ) -> MatchFeedback:
        """Record that user viewed a job."""
        feedback = await self._get_or_create(user_id, job_id, match_score)

        feedback.viewed = True
        feedback.view_count = (feedback.view_count or 0) + 1
        feedback.view_duration_seconds = (feedback.view_duration_seconds or 0) + duration_seconds
        feedback.last_viewed_at = datetime.utcnow()

        if not feedback.first_viewed_at:
            feedback.first_viewed_at = datetime.utcnow()

        self.db.add(feedback)
        await self.db.flush()
        return feedback

    async def record_save(
        self,
        user_id: str,
        job_id: str,
        match_score: int,
        saved: bool = True
    ) -> MatchFeedback:
        """Record that user saved/unsaved a job."""
        feedback = await self._get_or_create(user_id, job_id, match_score)

        feedback.saved = saved
        if saved:
            feedback.saved_at = datetime.utcnow()

        self.db.add(feedback)
        await self.db.flush()
        return feedback

    async def record_apply(
        self,
        user_id: str,
        job_id: str,
        match_score: int
    ) -> MatchFeedback:
        """Record that user applied to a job."""
        feedback = await self._get_or_create(user_id, job_id, match_score)

        feedback.applied = True
        feedback.applied_at = datetime.utcnow()

        self.db.add(feedback)
        await self.db.flush()
        return feedback

    async def record_not_interested(
        self,
        user_id: str,
        job_id: str,
        match_score: int,
        reason: Optional[str] = None
    ) -> MatchFeedback:
        """Record that user marked job as not interested."""
        feedback = await self._get_or_create(user_id, job_id, match_score)

        feedback.not_interested = True
        feedback.not_interested_reason = reason

        self.db.add(feedback)
        await self.db.flush()
        return feedback

    async def record_outcome(
        self,
        user_id: str,
        job_id: str,
        outcome: str,
        notes: Optional[str] = None
    ) -> Optional[MatchFeedback]:
        """
        Record application outcome.
        outcome: response, interview, offer, rejection
        """
        result = await self.db.execute(
            select(MatchFeedback).where(
                MatchFeedback.user_id == user_id,
                MatchFeedback.job_id == job_id
            )
        )
        feedback = result.scalar_one_or_none()

        if not feedback:
            return None

        if outcome == "response":
            feedback.got_response = True
        elif outcome == "interview":
            feedback.got_response = True
            feedback.got_interview = True
        elif outcome == "offer":
            feedback.got_response = True
            feedback.got_interview = True
            feedback.got_offer = True

        feedback.outcome_notes = notes
        feedback.outcome_reported_at = datetime.utcnow()

        self.db.add(feedback)
        await self.db.flush()
        return feedback

    async def record_rating(
        self,
        user_id: str,
        job_id: str,
        rating: int
    ) -> Optional[MatchFeedback]:
        """Record user's rating of a job match (1-5)."""
        result = await self.db.execute(
            select(MatchFeedback).where(
                MatchFeedback.user_id == user_id,
                MatchFeedback.job_id == job_id
            )
        )
        feedback = result.scalar_one_or_none()

        if feedback:
            feedback.user_rating = rating
            self.db.add(feedback)
            await self.db.flush()

        return feedback

    async def get_user_feedback(self, user_id: str, limit: int = 100) -> list[MatchFeedback]:
        """Get all feedback for a user."""
        result = await self.db.execute(
            select(MatchFeedback)
            .where(MatchFeedback.user_id == user_id)
            .order_by(MatchFeedback.created_at.desc())
            .limit(limit)
        )
        return result.scalars().all()

    async def compute_metrics(self) -> dict:
        """
        Compute aggregate metrics to evaluate match quality.

        Returns metrics by score bucket to validate algorithm:
        - Higher scores should have higher engagement
        - If not, algorithm needs adjustment
        """
        buckets = ["90-100", "80-89", "70-79", "60-69", "<60"]
        metrics = {}

        for bucket in buckets:
            if bucket == "90-100":
                min_score, max_score = 90, 100
            elif bucket == "80-89":
                min_score, max_score = 80, 89
            elif bucket == "70-79":
                min_score, max_score = 70, 79
            elif bucket == "60-69":
                min_score, max_score = 60, 69
            else:
                min_score, max_score = 0, 59

            result = await self.db.execute(
                select(
                    func.count(MatchFeedback.id).label('total'),
                    func.sum(func.cast(MatchFeedback.viewed, Integer)).label('viewed'),
                    func.sum(func.cast(MatchFeedback.saved, Integer)).label('saved'),
                    func.sum(func.cast(MatchFeedback.applied, Integer)).label('applied'),
                    func.sum(func.cast(MatchFeedback.got_response, Integer)).label('responses'),
                    func.avg(MatchFeedback.view_duration_seconds).label('avg_duration'),
                )
                .where(
                    MatchFeedback.match_score >= min_score,
                    MatchFeedback.match_score <= max_score
                )
            )
            row = result.one()

            total = row.total or 1
            viewed = row.viewed or 0
            saved = row.saved or 0
            applied = row.applied or 0
            responses = row.responses or 0

            metrics[bucket] = {
                "total_shown": total,
                "click_through_rate": viewed / total,
                "save_rate": saved / max(viewed, 1),
                "apply_rate": applied / max(viewed, 1),
                "response_rate": responses / max(applied, 1) if applied else None,
                "avg_view_duration": row.avg_duration or 0,
            }

        return metrics

    async def _get_or_create(
        self,
        user_id: str,
        job_id: str,
        match_score: int
    ) -> MatchFeedback:
        """Get existing feedback or create new."""
        result = await self.db.execute(
            select(MatchFeedback).where(
                MatchFeedback.user_id == user_id,
                MatchFeedback.job_id == job_id
            )
        )
        feedback = result.scalar_one_or_none()

        if not feedback:
            feedback = MatchFeedback(
                user_id=user_id,
                job_id=job_id,
                match_score=match_score
            )

        return feedback


# Import Integer for SQL cast (add at top with other imports)
from sqlalchemy import Integer
