# MatchForge MVP

AI-Powered Job Matching Platform with Human Coaching

## Features

- **AI-Powered Matching**: Multi-factor job matching using skills, experience, salary, and location (vector similarity with sentence-transformers)
- **ATS Optimization**: Resume compatibility checking for top ATS systems (iCIMS, Taleo, Workday, Greenhouse)
- **Multiple Job Sources**: Aggregates from USAJobs, The Muse, and Adzuna APIs
- **Feedback Tracking**: Tracks user interactions to validate and improve matching algorithm
- **Human Coaching**: Real-time chat for coaching sessions

## Quick Start

### Option 1: Docker (Recommended for Teams)

```bash
# Clone and run with one command
git clone https://github.com/jerm71279/matchforge.git
cd matchforge
docker-compose up
```

Open http://localhost:8001/demo - that's it!

### Option 2: Local Python Setup

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run with demo data (no database needed)
DEMO_MODE=true uvicorn app.main:app --port 8001 --reload
```

**Windows users:** See [Team Setup](#team-setup) section for Windows-specific commands.

Visit http://localhost:8001/docs for API documentation.

### Demo UI

**Linux/Mac:**
```bash
DEMO_MODE=true uvicorn app.main:app --port 8001 --reload
```

**Windows (PowerShell):**
```powershell
$env:DEMO_MODE="true"; uvicorn app.main:app --port 8001 --reload
```

Then open http://localhost:8001/demo in your browser.

The demo UI includes:
- **ATS Checker** - Upload resume (PDF/DOCX) and check compatibility
- **Find Jobs** - Search with real API sources (The Muse works without keys)
- **Coaching** - Book sessions and chat with coaches via WebSocket

Default login: `demo@matchforge.com` / `DemoPass123`

### Full Setup

```bash
# Copy environment file
cp .env.example .env

# Edit .env with your credentials (optional - demo mode works without them)

# Start PostgreSQL and Redis (or use Docker)
docker-compose up -d

# Run migrations
alembic upgrade head

# Start server
uvicorn app.main:app --reload
```

## API Endpoints

### Authentication
- `POST /api/v1/auth/register` - Create account
- `POST /api/v1/auth/login` - Get access token
- `GET /api/v1/auth/me` - Get current user
- `GET /api/v1/auth/profile` - Get job matching profile
- `PUT /api/v1/auth/profile` - Update profile

### Jobs
- `POST /api/v1/jobs/search` - Search and match jobs
- `GET /api/v1/jobs/{id}` - Get job details
- `POST /api/v1/jobs/{id}/save` - Save job
- `POST /api/v1/jobs/{id}/apply` - Mark as applied
- `POST /api/v1/jobs/ats-check` - Check ATS compatibility

### Feedback
- `POST /api/v1/feedback/view` - Record job view
- `POST /api/v1/feedback/save` - Record save/unsave
- `POST /api/v1/feedback/apply` - Record application
- `POST /api/v1/feedback/outcome` - Record outcome (response/interview/offer)
- `GET /api/v1/feedback/metrics` - Get algorithm validation metrics

### Coaching
- `GET /api/v1/coaching/slots` - Get available slots
- `POST /api/v1/coaching/book` - Book session
- `GET /api/v1/coaching/sessions` - Get user's sessions
- `WS /api/v1/coaching/chat/{session_id}` - Real-time chat

## Project Structure

```
matchforge/
├── app/
│   ├── api/
│   │   ├── auth.py         # Authentication endpoints
│   │   ├── jobs.py         # Job search and matching
│   │   ├── feedback.py     # Feedback tracking
│   │   └── coaching.py     # Coaching and chat
│   ├── core/
│   │   ├── config.py       # Settings management
│   │   ├── database.py     # Database setup
│   │   └── security.py     # JWT authentication
│   ├── models/
│   │   ├── user.py         # User models
│   │   ├── job.py          # Job models
│   │   └── feedback.py     # Feedback models
│   ├── schemas/
│   │   ├── auth.py         # Auth schemas
│   │   ├── job.py          # Job schemas
│   │   └── feedback.py     # Feedback schemas
│   ├── services/
│   │   ├── job_fetcher.py  # API integrations
│   │   ├── job_matcher.py  # Matching algorithm
│   │   ├── ats_checker.py  # ATS validation
│   │   ├── feedback.py     # Feedback service
│   │   └── chat.py         # Chat service
│   └── main.py             # FastAPI application
├── data/
│   └── demo_jobs.json      # 50-job demo dataset
├── requirements.txt
└── .env.example
```

## Matching Algorithm

Jobs are scored on 6 factors:

| Factor | Weight | Description |
|--------|--------|-------------|
| Skills | 35% | Semantic similarity using sentence-transformers |
| Experience | 20% | Years of experience match |
| Salary | 15% | Salary range overlap |
| Location | 15% | Location/remote preference |
| Title | 10% | Target title similarity |
| Recency | 5% | How recent the posting is |

## Feedback Loop

The system tracks implicit and explicit signals to validate matching:

- **Implicit**: Views, view duration, saves, applications
- **Explicit**: Ratings, not-interested reasons, outcomes (response/interview/offer)

Metrics are computed by score bucket (90-100, 80-89, etc.) to verify that higher match scores correlate with better engagement.

## Class Project Notes

This is an MVP implementation for a class project demonstrating:
1. Multi-source job API integration with rate limiting
2. Vector-based semantic matching
3. ATS compatibility validation
4. Feedback tracking for algorithm validation
5. Real-time WebSocket chat

Financial projections and business model are theoretical for educational purposes.

## Testing

### Run All Tests

```bash
# Install test dependencies
pip install pytest pytest-asyncio httpx

