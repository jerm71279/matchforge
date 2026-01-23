"""
MatchForge Job Schemas
Request/response models for jobs and matching

Includes OpenAPI examples for Swagger documentation.
"""
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional
from datetime import datetime


class JobBase(BaseModel):
    """Base job fields."""
    title: str = Field(..., description="Job title", examples=["Senior DevOps Engineer"])
    company: Optional[str] = Field(None, description="Company name", examples=["TechCorp Industries"])
    location: Optional[str] = Field(None, description="Job location", examples=["Austin, TX"])
    is_remote: bool = Field(False, description="Whether the job is remote")
    salary_min: Optional[int] = Field(None, description="Minimum salary (USD)", examples=[120000])
    salary_max: Optional[int] = Field(None, description="Maximum salary (USD)", examples=[160000])
    description: Optional[str] = Field(None, description="Full job description")


class JobResponse(JobBase):
    """
    Job listing response.

    Contains complete job information from source APIs.
    """
    id: str = Field(..., description="Unique job identifier", examples=["demo_5"])
    source: str = Field(..., description="Job source API", examples=["usajobs", "themuse", "adzuna", "demo"])
    source_url: Optional[str] = Field(None, description="Link to original job posting")
    required_skills: list[str] = Field(default=[], description="Required skills for the position")
    preferred_skills: list[str] = Field(default=[], description="Nice-to-have skills")
    min_experience: Optional[int] = Field(None, description="Minimum years of experience", examples=[3])
    max_experience: Optional[int] = Field(None, description="Maximum years of experience", examples=[7])
    posted_date: Optional[datetime] = Field(None, description="When the job was posted")
    is_active: bool = Field(True, description="Whether the job is still active")

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": "demo_5",
                "source": "demo",
                "source_url": "https://example.com/jobs/demo_5",
                "title": "DevOps Engineer",
                "company": "StartupXYZ",
                "location": "Austin, TX",
                "is_remote": True,
                "salary_min": 125000,
                "salary_max": 155000,
                "description": "Build and maintain CI/CD pipelines for a fast-growing SaaS platform...",
                "required_skills": ["CI/CD", "Jenkins", "GitHub Actions", "Kubernetes", "Docker"],
                "preferred_skills": ["ArgoCD", "Helm", "Go", "Prometheus"],
                "min_experience": 3,
                "max_experience": 7,
                "posted_date": "2026-01-22T00:00:00Z",
                "is_active": True
            }
        }
    )


class JobMatchResponse(BaseModel):
    """
    Job match with scores.

    Includes match score breakdown showing how well the job matches the user's profile.
    Match scores range from 0-100, with higher scores indicating better matches.
    """
    job: JobResponse = Field(..., description="Job details")
    match_scores: dict = Field(
        ...,
        description="Match score breakdown: total_score (0-100) and component scores",
        examples=[{
            "total_score": 87,
            "components": {
                "skills": 92,
                "experience": 85,
                "salary": 90,
                "location": 100,
                "title": 78,
                "recency": 95
            }
        }]
    )
    ats_score: int = Field(..., description="ATS compatibility score (0-100)", examples=[85])
    ats_suggestions: list[str] = Field(
        default=[],
        description="ATS improvement suggestions",
        examples=[["Add 'Kubernetes' keyword", "Add 'CI/CD' keyword"]]
    )
    is_saved: bool = Field(False, description="Whether the user has saved this job")
    is_applied: bool = Field(False, description="Whether the user has applied to this job")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "job": {
                    "id": "demo_5",
                    "source": "demo",
                    "title": "DevOps Engineer",
                    "company": "StartupXYZ",
                    "location": "Austin, TX",
                    "is_remote": True,
                    "salary_min": 125000,
                    "salary_max": 155000,
                    "required_skills": ["CI/CD", "Kubernetes", "Docker"],
                    "min_experience": 3,
                    "max_experience": 7,
                    "is_active": True
                },
                "match_scores": {
                    "total_score": 87,
                    "components": {
                        "skills": 92,
                        "experience": 85,
                        "salary": 90,
                        "location": 100,
                        "title": 78,
                        "recency": 95
                    }
                },
                "ats_score": 85,
                "ats_suggestions": ["Add 'ArgoCD' keyword"],
                "is_saved": False,
                "is_applied": False
            }
        }
    )


class JobSearchRequest(BaseModel):
    """
    Job search parameters.

    Search across multiple job APIs with optional filters.
    Results are ranked by match score against your profile.
    """
    keywords: Optional[str] = Field(
        None,
        description="Search keywords (job title, skills, etc.)",
        examples=["DevOps Engineer", "Python developer", "cloud security"]
    )
    location: Optional[str] = Field(
        None,
        description="Location filter (city, state, or 'Remote')",
        examples=["Austin, TX", "Remote", "San Francisco, CA"]
    )
    remote_only: bool = Field(False, description="Only show remote jobs")
    salary_min: Optional[int] = Field(
        None,
        description="Minimum salary filter (USD)",
        examples=[100000]
    )
    sources: Optional[list[str]] = Field(
        None,
        description="Specific sources to search. Options: usajobs, themuse, adzuna, demo",
        examples=[["usajobs", "adzuna"]]
    )
    page: int = Field(1, ge=1, description="Page number (1-indexed)")
    page_size: int = Field(20, ge=1, le=100, description="Results per page (max 100)")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "keywords": "DevOps Engineer",
                "location": "Remote",
                "remote_only": True,
                "salary_min": 120000,
                "sources": ["demo"],
                "page": 1,
                "page_size": 20
            }
        }
    )


