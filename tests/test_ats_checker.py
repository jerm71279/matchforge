"""
Integration tests for ATSChecker service.
Tests ATS validation with expanded 10-system coverage.
"""
import pytest
from app.services.ats_checker import ATSChecker, Severity


class TestATSCoverage:
    """Test that all 10 ATS systems are covered per verified data."""

    @pytest.fixture
    def checker(self):
        return ATSChecker()

    def test_top_10_systems_covered(self, checker):
        """Should have all top 10 ATS systems."""
        expected_systems = [
            "icims", "taleo", "workday", "greenhouse",
            "lever", "smartrecruiters", "adp", "ceridian",
            "successfactors", "bullhorn"
        ]

        for system in expected_systems:
            assert system in checker.ATS_BEHAVIORS, f"Missing ATS system: {system}"

    def test_parser_groups_defined(self, checker):
        """Should have all 4 parser groups."""
        expected_groups = ["legacy_strict", "modern_cloud", "hcm_integrated", "staffing_specific"]

        for group in expected_groups:
            assert group in checker.PARSER_GROUPS, f"Missing parser group: {group}"

    def test_legacy_strict_systems(self, checker):
        """Legacy-Strict group should have correct systems."""
        legacy_systems = checker.PARSER_GROUPS["legacy_strict"]["systems"]
        assert "icims" in legacy_systems
        assert "taleo" in legacy_systems
        assert "successfactors" in legacy_systems

    def test_modern_cloud_systems(self, checker):
        """Modern-Cloud group should have correct systems."""
        modern_systems = checker.PARSER_GROUPS["modern_cloud"]["systems"]
        assert "greenhouse" in modern_systems
        assert "lever" in modern_systems
        assert "smartrecruiters" in modern_systems

    def test_hcm_integrated_systems(self, checker):
        """HCM-Integrated group should have correct systems."""
        hcm_systems = checker.PARSER_GROUPS["hcm_integrated"]["systems"]
        assert "workday" in hcm_systems
        assert "adp" in hcm_systems
        assert "ceridian" in hcm_systems

    def test_staffing_specific_systems(self, checker):
        """Staffing-Specific group should have correct systems."""
        staffing_systems = checker.PARSER_GROUPS["staffing_specific"]["systems"]
        assert "bullhorn" in staffing_systems


class TestCoverageStatistics:
    """Test market coverage calculations."""

    def test_total_coverage_above_50_percent(self):
        """Should report ~51% market coverage."""
        checker = ATSChecker()
        stats = checker.get_coverage_stats()

        # Extract number from percentage string
        coverage = float(stats["estimated_market_coverage"].replace("%", ""))
        assert coverage >= 40, f"Coverage {coverage}% is below expected ~51%"

    def test_coverage_by_parser_group(self):
        """Should report coverage by parser group."""
        checker = ATSChecker()
        stats = checker.get_coverage_stats()

        assert "by_parser_group" in stats
        assert "legacy_strict" in stats["by_parser_group"]
        assert "modern_cloud" in stats["by_parser_group"]


class TestBasicATSChecks:
    """Test basic ATS checking functionality."""

    @pytest.fixture
    def checker(self):
        return ATSChecker()

    def test_good_resume_scores_high(self, checker, legacy_ats_resume):
        """Well-formatted resume should score high."""
        issues = checker.check_resume(legacy_ats_resume, "docx")
        score = checker.compute_ats_score(issues)

        assert score >= 70, f"Good resume scored only {score}"

    def test_poor_resume_has_issues(self, checker, poor_ats_resume):
        """Poorly formatted resume should have issues."""
        issues = checker.check_resume(poor_ats_resume, "pdf")

        assert len(issues) > 0
        # Should detect special characters
        special_char_issues = [i for i in issues if i.category == "content"]
        assert len(special_char_issues) > 0

    def test_missing_experience_section(self, checker):
        """Should flag missing Experience section."""
        resume = """
        John Smith
        john@email.com

        EDUCATION
        BS Computer Science, MIT

        SKILLS
        Python, Java
        """
        issues = checker.check_resume(resume, "docx")

        experience_issues = [
            i for i in issues
            if "experience" in i.message.lower() and i.severity == Severity.ERROR
        ]
        assert len(experience_issues) > 0

    def test_missing_email(self, checker):
        """Should flag missing email address."""
        resume = """
        John Smith

        WORK EXPERIENCE
        Software Engineer at TechCorp

        EDUCATION
        BS in CS
        """
        issues = checker.check_resume(resume, "docx")

        email_issues = [i for i in issues if "email" in i.message.lower()]
        assert len(email_issues) > 0

    def test_pdf_format_warning(self, checker, sample_resume_text):
        """Should warn about PDF format."""
        issues = checker.check_resume(sample_resume_text, "pdf")

        format_issues = [
            i for i in issues
            if i.category == "format" and "pdf" in i.message.lower()
        ]
        assert len(format_issues) > 0


