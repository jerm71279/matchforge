"""
Integration tests for JobFetcher service.
Tests demo mode functionality using the 50-job demo dataset.
"""
import pytest
from app.services.job_fetcher import JobFetcher, RateLimiter, RATE_LIMITS


class TestRateLimits:
    """Test rate limit configurations match verified data."""

    def test_usajobs_rate_limit(self):
        """USAJobs: 10,000 rows per query per day."""
        config = RATE_LIMITS["usajobs"]
        assert config.requests_per_period == 10000
        assert config.period_seconds == 86400  # 1 day

    def test_themuse_rate_limit(self):
        """The Muse: 3,600 requests per hour."""
        config = RATE_LIMITS["themuse"]
        assert config.requests_per_period == 3600
        assert config.period_seconds == 3600  # 1 hour

    def test_adzuna_rate_limit(self):
        """Adzuna: 25 requests per minute (1,500/hour)."""
        config = RATE_LIMITS["adzuna"]
        assert config.requests_per_period == 1500
        assert config.period_seconds == 3600  # 1 hour
        # Verify 25/min calculation
        assert config.requests_per_period / (config.period_seconds / 60) == 25

    def test_jsearch_rate_limit(self):
        """JSearch: 200 requests per month (free tier)."""
        config = RATE_LIMITS["jsearch"]
        assert config.requests_per_period == 200
        assert config.period_seconds == 2592000  # 30 days


class TestJobFetcherDemo:
    """Test JobFetcher in demo mode."""

    @pytest.fixture
    def fetcher(self):
        """Create fetcher without Redis (demo mode)."""
        return JobFetcher(redis_client=None)

    @pytest.mark.asyncio
    async def test_fetch_demo_jobs_no_filter(self, fetcher, demo_jobs, monkeypatch):
        """Should return all demo jobs when no filter applied."""
        # Force demo mode
        monkeypatch.setattr("app.services.job_fetcher.settings.DEMO_MODE", True)

        jobs = await fetcher.fetch_jobs(keywords="", location=None)

        assert len(jobs) == len(demo_jobs)
        assert all("id" in job for job in jobs)
        assert all("title" in job for job in jobs)

    @pytest.mark.asyncio
    async def test_fetch_demo_jobs_keyword_filter(self, fetcher, monkeypatch):
        """Should filter jobs by keyword in title, description, or skills."""
        monkeypatch.setattr("app.services.job_fetcher.settings.DEMO_MODE", True)

        jobs = await fetcher.fetch_jobs(keywords="DevOps", location=None)

        assert len(jobs) > 0
        for job in jobs:
            match_found = (
                "devops" in job.get("title", "").lower() or
                "devops" in job.get("description", "").lower() or
                any("devops" in skill.lower() for skill in job.get("required_skills", []))
            )
            assert match_found, f"Job {job['title']} doesn't match 'DevOps' filter"

    @pytest.mark.asyncio
    async def test_fetch_demo_jobs_location_filter(self, fetcher, monkeypatch):
        """Should filter jobs by location, including remote."""
        monkeypatch.setattr("app.services.job_fetcher.settings.DEMO_MODE", True)

        jobs = await fetcher.fetch_jobs(keywords="", location="Austin")

        assert len(jobs) > 0
        for job in jobs:
            location_match = (
                "austin" in job.get("location", "").lower() or
                job.get("is_remote", False)
            )
            assert location_match, f"Job in {job['location']} doesn't match Austin filter"

    @pytest.mark.asyncio
    async def test_fetch_demo_jobs_combined_filter(self, fetcher, monkeypatch):
        """Should filter by both keyword and location."""
        monkeypatch.setattr("app.services.job_fetcher.settings.DEMO_MODE", True)

        jobs = await fetcher.fetch_jobs(keywords="Python", location="Remote")

        assert len(jobs) > 0
        for job in jobs:
            # Must match Python AND be remote
            keyword_match = (
                "python" in job.get("title", "").lower() or
                "python" in job.get("description", "").lower() or
                any("python" in skill.lower() for skill in job.get("required_skills", []))
            )
            location_match = job.get("is_remote", False) or "remote" in job.get("location", "").lower()
            assert keyword_match and location_match


class TestJobDeduplication:
    """Test job deduplication logic."""

    def test_deduplicate_removes_duplicates(self):
        """Should remove jobs with same title + company."""
        fetcher = JobFetcher(redis_client=None)

        jobs = [
            {"id": "1", "title": "Software Engineer", "company": "TechCorp"},
            {"id": "2", "title": "Software Engineer", "company": "TechCorp"},  # Duplicate
            {"id": "3", "title": "Software Engineer", "company": "OtherCorp"},  # Different company
        ]

        result = fetcher._deduplicate(jobs)

        assert len(result) == 2
        assert result[0]["id"] == "1"
        assert result[1]["id"] == "3"

    def test_deduplicate_case_insensitive(self):
        """Should treat different cases as same job."""
        fetcher = JobFetcher(redis_client=None)

        jobs = [
            {"id": "1", "title": "Software Engineer", "company": "TechCorp"},
            {"id": "2", "title": "SOFTWARE ENGINEER", "company": "TECHCORP"},  # Same, different case
        ]

        result = fetcher._deduplicate(jobs)

        assert len(result) == 1

    def test_deduplicate_handles_empty_fields(self):
        """Should handle jobs with empty title or company."""
        fetcher = JobFetcher(redis_client=None)

        jobs = [
            {"id": "1", "title": "", "company": "TechCorp"},
            {"id": "2", "title": "Engineer", "company": ""},
            {"id": "3", "title": "", "company": ""},
        ]

        result = fetcher._deduplicate(jobs)

        # All should be kept as they have different combinations
        assert len(result) == 3


class TestSalaryParsing:
    """Test salary parsing logic."""

    def test_parse_salary_integer(self):
        """Should parse integer salary."""
        fetcher = JobFetcher(redis_client=None)
        assert fetcher._parse_salary(100000) == 100000

    def test_parse_salary_string(self):
        """Should parse string salary."""
        fetcher = JobFetcher(redis_client=None)
        assert fetcher._parse_salary("100000") == 100000

    def test_parse_salary_with_formatting(self):
        """Should parse salary with commas and dollar sign."""
        fetcher = JobFetcher(redis_client=None)
        assert fetcher._parse_salary("$100,000") == 100000

    def test_parse_salary_none(self):
        """Should return None for empty value."""
        fetcher = JobFetcher(redis_client=None)
        assert fetcher._parse_salary(None) is None
        assert fetcher._parse_salary("") is None

    def test_parse_salary_invalid(self):
        """Should return None for invalid value."""
        fetcher = JobFetcher(redis_client=None)
        assert fetcher._parse_salary("negotiable") is None
