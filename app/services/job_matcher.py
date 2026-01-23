"""
MatchForge Job Matcher Service
Multi-factor matching algorithm with vector similarity
"""
import numpy as np
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

# Lazy load sentence-transformers to speed up imports
_model = None


def get_model():
    """Lazy load the sentence transformer model"""
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer
        _model = SentenceTransformer('all-MiniLM-L6-v2')
    return _model


@dataclass
class MatchWeights:
    """
    Configurable weights for match scoring.
    Total should equal 1.0.
    """
    skills_semantic: float = 0.35      # Vector similarity of skills
    experience_level: float = 0.20     # Years of experience match
    salary_fit: float = 0.15           # Salary range overlap
    location_match: float = 0.15       # Location/remote preference
    title_similarity: float = 0.10     # Job title semantic match
    recency: float = 0.05              # How recent the posting is


DEFAULT_WEIGHTS = MatchWeights()


class JobMatcher:
    """
    Multi-factor job matching with vector similarity and rule-based filters.
    """

    def __init__(self, weights: MatchWeights = None):
        self.weights = weights or DEFAULT_WEIGHTS

    def compute_match_score(
        self,
        user_profile: dict,
        job: dict,
        weights: MatchWeights = None
    ) -> dict:
        """
        Compute comprehensive match score between user and job.

        Args:
            user_profile: User's profile data (skills, experience, preferences)
            job: Job listing data

        Returns:
            Dict with total_score (0-100) and component breakdown
        """
        weights = weights or self.weights
        scores = {}

        # 1. Skills semantic similarity (35%)
        scores['skills'] = self._compute_skills_match(
            user_profile.get('skills', []),
            job.get('description', ''),
            job.get('required_skills', [])
        )

        # 2. Experience level match (20%)
        scores['experience'] = self._compute_experience_match(
            user_profile.get('years_experience', 0),
            job.get('min_experience'),
            job.get('max_experience')
        )

        # 3. Salary fit (15%)
        scores['salary'] = self._compute_salary_match(
            user_profile.get('salary_min'),
            user_profile.get('salary_max'),
            job.get('salary_min'),
            job.get('salary_max')
        )

        # 4. Location match (15%)
        scores['location'] = self._compute_location_match(
            user_profile.get('preferred_locations', []),
            user_profile.get('remote_preference'),
            job.get('location'),
            job.get('is_remote')
        )

        # 5. Title similarity (10%)
        scores['title'] = self._compute_title_match(
            user_profile.get('target_titles', []),
            job.get('title', '')
        )

        # 6. Recency (5%)
        scores['recency'] = self._compute_recency_score(
            job.get('posted_date')
        )

        # Weighted total
        total = (
            scores['skills'] * weights.skills_semantic +
            scores['experience'] * weights.experience_level +
            scores['salary'] * weights.salary_fit +
            scores['location'] * weights.location_match +
            scores['title'] * weights.title_similarity +
            scores['recency'] * weights.recency
        )

        return {
            'total_score': round(total * 100),
            'components': {k: round(v * 100) for k, v in scores.items()},
            'weights_used': {k: v for k, v in weights.__dict__.items()}
        }

    def _compute_skills_match(
        self,
        user_skills: list[str],
        job_description: str,
        required_skills: list[str]
    ) -> float:
        """
        Semantic similarity between user skills and job requirements.
        """
        if not user_skills:
            return 0.5  # Neutral if no skills provided

        user_text = " ".join(user_skills)
        job_text = job_description
        if required_skills:
            job_text += " " + " ".join(required_skills)

        if not job_text.strip():
            return 0.5

        try:
            model = get_model()
            embeddings = model.encode([user_text, job_text])
            similarity = np.dot(embeddings[0], embeddings[1]) / (
                np.linalg.norm(embeddings[0]) * np.linalg.norm(embeddings[1])
            )
            return max(0, (similarity + 1) / 2)
        except Exception:
            # Fallback to keyword matching
            return self._keyword_match(user_skills, job_text)

    def _keyword_match(self, user_skills: list[str], job_text: str) -> float:
        """Fallback keyword matching if model fails"""
        if not user_skills or not job_text:
            return 0.5

        job_lower = job_text.lower()
        matches = sum(1 for skill in user_skills if skill.lower() in job_lower)
        return min(1.0, 0.3 + (matches / len(user_skills)) * 0.7)

    def _compute_experience_match(
        self,
        user_years: int,
        job_min: Optional[int],
        job_max: Optional[int]
    ) -> float:
        """Score based on experience level fit."""
        if job_min is None and job_max is None:
            return 0.7  # Neutral if not specified

        job_min = job_min or 0
        job_max = job_max or 30
        user_years = user_years or 0

        if job_min <= user_years <= job_max:
            return 1.0  # Perfect fit

        if user_years < job_min:
            gap = job_min - user_years
            return max(0.2, 1.0 - (gap * 0.15))

        # Over-qualified
        gap = user_years - job_max
        if gap <= 3:
            return 0.8
        elif gap <= 5:
            return 0.6
        return 0.5

    def _compute_salary_match(
        self,
        user_min: Optional[int],
        user_max: Optional[int],
        job_min: Optional[int],
        job_max: Optional[int]
    ) -> float:
        """Score based on salary range overlap."""
        if (user_min is None and user_max is None) or (job_min is None and job_max is None):
            return 0.7

        user_min = user_min or 0
        user_max = user_max or 500000
        job_min = job_min or 0
        job_max = job_max or 500000

        overlap_start = max(user_min, job_min)
        overlap_end = min(user_max, job_max)

        if overlap_start > overlap_end:
            if job_max < user_min:
                gap_pct = (user_min - job_max) / user_min
                return max(0.2, 1.0 - gap_pct)
            return 0.5

        user_range = user_max - user_min or 1
        overlap = overlap_end - overlap_start
        overlap_pct = overlap / user_range

        return min(1.0, 0.5 + (overlap_pct * 0.5))

    def _compute_location_match(
        self,
        preferred_locations: list[str],
        remote_preference: Optional[str],
        job_location: str,
        job_remote: bool
    ) -> float:
        """Score based on location and remote work preferences."""
        remote_preference = remote_preference or "any"

        if remote_preference == "remote":
            if job_remote:
                return 1.0
            return 0.3

        if remote_preference == "onsite":
            if job_remote:
                return 0.5

        if preferred_locations and job_location:
            job_loc_lower = job_location.lower()
            for pref in preferred_locations:
                if pref.lower() in job_loc_lower:
                    return 1.0
            return 0.5

        return 0.7

    def _compute_title_match(
        self,
        target_titles: list[str],
        job_title: str
    ) -> float:
        """Semantic similarity between target titles and job title."""
        if not target_titles or not job_title:
            return 0.7

        job_lower = job_title.lower()
        for title in target_titles:
            if title.lower() in job_lower or job_lower in title.lower():
                return 1.0

        try:
            model = get_model()
            targets_text = " ".join(target_titles)
            embeddings = model.encode([targets_text, job_title])
            similarity = np.dot(embeddings[0], embeddings[1]) / (
                np.linalg.norm(embeddings[0]) * np.linalg.norm(embeddings[1])
            )
            return max(0, (similarity + 1) / 2)
        except Exception:
            return 0.5

    def _compute_recency_score(self, posted_date: Optional[str]) -> float:
        """Score based on how recent the job posting is."""
        if not posted_date:
            return 0.5

        try:
            if isinstance(posted_date, str):
                for fmt in ["%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S.%fZ"]:
                    try:
                        posted = datetime.strptime(posted_date[:26], fmt)
                        break
                    except:
                        continue
                else:
                    return 0.5
            else:
                posted = posted_date

            days_old = (datetime.now() - posted).days

            if days_old <= 3:
                return 1.0
            elif days_old <= 7:
                return 0.9
            elif days_old <= 14:
                return 0.7
            elif days_old <= 30:
                return 0.5
            return 0.3

        except:
            return 0.5

    def rank_jobs(
        self,
        user_profile: dict,
        jobs: list[dict],
        min_score: int = 0
    ) -> list[dict]:
        """
        Rank jobs by match score.

        Args:
            user_profile: User profile data
            jobs: List of job dictings
            min_score: Minimum score threshold (0-100)

        Returns:
            List of jobs with match_scores, sorted by total_score descending
        """
        scored_jobs = []

        for job in jobs:
            scores = self.compute_match_score(user_profile, job)
            if scores['total_score'] >= min_score:
                scored_jobs.append({
                    **job,
                    'match_scores': scores
                })

        # Sort by total score descending
        scored_jobs.sort(key=lambda x: x['match_scores']['total_score'], reverse=True)

        return scored_jobs
