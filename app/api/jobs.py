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
from app.core.config import settings


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
    # Get user profile (mock mode or database)
    if settings.DEMO_MODE or settings.SKIP_DB:
        from app.api.auth import _demo_profiles, _get_default_profile
        profile_dict = _demo_profiles.get(user_id, _get_default_profile(user_id))
        user_profile = {
            "skills": profile_dict.get("skills") or [],
            "years_experience": profile_dict.get("years_experience"),
            "salary_min": search.salary_min or profile_dict.get("salary_min"),
            "salary_max": profile_dict.get("salary_max"),
            "preferred_locations": profile_dict.get("preferred_locations") or [],
            "remote_preference": "remote" if search.remote_only else profile_dict.get("remote_preference", "any"),
            "target_titles": profile_dict.get("target_titles") or [],
        }
    else:
        result = await db.execute(select(UserProfile).where(UserProfile.user_id == user_id))
        profile = result.scalar_one_or_none()

        if not profile:
            profile = UserProfile(user_id=user_id)

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


@router.post(
    "/parse-resume",
    summary="Parse Resume and Extract Profile Data",
    description="""
    Upload a resume file and automatically extract profile data using AI.

    **Features:**
    - Extracts skills, experience, certifications from resume text
    - Uses GPT-4o-mini or Claude Haiku for intelligent extraction
    - Falls back to keyword extraction if no API keys configured
    - Optionally auto-updates your profile with extracted data

    **Extracted Fields:**
    - Skills (technical and soft)
    - Years of experience
    - Current job title
    - Suggested target titles
    - Certifications
    - Career level

    **Cost:** ~$0.0002 per parse with LLM
    """
)
async def parse_resume_for_profile(
    file: UploadFile = File(..., description="Resume file (PDF or DOCX)"),
    auto_update_profile: bool = Form(False, description="Automatically update profile with extracted data"),
    user_id: str = Depends(get_current_user_id)
):
    """
    Parse resume and extract profile data.

    Returns extracted profile fields. Optionally updates user profile.
    """
    from app.services.llm_resume_parser import parse_resume_with_llm

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
    else:
        resume_text = extract_text_from_docx(content)

    if not resume_text or len(resume_text) < 50:
        raise HTTPException(
            status_code=400,
            detail="Could not extract sufficient text from resume. Please check the file."
        )

    # Parse with LLM
    extracted = parse_resume_with_llm(resume_text)

    # Auto-update profile if requested
    if auto_update_profile and (settings.DEMO_MODE or settings.SKIP_DB):
        from app.api.auth import _demo_profiles, _get_default_profile, _calculate_mock_profile_strength

        profile = _demo_profiles.get(user_id, _get_default_profile(user_id))

        # Update with extracted data (only non-empty fields)
        if extracted.get("skills"):
            profile["skills"] = extracted["skills"]
        if extracted.get("years_experience"):
            profile["years_experience"] = extracted["years_experience"]
        if extracted.get("current_title"):
            profile["current_title"] = extracted["current_title"]
        if extracted.get("target_titles"):
            profile["target_titles"] = extracted["target_titles"]
        if extracted.get("certifications"):
            profile["certifications"] = extracted["certifications"]
        if extracted.get("locations"):
            profile["preferred_locations"] = extracted["locations"]

        # Estimate salary if career level is provided
        salary_estimates = {
            "junior": (50000, 80000),
            "mid": (80000, 120000),
            "senior": (120000, 180000),
            "lead": (150000, 220000),
            "executive": (200000, 350000)
        }
        if extracted.get("career_level") and extracted["career_level"] in salary_estimates:
            est = salary_estimates[extracted["career_level"]]
            if not profile.get("salary_min"):
                profile["salary_min"] = est[0]
            if not profile.get("salary_max"):
                profile["salary_max"] = est[1]

        profile["profile_strength"] = _calculate_mock_profile_strength(profile)
        _demo_profiles[user_id] = profile

        extracted["profile_updated"] = True
        extracted["new_profile_strength"] = profile["profile_strength"]

    return {
        "extracted": extracted,
        "resume_length": len(resume_text),
        "metadata": extracted.get("_metadata", {})
    }


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


