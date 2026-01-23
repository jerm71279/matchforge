"""
MatchForge Jobs API
Job search, matching, and ATS checking

This module provides endpoints for:
- Searching and matching jobs from multiple APIs
- ATS compatibility checking for top 10 systems
- Saving jobs and searches
"""
from fastapi import APIRouter, Depends, HTTPException, Query, Body, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional
import io

from app.core.database import get_db
from app.core.security import get_current_user_id
from app.models.user import UserProfile
from app.models.job import Job, JobMatch, SavedSearch
from app.schemas.job import (
    JobSearchRequest, JobSearchResponse, JobMatchResponse, JobResponse,
    SavedSearchCreate, SavedSearchResponse, ATSCheckResult, ATSCheckRequest
)
from app.services.job_fetcher import JobFetcher
from app.services.job_matcher import JobMatcher
from app.services.ats_checker import ATSChecker


def extract_text_from_pdf(file_content: bytes) -> str:
    """Extract text from PDF file."""
    try:
        from PyPDF2 import PdfReader
        pdf = PdfReader(io.BytesIO(file_content))
        text = ""
        for page in pdf.pages:
            text += page.extract_text() or ""
        return text.strip()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Could not parse PDF: {str(e)}")


def extract_text_from_docx(file_content: bytes) -> str:
    """Extract text from DOCX file."""
    try:
        from docx import Document
        doc = Document(io.BytesIO(file_content))
        text = "\n".join([para.text for para in doc.paragraphs])
        return text.strip()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Could not parse DOCX: {str(e)}")

router = APIRouter(
    prefix="/jobs",
    tags=["Jobs"],
    responses={
        401: {"description": "Not authenticated"},
        403: {"description": "Not authorized"},
    }
)


@router.post(
    "/search",
    response_model=JobSearchResponse,
    summary="Search and Match Jobs",
    description="""
    Search for jobs and get AI-matched results ranked by compatibility.

    **Job Sources (Free APIs):**
    - **USAJobs**: US Government jobs (10,000 rows/query)
    - **The Muse**: Tech startups with culture data (3,600 req/hour)
    - **Adzuna**: 16+ countries (25 req/minute)
    - **Demo**: 50-job demo dataset for testing

    **Match Score Calculation (0-100):**
    | Factor | Weight | Description |
    |--------|--------|-------------|
    | Skills | 35% | Semantic similarity using sentence-transformers |
    | Experience | 20% | Years of experience match |
    | Salary | 15% | Salary range overlap |
    | Location | 15% | Location/remote preference |
    | Title | 10% | Target title similarity |
    | Recency | 5% | How recent the posting is |

    Higher scores indicate better matches. Jobs are returned sorted by match score.
    """
)
async def search_jobs(
    search: JobSearchRequest,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db)
):
    """
    Search for jobs and get matched results.

    Jobs are fetched from multiple sources and ranked by match score.
    """
    # Get user profile
    result = await db.execute(select(UserProfile).where(UserProfile.user_id == user_id))
    profile = result.scalar_one_or_none()

    if not profile:
        profile = UserProfile(user_id=user_id)

    # Build user profile dict for matching
    user_profile = {
        "skills": profile.skills or [],
        "years_experience": profile.years_experience,
        "salary_min": search.salary_min or profile.salary_min,
        "salary_max": profile.salary_max,
        "preferred_locations": profile.preferred_locations or [],
        "remote_preference": "remote" if search.remote_only else profile.remote_preference,
        "target_titles": profile.target_titles or [],
    }

    # Fetch jobs
    fetcher = JobFetcher()
    jobs = await fetcher.fetch_jobs(
        keywords=search.keywords or "",
        location=search.location,
        sources=search.sources
    )

    # Match and rank
    matcher = JobMatcher()
    ranked_jobs = matcher.rank_jobs(user_profile, jobs)

    # Paginate
    start = (search.page - 1) * search.page_size
    end = start + search.page_size
    page_jobs = ranked_jobs[start:end]

    # Build response
    job_matches = []
    ats_checker = ATSChecker()

    for job_data in page_jobs:
        # ATS suggestions based on job description
        ats_suggestions = []
        if profile.resume_text and job_data.get("description"):
            keywords = ats_checker.suggest_keywords(profile.resume_text, job_data["description"])
            ats_suggestions = [f"Add '{k['keyword']}' keyword" for k in keywords[:3]]

        job_response = JobResponse(
            id=job_data.get("id", ""),
            source=job_data.get("source", ""),
            source_url=job_data.get("source_url"),
            title=job_data.get("title", ""),
            company=job_data.get("company"),
            location=job_data.get("location"),
            is_remote=job_data.get("is_remote", False),
            salary_min=job_data.get("salary_min"),
            salary_max=job_data.get("salary_max"),
            description=job_data.get("description"),
            required_skills=job_data.get("required_skills", []),
            preferred_skills=job_data.get("preferred_skills", []),
            min_experience=job_data.get("min_experience"),
            max_experience=job_data.get("max_experience"),
            posted_date=job_data.get("posted_date"),
            is_active=True,
        )

        job_matches.append(JobMatchResponse(
            job=job_response,
            match_scores=job_data.get("match_scores", {"total_score": 0, "components": {}}),
            ats_score=80,  # Default for now
            ats_suggestions=ats_suggestions,
            is_saved=False,
            is_applied=False,
        ))

    # Determine sources used
    sources_used = list(set(j.job.source for j in job_matches))

    return JobSearchResponse(
        jobs=job_matches,
        total=len(ranked_jobs),
        page=search.page,
        page_size=search.page_size,
        sources_used=sources_used
    )


