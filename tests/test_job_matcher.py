"""
Integration tests for JobMatcher service.
Tests matching algorithm with demo dataset.
"""
import pytest
from app.services.job_matcher import JobMatcher, MatchWeights


class TestMatchWeights:
    """Test matching weight configuration matches technical spec."""

    def test_weights_sum_to_100(self):
        """Weights should sum to 100% (1.0)."""
        weights = MatchWeights()
        total = (
            weights.skills_semantic +
            weights.experience_level +
            weights.salary_fit +
            weights.location_match +
            weights.title_similarity +
            weights.recency
        )
        assert total == pytest.approx(1.0, rel=0.01)

    def test_skills_weight_is_35_percent(self):
        """Skills weight should be 35% per technical spec."""
        weights = MatchWeights()
        assert weights.skills_semantic == 0.35

    def test_experience_weight_is_20_percent(self):
        """Experience weight should be 20% per technical spec."""
        weights = MatchWeights()
        assert weights.experience_level == 0.20

    def test_salary_weight_is_15_percent(self):
        """Salary weight should be 15% per technical spec."""
        weights = MatchWeights()
        assert weights.salary_fit == 0.15

    def test_location_weight_is_15_percent(self):
        """Location weight should be 15% per technical spec."""
        weights = MatchWeights()
        assert weights.location_match == 0.15

    def test_title_weight_is_10_percent(self):
        """Title weight should be 10% per technical spec."""
        weights = MatchWeights()
        assert weights.title_similarity == 0.10

    def test_recency_weight_is_5_percent(self):
        """Recency weight should be 5% per technical spec."""
        weights = MatchWeights()
        assert weights.recency == 0.05


class TestJobMatcherBasics:
    """Test basic JobMatcher functionality."""

    @pytest.fixture
    def matcher(self):
        """Create matcher instance."""
        return JobMatcher()

    def test_rank_jobs_returns_sorted_results(self, matcher, demo_jobs, sample_user_profile):
        """Should return jobs sorted by match score descending."""
        results = matcher.rank_jobs(sample_user_profile, demo_jobs[:10])

        assert len(results) > 0
        scores = [r["match_scores"]["total_score"] for r in results]
        assert scores == sorted(scores, reverse=True)

    def test_rank_jobs_includes_score_breakdown(self, matcher, demo_jobs, sample_user_profile):
        """Should include score breakdown for each job."""
        results = matcher.rank_jobs(sample_user_profile, demo_jobs[:5])

        for result in results:
            assert "match_scores" in result
            scores = result["match_scores"]
            assert "total_score" in scores
            assert "components" in scores
            components = scores["components"]
            assert "skills" in components
            assert "experience" in components
            assert "salary" in components
            assert "location" in components
            assert "title" in components

    def test_match_score_range(self, matcher, demo_jobs, sample_user_profile):
        """Match scores should be between 0 and 100."""
        results = matcher.rank_jobs(sample_user_profile, demo_jobs)

        for result in results:
            assert 0 <= result["match_scores"]["total_score"] <= 100


class TestSkillsMatching:
    """Test skills matching component."""

    @pytest.fixture
    def matcher(self):
        return JobMatcher()

    def test_exact_skill_match_scores_high(self, matcher):
        """Exact skill match should score reasonably with keyword matching."""
        job = {
            "description": "Looking for Python and AWS experience with Docker skills",
            "required_skills": ["Python", "AWS", "Docker"],
        }
        profile = {
            "skills": ["Python", "AWS", "Docker", "Kubernetes"],
        }

        score = matcher._compute_skills_match(
            profile["skills"],
            job["description"],
            job["required_skills"]
        )
        assert score > 0.5  # Should match well

    def test_no_skill_match_scores_low(self, matcher):
        """No skill overlap should score lower."""
        job = {
            "description": "Java and Oracle Spring development",
            "required_skills": ["Java", "Oracle", "Spring"],
        }
        profile = {
            "skills": ["Python", "PostgreSQL", "FastAPI"],
        }

        score = matcher._compute_skills_match(
            profile["skills"],
            job["description"],
            job["required_skills"]
        )
        # Will be 0.5 neutral or lower depending on matching
        assert score <= 0.6


class TestExperienceMatching:
    """Test experience matching component."""

    @pytest.fixture
    def matcher(self):
        return JobMatcher()

    def test_experience_in_range(self, matcher):
        """Experience within required range should score 1.0."""
        score = matcher._compute_experience_match(5, 3, 7)
        assert score == 1.0

    def test_experience_at_minimum(self, matcher):
        """Experience at minimum should score 1.0."""
        score = matcher._compute_experience_match(3, 3, 7)
        assert score == 1.0

    def test_experience_below_minimum(self, matcher):
        """Experience below minimum should score lower."""
        score = matcher._compute_experience_match(2, 5, 10)
        assert score < 1.0

    def test_experience_above_maximum(self, matcher):
        """Experience above maximum should score lower (overqualified)."""
        score = matcher._compute_experience_match(10, 2, 5)
        assert score < 1.0

    def test_experience_no_requirements(self, matcher):
        """No experience requirements should score neutral (0.7)."""
        score = matcher._compute_experience_match(5, None, None)
        assert score == 0.7