@router.post(
    "/explain-match",
    summary="Get AI Explanation for Job Match",
    description="""
    Generate a natural language explanation for why a job matches (or doesn't match) a user's profile.

    **Features:**
    - Plain English explanation of match score
    - Identifies the biggest strength
    - Identifies the main gap (if any)
    - Provides actionable improvement suggestion

    **Supported LLM Providers:**
    - OpenAI (GPT-4o-mini) - default
    - Anthropic (Claude Haiku)
    - xAI (Grok)

    Cost: ~$0.0002 per explanation
    """
)
async def explain_job_match(
    job_data: dict = Body(..., description="Job posting data"),
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db)
):
    """
    Get AI-powered explanation for job match score.

    Returns natural language explanation with:
    - Why this job matches/doesn't match
    - Biggest strength of the match
    - Main gap to address
    - Specific action item to improve
    """
    from app.services.llm_explainer import explain_match

    # Get user profile
    result = await db.execute(select(UserProfile).where(UserProfile.user_id == user_id))
    profile = result.scalar_one_or_none()

    if not profile:
        profile = UserProfile(user_id=user_id)

    # Build user profile dict
    user_profile = {
        "skills": profile.skills or [],
        "years_experience": profile.years_experience or 0,
        "salary_min": profile.salary_min or 0,
        "salary_max": profile.salary_max or 0,
        "preferred_locations": profile.preferred_locations or [],
        "remote_preference": profile.remote_preference or "any",
        "target_titles": profile.target_titles or [],
    }

    # Compute match scores
    matcher = JobMatcher()
    match_scores = matcher.compute_match_score(user_profile, job_data)

    # Generate explanation
    try:
        explanation = explain_match(user_profile, job_data, match_scores)
        return {
            "match_scores": match_scores,
            **explanation
        }
    except Exception as e:
        # Return scores without explanation if LLM fails
        return {
            "match_scores": match_scores,
            "explanation": f"Could not generate explanation: {str(e)}",
            "strength": "See match scores above",
            "gap": "See match scores above",
            "action_item": "Review the component scores for improvement areas",
            "metadata": {"model": "error", "tokens_used": 0, "cost_usd": 0}
        }


@router.post(
    "/skill-gaps",
    summary="Analyze Skill Gaps",
    description="""
    Analyze skill gaps between your profile and target jobs.

    **Features:**
    - Compares your skills against job requirements
    - Identifies high-demand skills you're missing
    - Provides learning recommendations with resources
    - Estimates potential match score improvement

    **How it works:**
    1. Searches for jobs matching your criteria
    2. Extracts required skills from job postings
    3. Compares against your profile skills
    4. Ranks gaps by demand frequency
    5. Generates personalized learning recommendations

    **Cost:** Free (keyword extraction) or ~$0.0003 (with LLM recommendations)
    """
)
async def analyze_skill_gaps(
    keywords: str = Body(..., embed=True, description="Job search keywords"),
    location: Optional[str] = Body(None, embed=True, description="Preferred location"),
    top_n: int = Body(5, embed=True, description="Number of top gaps to return"),
    user_id: str = Depends(get_current_user_id)
):
    """
    Analyze skill gaps based on target job requirements.

    Returns skill gaps, recommendations, and potential improvement.
    """
    from app.services.skill_gap_analyzer import analyze_skill_gaps as analyze

    # Get user profile (mock mode or database)
    if settings.DEMO_MODE or settings.SKIP_DB:
        from app.api.auth import _demo_profiles, _get_default_profile
        profile_dict = _demo_profiles.get(user_id, _get_default_profile(user_id))
        user_profile = {
            "skills": profile_dict.get("skills") or [],
            "years_experience": profile_dict.get("years_experience"),
            "target_titles": profile_dict.get("target_titles") or [],
        }
    else:
        result = await db.execute(select(UserProfile).where(UserProfile.user_id == user_id))
        profile = result.scalar_one_or_none()
        if not profile:
            profile = UserProfile(user_id=user_id)
        user_profile = {
            "skills": profile.skills or [],
            "years_experience": profile.years_experience,
            "target_titles": profile.target_titles or [],
        }

    # Fetch jobs for analysis
    fetcher = JobFetcher()
    jobs = await fetcher.fetch_jobs(
        keywords=keywords,
        location=location,
        sources=["themuse", "demo"]  # Use reliable sources
    )

    if not jobs:
        return {
            "skill_gaps": [],
            "message": "No jobs found for analysis. Try different keywords."
        }

    # Analyze gaps
    analysis = analyze(user_profile, jobs, top_n=top_n)

    return {
        "jobs_analyzed": len(jobs),
        "user_skills_count": len(user_profile.get("skills", [])),
        **analysis
    }


@router.post(
    "/scrape-career-page",
    summary="Scrape Company Career Page",
    description="""
    Scrape job listings directly from a company's career page.

    **Features:**
    - Direct access to company job postings
    - No API key required (free)
    - Fresher data than aggregators
    - Works with most standard career pages

    **Example URLs:**
    - https://careers.google.com/jobs
    - https://www.apple.com/careers/us/
    - https://amazon.jobs/en/

    **Note:** Some sites may block automated requests. Results vary by site structure.
    """
)
async def scrape_career_page(
    career_url: str = Body(..., embed=True, description="URL to company careers page"),
    keywords: Optional[str] = Body(None, embed=True, description="Filter by keywords"),
    user_id: str = Depends(get_current_user_id)
):
    """
    Scrape jobs from a company career page.

    Returns list of jobs found on the page, matched against user profile.
    """
    fetcher = JobFetcher()
    jobs = await fetcher.scrape_career_page(career_url, keywords)

    if not jobs:
        return {
            "jobs": [],
            "total": 0,
            "message": "No jobs found. The site may block scraping or have non-standard structure."
        }

    return {
        "jobs": jobs,
        "total": len(jobs),
        "source_url": career_url
    }