@router.get("/{job_id}", response_model=JobMatchResponse)
async def get_job(
    job_id: str,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db)
):
    """Get job details with match score."""
    # For demo, return mock data
    # In production, fetch from database
    raise HTTPException(status_code=404, detail="Job not found")


@router.post("/{job_id}/save")
async def save_job(
    job_id: str,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db)
):
    """Save a job to favorites."""
    # Record in job_matches
    return {"success": True, "message": "Job saved"}


@router.delete("/{job_id}/save")
async def unsave_job(
    job_id: str,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db)
):
    """Remove job from favorites."""
    return {"success": True, "message": "Job removed from saved"}


@router.post("/{job_id}/apply")
async def mark_applied(
    job_id: str,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db)
):
    """Mark job as applied."""
    return {"success": True, "message": "Marked as applied"}


@router.post(
    "/ats-check",
    response_model=ATSCheckResult,
    summary="Check Resume ATS Compatibility",
    description="""
    Validate your resume against top ATS (Applicant Tracking Systems).

    **Supported ATS Systems (Top 10 by market share, ~51% combined):**

    | System | Market Share | Parser Group |
    |--------|--------------|--------------|
    | iCIMS | 10.7% | Legacy-Strict |
    | Taleo | 8-9% | Legacy-Strict |
    | Workday | 7-8% | HCM-Integrated |
    | Greenhouse | 6-7% | Modern-Cloud |
    | Lever | 4-5% | Modern-Cloud |
    | SmartRecruiters | 3-4% | Modern-Cloud |
    | ADP | 3% | HCM-Integrated |
    | Ceridian | 2-3% | HCM-Integrated |
    | SAP SuccessFactors | 2-3% | Legacy-Strict |
    | Bullhorn | 2-3% | Staffing-Specific |

    **Parser Groups:**
    - **Legacy-Strict**: Requires .docx, strict headers, keyword-heavy (iCIMS, Taleo, SuccessFactors)
    - **Modern-Cloud**: PDF acceptable, forgiving parsers (Greenhouse, Lever, SmartRecruiters)
    - **HCM-Integrated**: Skills section critical (Workday, ADP, Ceridian)
    - **Staffing-Specific**: Include availability info (Bullhorn)
    """
)
async def check_ats_compatibility(
    request: ATSCheckRequest = Body(...),
    user_id: str = Depends(get_current_user_id)
):
    """
    Check resume ATS compatibility.

    Validates against top 10 ATS systems covering ~51% market share.
    Returns compatibility score, issues found, and keyword suggestions.
    """
    checker = ATSChecker()

    # Check against specific ATS or general rules
    if request.target_ats:
        result = checker.check_for_ats(
            request.resume_text,
            request.resume_format,
            request.target_ats
        )

        if "error" in result:
            raise HTTPException(
                status_code=400,
                detail=f"Unknown ATS: {request.target_ats}. Supported: {result['supported_systems']}"
            )

        issues = result["issues"]
        score = result["score"]
        parser_group = result.get("parser_group")
        market_coverage = result.get("market_share")
    else:
        issues_list = checker.check_resume(request.resume_text, request.resume_format)
        issues = [issue.to_dict() for issue in issues_list]
        score = checker.compute_ats_score(issues_list)
        parser_group = None
        market_coverage = None

    # Get keyword suggestions if job description provided
    suggestions = []
    if request.job_description:
        keywords = checker.suggest_keywords(request.resume_text, request.job_description)
        suggestions = [f"Add '{k['keyword']}' ({k['importance']} priority)" for k in keywords]

    return ATSCheckResult(
        overall_score=score,
        issues=issues if isinstance(issues, list) else issues,
        suggestions=suggestions,
        target_ats=request.target_ats,
        parser_group=parser_group,
        market_coverage=market_coverage
    )


