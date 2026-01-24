# MatchForge Project Memory

## Project Overview
AI-powered job matching platform with human coaching - MVP for class project.

## Key Architecture Decisions
- FastAPI backend with layered architecture (API → Services → Models)
- Demo mode runs without database using in-memory mock sessions
- 6-factor job matching algorithm using sentence-transformers
- ATS checker supports 10 systems (~51% market coverage)
- Job aggregation from USAJobs, The Muse, Adzuna

## Running the App
```bash
# Demo mode (no database needed)
DEMO_MODE=true uvicorn app.main:app --port 8001 --reload

# Or via Docker
docker-compose up
```

## Running Tests
```bash
python -m pytest -v
```

## Conversation History
- **2026-01-23**: Initial build - full MVP created including job matching, ATS checker, coaching chat, feedback loop, demo UI, Docker support

## Notes for Future Sessions
-
