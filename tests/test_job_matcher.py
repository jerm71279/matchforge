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
            weights.skills +
            weights.experience +
            weights.salary +
            weights.location +
            weights.title +
            weights.recency
        )
        assert total == pytest.approx(1.0, rel=0.01)

    def test_skills_weight_is_35_percent(self):
        """Skills weight should be 35% per technical spec."""
        weights = MatchWeights()
        assert weights.skills == 0.35

    def test_experience_weight_is_20_percent(self):
        """Experience weight should be 20% per technical spec."""
        weights = MatchWeights()
        assert weights.experience == 0.20

    def test_salary_weight_is_15_percent(self):
        """Salary weight should be 15% per technical spec."""
        weights = MatchWeights()
        assert weights.salary == 0.15

    def test_location_weight_is_15_percent(self):
        """Location weight should be 15% per technical spec."""
        weights = MatchWeights()
        assert weights.location == 0.15

    def test_title_weight_is_10_percent(self):
        """Title weight should be 10% per technical spec."""
        weights = MatchWeights()
        assert weights.title == 0.10

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

    def test_match_jobs_returns_sorted_results(self, matcher, demo_jobs, sample_user_profile):
        """Should return jobs sorted by match score descending."""
        results = matcher.match_jobs(demo_jobs[:10], sample_user_profile)

        assert len(results) > 0
        scores = [r["match_score"] for r in results]
        assert scores == sorted(scores, reverse=True)

    def test_match_jobs_includes_score_breakdown(self, matcher, demo_jobs, sample_user_profile):
        """Should include score breakdown for each job."""
        results = matcher.match_jobs(demo_jobs[:5], sample_user_profile)

        for result in results:
            assert "match_score" in result
            assert "score_breakdown" in result
            breakdown = result["score_breakdown"]
            assert "skills" in breakdown
            assert "experience" in breakdown
            assert "salary" in breakdown
            assert "location" in breakdown
            assert "title" in breakdown

    def test_match_score_range(self, matcher, demo_jobs, sample_user_profile):
        """Match scores should be between 0 and 100."""
        results = matcher.match_jobs(demo_jobs, sample_user_profile)

        for result in results:
            assert 0 <= result["match_score"] <= 100


class TestSkillsMatching:
    """Test skills matching component."""

    @pytest.fixture
    def matcher(self):
        return JobMatcher()

    def test_exact_skill_match_scores_high(self, matcher):
        """Exact skill match should score highly."""
        job = {
            "required_skills": ["Python", "AWS", "Docker"],
            "preferred_skills": ["Kubernetes"],
        }
        profile = {
            "skills": ["Python", "AWS", "Docker", "Kubernetes"],
        }

        score = matcher._score_skills(job, profile)
        assert score > 0.8  # Should be high match

    def test_no_skill_match_scores_low(self, matcher):
        """No skill overlap should score low."""
        job = {
            "required_skills": ["Java", "Oracle", "Spring"],
            "preferred_skills": ["Maven"],
        }
        profile = {
            "skills": ["Python", "PostgreSQL", "FastAPI"],
        }

        score = matcher._score_skills(job, profile)
        assert score < 0.5  # Should be low match

    def test_partial_skill_match(self, matcher):
        """Partial skill overlap should score medium."""
        job = {
            "required_skills": ["Python", "AWS", "Java"],
            "preferred_skills": ["Docker"],
        }
        profile = {
            "skills": ["Python", "AWS", "Go"],
        }

        score = matcher._score_skills(job, profile)
        assert 0.4 < score < 0.9  # Medium match


class TestExperienceMatching:
    """Test experience matching component."""

    @pytest.fixture
    def matcher(self):
        return JobMatcher()

    def test_experience_in_range(self, matcher):
        """Experience within required range should score 1.0."""
        job = {"min_experience": 3, "max_experience": 7}
        profile = {"years_experience": 5}

        score = matcher._score_experience(job, profile)
        assert score == 1.0

    def test_experience_at_minimum(self, matcher):
        """Experience at minimum should score 1.0."""
        job = {"min_experience": 3, "max_experience": 7}
        profile = {"years_experience": 3}

        score = matcher._score_experience(job, profile)
        assert score == 1.0

    def test_experience_below_minimum(self, matcher):
        """Experience below minimum should score lower."""
        job = {"min_experience": 5, "max_experience": 10}
        profile = {"years_experience": 2}

        score = matcher._score_experience(job, profile)
        assert score < 1.0

    def test_experience_above_maximum(self, matcher):
        """Experience above maximum should score lower (overqualified)."""
        job = {"min_experience": 2, "max_experience": 5}
        profile = {"years_experience": 10}

        score = matcher._score_experience(job, profile)
        assert score < 1.0

    def test_experience_no_requirements(self, matcher):
        """No experience requirements should score 1.0."""
        job = {"min_experience": None, "max_experience": None}
        profile = {"years_experience": 5}

        score = matcher._score_experience(job, profile)
        assert score == 1.0