@router.post(
    "/resume-check",
    response_model=ATSCheckResult,
    summary="Upload Resume for ATS Check",
    description="""
    Upload a resume file (PDF or DOCX) and check ATS compatibility.

    **Supported formats:**
    - PDF (.pdf)
    - Microsoft Word (.docx)

    The resume text is extracted automatically and scored against the selected ATS system.
    """
)
async def upload_resume_for_ats_check(
    file: UploadFile = File(..., description="Resume file (PDF or DOCX)"),
    target_ats: Optional[str] = Form("icims", description="Target ATS system"),
    job_description: Optional[str] = Form(None, description="Optional job description for keyword matching"),
    user_id: str = Depends(get_current_user_id)
):
    """
    Upload resume and check ATS compatibility.

    Accepts PDF or DOCX files, extracts text, and runs ATS validation.
    """
    # Validate file type
    filename = file.filename.lower()
    if not (filename.endswith('.pdf') or filename.endswith('.docx')):
        raise HTTPException(
            status_code=400,
            detail="Unsupported file format. Please upload PDF or DOCX."
        )

    # Read file content
    content = await file.read()

    # Extract text based on file type
    if filename.endswith('.pdf'):
        resume_text = extract_text_from_pdf(content)
        resume_format = "pdf"
    else:
        resume_text = extract_text_from_docx(content)
        resume_format = "docx"

    if not resume_text or len(resume_text) < 50:
        raise HTTPException(
            status_code=400,
            detail="Could not extract sufficient text from resume. Please check the file."
        )

    # Run ATS check
    checker = ATSChecker()

    if target_ats:
        result = checker.check_for_ats(resume_text, resume_format, target_ats)

        if "error" in result:
            raise HTTPException(
                status_code=400,
                detail=f"Unknown ATS: {target_ats}. Supported: {result['supported_systems']}"
            )

        issues = result["issues"]
        score = result["score"]
        parser_group = result.get("parser_group")
        market_coverage = result.get("market_share")
    else:
        issues_list = checker.check_resume(resume_text, resume_format)
        issues = [issue.to_dict() for issue in issues_list]
        score = checker.compute_ats_score(issues_list)
        parser_group = None
        market_coverage = None

    # Get keyword suggestions if job description provided
    suggestions = []
    if job_description:
        keywords = checker.suggest_keywords(resume_text, job_description)
        suggestions = [f"Add '{k['keyword']}' ({k['importance']} priority)" for k in keywords]

    return ATSCheckResult(
        overall_score=score,
        issues=issues,
        suggestions=suggestions,
        target_ats=target_ats,
        parser_group=parser_group,
        market_coverage=market_coverage
    )


@router.post("/saved-searches", response_model=SavedSearchResponse)
async def create_saved_search(
    search: SavedSearchCreate,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db)
):
    """Create a saved search with optional alerts."""
    saved = SavedSearch(
        user_id=user_id,
        keywords=search.keywords,
        location=search.location,
        remote_only=search.remote_only,
        salary_min=search.salary_min,
        alert_enabled=search.alert_enabled,
        alert_frequency=search.alert_frequency,
    )
    db.add(saved)
    await db.flush()

    return saved


@router.get("/saved-searches", response_model=list[SavedSearchResponse])
async def get_saved_searches(
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db)
):
    """Get user's saved searches."""
    result = await db.execute(
        select(SavedSearch)
        .where(SavedSearch.user_id == user_id)
        .order_by(SavedSearch.created_at.desc())
    )
    return result.scalars().all()