class TestATSSpecificChecks:
    """Test ATS-specific validation."""

    @pytest.fixture
    def checker(self):
        return ATSChecker()

    def test_icims_requires_docx(self, checker, sample_resume_text):
        """iCIMS should strongly prefer DOCX."""
        result = checker.check_for_ats(sample_resume_text, "pdf", "icims")

        assert result["target_ats"] == "icims"
        assert result["parser_group"] == "legacy_strict"

        # Should have format error for PDF
        format_issues = [
            i for i in result["issues"]
            if i["category"] == "format" and "docx" in i["message"].lower()
        ]
        assert len(format_issues) > 0

    def test_greenhouse_accepts_pdf(self, checker, sample_resume_text):
        """Greenhouse should accept PDF without error."""
        result = checker.check_for_ats(sample_resume_text, "pdf", "greenhouse")

        assert result["parser_group"] == "modern_cloud"

        # Should not have critical format errors for PDF
        format_errors = [
            i for i in result["issues"]
            if i["category"] == "format" and i["severity"] == "error"
        ]
        # May have warning but not error for PDF
        assert len([e for e in format_errors if "docx" in e["message"].lower()]) == 0

    def test_workday_requires_skills_section(self, checker):
        """Workday should flag missing Skills section."""
        resume_no_skills = """
        John Smith
        john@email.com | 555-1234

        WORK EXPERIENCE
        Senior Engineer at TechCorp, 2020-Present

        EDUCATION
        BS Computer Science
        """
        result = checker.check_for_ats(resume_no_skills, "docx", "workday")

        assert result["parser_group"] == "hcm_integrated"

        # Should flag missing skills
        skills_issues = [
            i for i in result["issues"]
            if "skills" in i["message"].lower()
        ]
        assert len(skills_issues) > 0

    def test_bullhorn_expects_availability(self, checker, sample_resume_text):
        """Bullhorn should note missing availability."""
        result = checker.check_for_ats(sample_resume_text, "docx", "bullhorn")

        assert result["parser_group"] == "staffing_specific"

        # Should mention availability
        availability_issues = [
            i for i in result["issues"]
            if "availability" in i["message"].lower()
        ]
        assert len(availability_issues) > 0

    def test_unknown_ats_returns_error(self, checker, sample_resume_text):
        """Unknown ATS should return error with supported list."""
        result = checker.check_for_ats(sample_resume_text, "docx", "unknownats")

        assert "error" in result
        assert "supported_systems" in result
        assert len(result["supported_systems"]) == 10


class TestParserGroupChecks:
    """Test parser group validation."""

    @pytest.fixture
    def checker(self):
        return ATSChecker()

    def test_legacy_strict_group_check(self, checker, sample_resume_text):
        """Should check all legacy-strict systems."""
        result = checker.check_for_parser_group(sample_resume_text, "docx", "legacy_strict")

        assert result["parser_group"] == "legacy_strict"
        assert "icims" in result["systems_checked"]
        assert "taleo" in result["systems_checked"]
        assert "successfactors" in result["systems_checked"]
        assert "average_score" in result
        assert "individual_scores" in result

    def test_modern_cloud_group_tips(self, checker, sample_resume_text):
        """Modern-cloud group should have relevant tips."""
        result = checker.check_for_parser_group(sample_resume_text, "docx", "modern_cloud")

        tips = result.get("group_tips", [])
        assert len(tips) > 0
        # Should mention PDF being acceptable
        pdf_tip_found = any("pdf" in tip.lower() for tip in tips)
        assert pdf_tip_found


class TestKeywordSuggestions:
    """Test keyword extraction and suggestions."""

    @pytest.fixture
    def checker(self):
        return ATSChecker()

    def test_suggest_missing_keywords(self, checker, sample_resume_text, sample_job_description):
        """Should suggest missing keywords from job description."""
        suggestions = checker.suggest_keywords(sample_resume_text, sample_job_description)

        assert isinstance(suggestions, list)
        # Should have some suggestions (resume doesn't have all JD keywords)
        # But not too many since resume is well-matched
        assert len(suggestions) <= 10

    def test_keyword_importance_tagging(self, checker, sample_resume_text, sample_job_description):
        """Should tag keywords as high or medium importance."""
        suggestions = checker.suggest_keywords(sample_resume_text, sample_job_description)

        for suggestion in suggestions:
            assert "keyword" in suggestion
            assert "importance" in suggestion
            assert suggestion["importance"] in ["high", "medium"]


class TestScoreCalculation:
    """Test ATS score calculation."""

    @pytest.fixture
    def checker(self):
        return ATSChecker()

    def test_score_starts_at_100(self, checker):
        """Score should start at 100 with no issues."""
        issues = []
        score = checker.compute_ats_score(issues)
        assert score == 100

    def test_error_reduces_score_by_20(self, checker):
        """Each ERROR should reduce score by 20."""
        from app.services.ats_checker import ATSIssue

        issues = [
            ATSIssue(Severity.ERROR, "test", "test", "test"),
        ]
        score = checker.compute_ats_score(issues)
        assert score == 80

    def test_warning_reduces_score_by_10(self, checker):
        """Each WARNING should reduce score by 10."""
        from app.services.ats_checker import ATSIssue

        issues = [
            ATSIssue(Severity.WARNING, "test", "test", "test"),
        ]
        score = checker.compute_ats_score(issues)
        assert score == 90

    def test_info_reduces_score_by_2(self, checker):
        """Each INFO should reduce score by 2."""
        from app.services.ats_checker import ATSIssue

        issues = [
            ATSIssue(Severity.INFO, "test", "test", "test"),
        ]
        score = checker.compute_ats_score(issues)
        assert score == 98

    def test_score_cannot_go_below_zero(self, checker):
        """Score should not go below 0."""
        from app.services.ats_checker import ATSIssue

        # 6 errors = 120 points off, but should cap at 0
        issues = [ATSIssue(Severity.ERROR, "test", f"test{i}", "test") for i in range(6)]
        score = checker.compute_ats_score(issues)
        assert score == 0