class TestSalaryMatching:
    """Test salary matching component."""

    @pytest.fixture
    def matcher(self):
        return JobMatcher()

    def test_salary_range_overlap(self, matcher):
        """Overlapping salary ranges should score well."""
        job = {"salary_min": 100000, "salary_max": 150000}
        profile = {"salary_min": 120000, "salary_max": 160000}

        score = matcher._score_salary(job, profile)
        assert score > 0.5  # Good overlap

    def test_salary_no_overlap(self, matcher):
        """Non-overlapping salary ranges should score low."""
        job = {"salary_min": 50000, "salary_max": 70000}
        profile = {"salary_min": 100000, "salary_max": 120000}

        score = matcher._score_salary(job, profile)
        assert score < 0.5  # Poor match

    def test_salary_job_no_salary_info(self, matcher):
        """Job without salary info should score neutral."""
        job = {"salary_min": None, "salary_max": None}
        profile = {"salary_min": 100000, "salary_max": 120000}

        score = matcher._score_salary(job, profile)
        assert score == 0.5  # Neutral


class TestLocationMatching:
    """Test location matching component."""

    @pytest.fixture
    def matcher(self):
        return JobMatcher()

    def test_remote_job_remote_preferred(self, matcher):
        """Remote job with remote preference should score 1.0."""
        job = {"is_remote": True, "location": "Remote"}
        profile = {"open_to_remote": True, "locations": []}

        score = matcher._score_location(job, profile)
        assert score == 1.0

    def test_exact_location_match(self, matcher):
        """Exact location match should score 1.0."""
        job = {"is_remote": False, "location": "Austin, TX"}
        profile = {"open_to_remote": False, "locations": ["Austin, TX"]}

        score = matcher._score_location(job, profile)
        assert score == 1.0

    def test_no_location_match(self, matcher):
        """No location match and not remote should score low."""
        job = {"is_remote": False, "location": "New York, NY"}
        profile = {"open_to_remote": False, "locations": ["San Francisco, CA"]}

        score = matcher._score_location(job, profile)
        assert score < 0.5


class TestTitleMatching:
    """Test title matching component."""

    @pytest.fixture
    def matcher(self):
        return JobMatcher()

    def test_exact_title_match(self, matcher):
        """Exact title match should score very high."""
        job = {"title": "DevOps Engineer"}
        profile = {"target_title": "DevOps Engineer"}

        score = matcher._score_title(job, profile)
        assert score > 0.9

    def test_similar_title_match(self, matcher):
        """Similar title should score well."""
        job = {"title": "Senior DevOps Engineer"}
        profile = {"target_title": "DevOps Engineer"}

        score = matcher._score_title(job, profile)
        assert score > 0.7

    def test_different_title(self, matcher):
        """Very different title should score low."""
        job = {"title": "Marketing Manager"}
        profile = {"target_title": "DevOps Engineer"}

        score = matcher._score_title(job, profile)
        assert score < 0.5


class TestDemoDatasetMatching:
    """Integration tests using full demo dataset."""

    @pytest.fixture
    def matcher(self):
        return JobMatcher()

    def test_devops_profile_matches_devops_jobs(self, matcher, demo_jobs):
        """DevOps profile should rank DevOps jobs highest."""
        profile = {
            "target_title": "DevOps Engineer",
            "skills": ["Kubernetes", "Docker", "AWS", "Terraform", "CI/CD", "Jenkins"],
            "years_experience": 5,
            "salary_min": 120000,
            "salary_max": 160000,
            "locations": ["Remote", "Austin, TX"],
            "open_to_remote": True,
        }

        results = matcher.match_jobs(demo_jobs, profile)

        # Top results should include DevOps-related jobs
        top_5_titles = [r["title"].lower() for r in results[:5]]
        devops_related = sum(
            1 for t in top_5_titles
            if "devops" in t or "sre" in t or "platform" in t or "infrastructure" in t
        )
        assert devops_related >= 2, f"Expected DevOps jobs in top 5, got: {top_5_titles}"

    def test_entry_level_profile_avoids_senior_roles(self, matcher, demo_jobs):
        """Entry-level profile should not highly rank senior roles."""
        profile = {
            "target_title": "Software Developer",
            "skills": ["Python", "JavaScript", "Git"],
            "years_experience": 1,
            "salary_min": 60000,
            "salary_max": 90000,
            "locations": ["Remote"],
            "open_to_remote": True,
        }

        results = matcher.match_jobs(demo_jobs, profile)

        # Top results should not be senior/director level
        top_5_titles = [r["title"].lower() for r in results[:5]]
        senior_count = sum(
            1 for t in top_5_titles
            if "senior" in t or "director" in t or "lead" in t or "architect" in t
        )
        assert senior_count <= 2, f"Too many senior roles for entry-level: {top_5_titles}"

    def test_security_profile_matches_security_jobs(self, matcher, demo_jobs):
        """Security profile should rank security jobs highly."""
        profile = {
            "target_title": "Security Engineer",
            "skills": ["SIEM", "Incident Response", "Network Security", "Python", "AWS Security"],
            "years_experience": 4,
            "salary_min": 100000,
            "salary_max": 150000,
            "locations": ["Remote"],
            "open_to_remote": True,
        }

        results = matcher.match_jobs(demo_jobs, profile)

        # Top results should include security-related jobs
        top_10_titles = [r["title"].lower() for r in results[:10]]
        security_related = sum(
            1 for t in top_10_titles
            if "security" in t or "cyber" in t or "penetration" in t or "soc" in t
        )
        assert security_related >= 3, f"Expected security jobs in top 10, got: {top_10_titles}"