class JobSearchResponse(BaseModel):
    """
    Paginated job search results.

    Contains matched jobs ranked by match score, with pagination info.
    """
    jobs: list[JobMatchResponse] = Field(..., description="List of matched jobs")
    total: int = Field(..., description="Total number of matching jobs", examples=[45])
    page: int = Field(..., description="Current page number", examples=[1])
    page_size: int = Field(..., description="Results per page", examples=[20])
    sources_used: list[str] = Field(
        ...,
        description="Which job sources returned results",
        examples=[["demo", "usajobs"]]
    )


class SavedSearchCreate(BaseModel):
    """
    Create saved search.

    Save a search to receive email alerts when new matching jobs are posted.
    """
    keywords: Optional[str] = Field(None, description="Search keywords", examples=["Python developer"])
    location: Optional[str] = Field(None, description="Location filter", examples=["Remote"])
    remote_only: bool = Field(False, description="Only remote jobs")
    salary_min: Optional[int] = Field(None, description="Minimum salary", examples=[100000])
    alert_enabled: bool = Field(True, description="Enable email alerts")
    alert_frequency: str = Field(
        "daily",
        description="Alert frequency: daily, weekly, or immediate",
        examples=["daily", "weekly", "immediate"]
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "keywords": "DevOps Engineer",
                "location": "Remote",
                "remote_only": True,
                "salary_min": 120000,
                "alert_enabled": True,
                "alert_frequency": "daily"
            }
        }
    )


class SavedSearchResponse(BaseModel):
    """Saved search response."""
    id: str = Field(..., description="Saved search ID")
    keywords: Optional[str] = Field(None, description="Search keywords")
    location: Optional[str] = Field(None, description="Location filter")
    remote_only: bool = Field(False, description="Remote only filter")
    salary_min: Optional[int] = Field(None, description="Minimum salary filter")
    alert_enabled: bool = Field(True, description="Whether alerts are enabled")
    alert_frequency: str = Field("daily", description="Alert frequency")
    created_at: datetime = Field(..., description="When the search was created")
    last_run: Optional[datetime] = Field(None, description="Last time alerts were sent")

    model_config = ConfigDict(from_attributes=True)


class ATSCheckRequest(BaseModel):
    """
    ATS compatibility check request.

    Check your resume against top ATS systems.
    """
    resume_text: str = Field(
        ...,
        description="Full resume text content",
        examples=["John Smith\njohn@email.com\n\nWORK EXPERIENCE\nSenior Engineer at TechCorp..."]
    )
    resume_format: str = Field(
        "docx",
        description="Resume file format: docx, pdf, or txt",
        examples=["docx", "pdf"]
    )
    job_description: Optional[str] = Field(
        None,
        description="Target job description for keyword matching"
    )
    target_ats: Optional[str] = Field(
        None,
        description="Specific ATS to check against. Options: icims, taleo, workday, greenhouse, lever, smartrecruiters, adp, ceridian, successfactors, bullhorn",
        examples=["icims", "greenhouse"]
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "resume_text": "John Smith\njohn.smith@email.com | 555-123-4567\n\nPROFESSIONAL SUMMARY\nExperienced DevOps Engineer with 6 years...\n\nWORK EXPERIENCE\nSenior DevOps Engineer | TechCorp | 2021-Present\n- Designed Kubernetes clusters\n\nEDUCATION\nBS Computer Science, UC Berkeley\n\nSKILLS\nAWS, Kubernetes, Docker, Terraform, Jenkins",
                "resume_format": "docx",
                "job_description": "Seeking a DevOps Engineer with CI/CD experience...",
                "target_ats": "icims"
            }
        }
    )


class ATSCheckResult(BaseModel):
    """
    ATS compatibility check result.

    Shows compatibility score, issues found, and improvement suggestions.
    Targets top 10 ATS systems covering ~51% market share.
    """
    overall_score: int = Field(
        ...,
        ge=0,
        le=100,
        description="Overall ATS compatibility score (0-100)",
        examples=[78]
    )
    issues: list[dict] = Field(
        ...,
        description="List of issues found with severity, category, message, and suggestion",
        examples=[[
            {
                "severity": "warning",
                "category": "format",
                "message": "PDF format detected",
                "suggestion": "DOCX is preferred for maximum ATS compatibility."
            },
            {
                "severity": "info",
                "category": "keywords",
                "message": "Found acronyms without full forms",
                "suggestion": "Include both acronym and full term. Example: Amazon Web Services (AWS)"
            }
        ]]
    )
    suggestions: list[str] = Field(
        default=[],
        description="Keyword suggestions based on job description",
        examples=[["Add 'Kubernetes' (high priority)", "Add 'CI/CD' (medium priority)"]]
    )
    target_ats: Optional[str] = Field(
        None,
        description="The ATS system checked against",
        examples=["icims"]
    )
    parser_group: Optional[str] = Field(
        None,
        description="Parser group for the target ATS",
        examples=["legacy_strict", "modern_cloud", "hcm_integrated", "staffing_specific"]
    )
    market_coverage: Optional[str] = Field(
        None,
        description="Market share coverage of checked ATS",
        examples=["10.7%"]
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "overall_score": 78,
                "issues": [
                    {
                        "severity": "warning",
                        "category": "format",
                        "message": "PDF format detected",
                        "suggestion": "DOCX is preferred for maximum ATS compatibility."
                    },
                    {
                        "severity": "info",
                        "category": "content",
                        "message": "Multiple date formats: MM/YYYY, Month YYYY",
                        "suggestion": "Use consistent date formatting throughout."
                    }
                ],
                "suggestions": [
                    "Add 'Kubernetes' (high priority)",
                    "Add 'Terraform' (medium priority)"
                ],
                "target_ats": "icims",
                "parser_group": "legacy_strict",
                "market_coverage": "10.7%"
            }
        }
    )