class TestSalaryMatching:
    """Test salary matching component."""

    @pytest.fixture
    def matcher(self):
        return JobMatcher()

    def test_salary_range_overlap(self, matcher):
        """Overlapping salary ranges should score well."""
        score = matcher._compute_salary_match(120000, 160000, 100000, 150000)
        assert score > 0.5  # Good overlap

    def test_salary_no_overlap(self, matcher):
        """Non-overlapping salary ranges should score lower."""
        score = matcher._compute_salary_match(100000, 120000, 50000, 70000)
        assert score < 0.8  # Some penalty for gap

    def test_salary_job_no_salary_info(self, matcher):
        """Job without salary info should score neutral (0.7)."""
        score = matcher._compute_salary_match(100000, 120000, None, None)
        assert score == 0.7


class TestLocationMatching:
    """Test location matching component."""

    @pytest.fixture
    def matcher(self):
        return JobMatcher()

    def test_remote_job_remote_preferred(self, matcher):
        """Remote job with remote preference should score 1.0."""
        score = matcher._compute_location_match([], "remote", "Remote", True)
        assert score == 1.0

    def test_exact_location_match(self, matcher):
        """Exact location match should score 1.0."""
        score = matcher._compute_location_match(["Austin, TX"], "any", "Austin, TX", False)
        assert score == 1.0

    def test_no_location_match(self, matcher):
        """No location match and not remote should score lower."""
        score = matcher._compute_location_match(["San Francisco, CA"], "onsite", "New York, NY", False)
        assert score < 1.0


class TestTitleMatching:
    """Test title matching component."""

    @pytest.fixture
    def matcher(self):
        return JobMatcher()

    def test_exact_title_match(self, matcher):
        """Exact title match should score 1.0."""
        score = matcher._compute_title_match(["DevOps Engineer"], "DevOps Engineer")
        assert score == 1.0

    def test_partial_title_match(self, matcher):
        """Partial title match should score 1.0."""
        score = matcher._compute_title_match(["DevOps Engineer"], "Senior DevOps Engineer")
        assert score == 1.0  # Contains the target title

    def test_no_title_provided(self, matcher):
        """No target title should score neutral (0.7)."""
        score = matcher._compute_title_match([], "DevOps Engineer")
        assert score == 0.7


class TestDemoDatasetMatching:
    """Integration tests using full demo dataset."""

    @pytest.fixture
    def matcher(self):
        return JobMatcher()

    def test_devops_profile_matches_devops_jobs(self, matcher, demo_jobs):
        """DevOps profile should rank DevOps jobs highly."""
        profile = {
            "target_titles": ["DevOps Engineer"],
            "skills": ["Kubernetes", "Docker", "AWS", "Terraform", "CI/CD", "Jenkins"],
            "years_experience": 5,
            "salary_min": 120000,
            "salary_max": 160000,
            "preferred_locations": ["Remote", "Austin, TX"],
            "remote_preference": "remote",
        }

        results = matcher.rank_jobs(profile, demo_jobs)

        # Should have results
        assert len(results) > 0

        # Top results should have decent scores
        top_5_scores = [r["match_scores"]["total_score"] for r in results[:5]]
        assert all(s >= 40 for s in top_5_scores), f"Top 5 scores too low: {top_5_scores}"

    def test_entry_level_profile_matching(self, matcher, demo_jobs):
        """Entry-level profile should find appropriate matches."""
        profile = {
            "target_titles": ["Software Developer", "Junior Developer"],
            "skills": ["Python", "JavaScript", "Git"],
            "years_experience": 1,
            "salary_min": 60000,
            "salary_max": 90000,
            "preferred_locations": ["Remote"],
            "remote_preference": "remote",
        }

        results = matcher.rank_jobs(profile, demo_jobs)

        # Should have results
        assert len(results) > 0

    def test_security_profile_matches_security_jobs(self, matcher, demo_jobs):
        """Security profile should find security-related jobs."""
        profile = {
            "target_titles": ["Security Engineer", "Security Analyst"],
            "skills": ["SIEM", "Incident Response", "Network Security", "Python", "AWS Security"],
            "years_experience": 4,
            "salary_min": 100000,
            "salary_max": 150000,
            "preferred_locations": ["Remote"],
            "remote_preference": "remote",
        }

        results = matcher.rank_jobs(profile, demo_jobs)

        # Should have results
        assert len(results) > 0

        # Look for security-related jobs in top results
        top_10_titles = [r["title"].lower() for r in results[:10]]
        security_related = sum(
            1 for t in top_10_titles
            if "security" in t or "cyber" in t or "penetration" in t or "soc" in t
        )
        # At least some security jobs should be in top 10
        assert security_related >= 1, f"Expected security jobs in top 10, got: {top_10_titles}"