# Run tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=app --cov-report=html
```

### Test Individual Components

```bash
# ATS Checker tests
pytest tests/test_ats_checker.py -v

# Job Matcher tests
pytest tests/test_job_matcher.py -v

# Feedback tracking tests
pytest tests/test_feedback.py -v

# Job Fetcher tests
pytest tests/test_job_fetcher.py -v
```

### Manual Testing with Demo UI

1. Start server:
   - **Linux/Mac:** `DEMO_MODE=true uvicorn app.main:app --port 8001 --reload`
   - **Windows (PowerShell):** `$env:DEMO_MODE="true"; uvicorn app.main:app --port 8001 --reload`
   - **Windows (CMD):** `set DEMO_MODE=true && uvicorn app.main:app --port 8001 --reload`
2. Open http://localhost:8001/demo
3. Login with demo credentials
4. Test each feature:
   - **ATS Tab**: Upload a resume PDF/DOCX, select ATS system, check score
   - **Jobs Tab**: Select "The Muse" source, search for "Engineer", verify real jobs appear
   - **Coaching Tab**: View available slots, book a session, open chat

### End-to-End Journey Test

```bash
# Run the full user journey test
python test_journey.py
```

This tests: Register → Login → Search Jobs → Save Job → ATS Check → Book Coaching

## Team Setup

### 1. Clone Repository

```bash
git clone https://github.com/jerm71279/matchforge.git
cd matchforge
```

### 2. Create Virtual Environment

**Linux/Mac:**
```bash
python -m venv venv
source venv/bin/activate
```

**Windows (PowerShell):**
```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

**Windows (CMD):**
```cmd
python -m venv venv
venv\Scripts\activate.bat
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Run in Demo Mode

**Linux/Mac:**
```bash
DEMO_MODE=true uvicorn app.main:app --port 8001 --reload
```

**Windows (PowerShell):**
```powershell
$env:DEMO_MODE="true"; uvicorn app.main:app --port 8001 --reload
```

**Windows (CMD):**
```cmd
set DEMO_MODE=true && uvicorn app.main:app --port 8001 --reload
```

### 5. Access the Application

| URL | Description |
|-----|-------------|
| http://localhost:8001/demo | Demo UI |
| http://localhost:8001/docs | Swagger API Docs |
| http://localhost:8001/redoc | ReDoc API Docs |

### Optional: Real Job APIs

To use real job APIs instead of demo data:

1. Copy `.env.example` to `.env`
2. Get free API keys:
   - **The Muse**: No key needed (works immediately)
   - **USAJobs**: https://developer.usajobs.gov/ (free)
   - **Adzuna**: https://developer.adzuna.com/ (free tier)
3. Add keys to `.env` file
4. Set `DEMO_MODE=false`

## Author

Jeremy Smith - jerm71279@gmail.com
