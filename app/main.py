"""
MatchForge - AI-Powered Job Matching Platform
Main FastAPI Application
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pathlib import Path

from app.core.config import settings
from app.core.database import init_db
from app.api import auth, jobs, feedback, coaching

# Create FastAPI app
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="""
    MatchForge - Smart Job Matching with Human Coaching

    ## Features
    - **AI-Powered Matching**: Multi-factor job matching using skills, experience, salary, and location
    - **ATS Optimization**: Resume compatibility checking for top ATS systems (iCIMS, Taleo, Workday, Greenhouse)
    - **Multiple Job Sources**: Aggregates from USAJobs, The Muse, and Adzuna APIs
    - **Feedback Loop**: Tracks user interactions to continuously improve matching
    - **Human Coaching**: Chat-based coaching sessions for personalized guidance

    ## MVP Scope
    This is an MVP implementation for a class project demonstrating:
    1. Job API integration with rate limiting
    2. Vector-based semantic matching
    3. ATS compatibility checking
    4. Feedback tracking for algorithm validation
    5. Real-time chat for coaching
    """,
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Startup event
@app.on_event("startup")
async def startup():
    """Initialize database on startup."""
    if not settings.DEMO_MODE:
        await init_db()


# Health check
@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "demo_mode": settings.DEMO_MODE
    }


# Include routers
app.include_router(auth.router, prefix=settings.API_V1_PREFIX)
app.include_router(jobs.router, prefix=settings.API_V1_PREFIX)
app.include_router(feedback.router, prefix=settings.API_V1_PREFIX)
app.include_router(coaching.router, prefix=settings.API_V1_PREFIX)


# Root endpoint
@app.get("/")
async def root():
    """Root endpoint with API info."""
    return {
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "docs": "/docs",
        "health": "/health",
        "demo": "/demo",
        "api_prefix": settings.API_V1_PREFIX,
        "endpoints": {
            "auth": f"{settings.API_V1_PREFIX}/auth",
            "jobs": f"{settings.API_V1_PREFIX}/jobs",
            "feedback": f"{settings.API_V1_PREFIX}/feedback",
            "coaching": f"{settings.API_V1_PREFIX}/coaching",
        }
    }


@app.get("/demo")
async def demo_page():
    """Serve the demo HTML page for ATS resume checking."""
    demo_path = Path(__file__).parent.parent / "demo.html"
    if demo_path.exists():
        return FileResponse(demo_path, media_type="text/html")
    return {"error": "Demo page not found"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG
    )
