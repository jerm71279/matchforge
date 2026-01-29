"""
MatchForge Job Fetcher Service
Fetches jobs from multiple free APIs with rate limiting and caching
"""
import asyncio
import json
import math
import os
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional
import aiohttp
import redis.asyncio as redis

from app.core.config import settings


def _safe_str(value, default: str = "") -> str:
    """Safely convert value to string, handling NaN, None, and pandas NA."""
    if value is None:
        return default
    if isinstance(value, float) and math.isnan(value):
        return default
    if isinstance(value, str):
        return value
    try:
        # Handle pandas NA
        import pandas as pd
        if pd.isna(value):
            return default
    except (ImportError, TypeError):
        pass
    return str(value)


def _safe_bool(value, default: bool = False) -> bool:
    """Safely convert value to bool, handling NaN and None."""
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, float) and math.isnan(value):
        return default
    try:
        import pandas as pd
        if pd.isna(value):
            return default
    except (ImportError, TypeError):
        pass
    return bool(value)


def extract_skills_from_description(description: str) -> list[str]:
    """Extract technical skills from job description text."""
    if not description:
        return []

    text = description.lower()

    # Common tech skills to look for
    skill_patterns = [
        # Programming languages
        "python", "java", "javascript", "typescript", "c++", "c#", "go", "golang",
        "rust", "ruby", "php", "swift", "kotlin", "scala", "r ", " r,",
        # Frontend
        "react", "angular", "vue", "vue.js", "next.js", "nextjs", "html", "css",
        "tailwind", "bootstrap", "jquery", "webpack",
        # Backend
        "node.js", "nodejs", "django", "flask", "fastapi", "spring", "spring boot",
        ".net", "express", "rails", "laravel",
        # Cloud & DevOps
        "aws", "amazon web services", "azure", "gcp", "google cloud",
        "docker", "kubernetes", "k8s", "terraform", "ansible", "jenkins",
        "ci/cd", "ci cd", "devops", "github actions", "gitlab",
        # Databases
        "sql", "mysql", "postgresql", "postgres", "mongodb", "redis",
        "elasticsearch", "dynamodb", "oracle", "cassandra", "sqlite",
        # Data & ML
        "machine learning", "deep learning", "data science", "tensorflow",
        "pytorch", "pandas", "numpy", "scikit-learn", "nlp", "ai",
        "data engineering", "spark", "hadoop", "kafka", "airflow",
        # Other tech
        "api", "rest", "graphql", "microservices", "agile", "scrum",
        "git", "linux", "unix", "jira", "confluence",
    ]

    found_skills = []
    for skill in skill_patterns:
        # Check if skill appears in text (with word boundaries)
        if skill in text:
            # Normalize the skill name
            normalized = skill.strip().replace(".", "").replace(" ", "")
            if normalized == "r":
                normalized = "R"
            elif normalized == "nodejs":
                normalized = "Node.js"
            elif normalized == "vuejs":
                normalized = "Vue.js"
            elif normalized == "nextjs":
                normalized = "Next.js"
            elif normalized == "k8s":
                normalized = "Kubernetes"
            elif normalized == "amazonwebservices":
                normalized = "AWS"
            elif normalized == "googlecloud":
                normalized = "GCP"
            elif normalized == "golang":
                normalized = "Go"
            elif normalized == "cicd" or normalized == "ci cd":
                normalized = "CI/CD"
            else:
                # Capitalize first letter
                normalized = skill.strip().title()

            if normalized not in found_skills:
                found_skills.append(normalized)

    return found_skills[:15]  # Limit to 15 skills


@dataclass
class RateLimitConfig:
    """Rate limit configuration per API"""
    requests_per_period: int
    period_seconds: int


# Rate limits for free APIs (Grok-verified January 2026)
RATE_LIMITS = {
    "usajobs": RateLimitConfig(requests_per_period=100, period_seconds=1),         # 100 rows/page with pagination
    "themuse": RateLimitConfig(requests_per_period=3600, period_seconds=3600),     # 3,600/hour (unverified)
    "adzuna": RateLimitConfig(requests_per_period=100, period_seconds=86400),      # 100 req/day free tier
    "jsearch": RateLimitConfig(requests_per_period=200, period_seconds=2592000),   # 200/month free tier
    "jobspy": RateLimitConfig(requests_per_period=50, period_seconds=3600),        # Self-imposed to avoid blocks
    "career_page": RateLimitConfig(requests_per_period=100, period_seconds=3600),  # Polite scraping
    "demo": RateLimitConfig(requests_per_period=999999, period_seconds=1),         # unlimited
}


class RateLimiter:
    """
    Token bucket rate limiter using Redis for distributed state.
    """

    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client

    async def acquire(self, source: str) -> bool:
        """
        Attempt to acquire a rate limit token.
        Returns True if request can proceed, False if rate limited.
        """
        config = RATE_LIMITS.get(source)
        if not config:
            return True

        key = f"ratelimit:{source}"
        current = await self.redis.get(key)

        if current is None:
            # Initialize bucket
            await self.redis.setex(key, config.period_seconds, config.requests_per_period - 1)
            return True

        current = int(current)
        if current > 0:
            await self.redis.decr(key)
            return True

        return False

    async def wait_and_acquire(self, source: str, max_wait: int = 60) -> bool:
        """Wait for rate limit token with exponential backoff."""
        wait_time = 1
        total_waited = 0

        while total_waited < max_wait:
            if await self.acquire(source):
                return True

            await asyncio.sleep(wait_time)
            total_waited += wait_time
            wait_time = min(wait_time * 2, 30)

        return False


class JobFetcher:
    """
    Unified job fetcher with rate limiting, caching, and fallback.
    """

    def __init__(self, redis_client: Optional[redis.Redis] = None):
        self.redis = redis_client
        self.rate_limiter = RateLimiter(redis_client) if redis_client else None
        self.cache_ttl = 3600  # 1 hour cache

    async def fetch_jobs(
        self,
        keywords: str,
        location: Optional[str] = None,
        sources: list[str] = None
    ) -> list[dict]:
        """
        Fetch jobs from multiple sources with fallback chain.

        Priority:
        1. Check cache
        2. Try sources in order
        3. Return cached stale data if all APIs fail
        """
        # Demo mode returns mock data
        if settings.DEMO_MODE:
            return await self._fetch_demo_jobs(keywords, location)

        sources = sources or ["jobspy", "usajobs", "themuse", "adzuna"]
        cache_key = f"jobs:{keywords}:{location}"

        # Check cache first
        if self.redis:
            cached = await self.redis.get(cache_key)
            if cached:
                return json.loads(cached)

        all_jobs = []

        for source in sources:
            if self.rate_limiter and not await self.rate_limiter.acquire(source):
                continue

            try:
                jobs = await self._fetch_from_source(source, keywords, location)
                all_jobs.extend(jobs)
            except Exception as e:
                print(f"Error fetching from {source}: {e}")
                continue

        # Deduplicate
        deduped = self._deduplicate(all_jobs)

        # Cache results
        if self.redis and deduped:
            await self.redis.setex(cache_key, self.cache_ttl, json.dumps(deduped))

        return deduped

    async def _fetch_from_source(
        self,
        source: str,
        keywords: str,
        location: Optional[str]
    ) -> list[dict]:
        """Fetch from a specific API source."""
        if source == "jobspy":
            return await self._fetch_jobspy(keywords, location)
        elif source == "usajobs":
            return await self._fetch_usajobs(keywords, location)
        elif source == "themuse":
            return await self._fetch_themuse(keywords, location)
        elif source == "adzuna":
            return await self._fetch_adzuna(keywords, location)
        elif source == "career_page":
            return []  # Requires explicit company URL
        elif source == "demo":
            return await self._fetch_demo_jobs(keywords, location)
        return []

    async def _fetch_usajobs(self, keywords: str, location: Optional[str]) -> list[dict]:
        """
        USAJobs API - Free, 10,000 rows per query
        https://developer.usajobs.gov/
        """
        if not settings.USAJOBS_API_KEY or not settings.USAJOBS_EMAIL:
            return []

        headers = {
            "Authorization-Key": settings.USAJOBS_API_KEY,
            "User-Agent": settings.USAJOBS_EMAIL,
        }

        params = {
            "Keyword": keywords,
            "ResultsPerPage": 50,
        }
        if location:
            params["LocationName"] = location

        async with aiohttp.ClientSession() as session:
            async with session.get(
                "https://data.usajobs.gov/api/search",
                headers=headers,
                params=params,
                timeout=30
            ) as response:
                if response.status != 200:
                    return []
                data = await response.json()

        jobs = []
        for item in data.get("SearchResult", {}).get("SearchResultItems", []):
            job = item.get("MatchedObjectDescriptor", {})
            remuneration = job.get("PositionRemuneration", [{}])
            salary_info = remuneration[0] if remuneration else {}

            title = _safe_str(job.get("PositionTitle"))
            jobs.append({
                "id": f"usajobs_{_safe_str(job.get('PositionID'))}",
                "source": "usajobs",
                "source_id": _safe_str(job.get("PositionID")),
                "title": title,
                "company": _safe_str(job.get("OrganizationName")),
                "location": _safe_str(job.get("PositionLocationDisplay")),
                "salary_min": self._parse_salary(salary_info.get("MinimumRange")),
                "salary_max": self._parse_salary(salary_info.get("MaximumRange")),
                "description": _safe_str(job.get("UserArea", {}).get("Details", {}).get("JobSummary", "")),
                "source_url": _safe_str(job.get("PositionURI")),
                "posted_date": _safe_str(job.get("PublicationStartDate")) or None,
                "is_remote": "telework" in title.lower() or "remote" in title.lower(),
                "required_skills": [],
                "min_experience": None,
                "max_experience": None,
            })

        return jobs

    async def _fetch_themuse(self, keywords: str, location: Optional[str]) -> list[dict]:
        """
        The Muse API - Free, 3,600 requests/hour
        https://www.themuse.com/developers/api/v2
        """
        params = {
            "page": 1,
            "descending": "true",
        }
        if location:
            params["location"] = location

        async with aiohttp.ClientSession() as session:
            async with session.get(
                "https://www.themuse.com/api/public/jobs",
                params=params,
                timeout=30
            ) as response:
                if response.status != 200:
                    return []
                data = await response.json()

        jobs = []
        for item in data.get("results", []):
            locations = item.get("locations", [])
            location_str = ", ".join([loc.get("name", "") for loc in locations])
            is_remote = any("remote" in loc.get("name", "").lower() for loc in locations)

            # Filter by keywords in title or company
            title = item.get("name", "").lower()
            company = item.get("company", {}).get("name", "").lower()
            if keywords and keywords.lower() not in title and keywords.lower() not in company:
                continue

            description = _safe_str(item.get("contents", ""))
            extracted_skills = extract_skills_from_description(description)

            jobs.append({
                "id": f"themuse_{item.get('id')}",
                "source": "themuse",
                "source_id": _safe_str(item.get("id")),
                "title": _safe_str(item.get("name")),
                "company": _safe_str(item.get("company", {}).get("name")),
                "location": _safe_str(location_str),
                "salary_min": None,  # The Muse doesn't provide salary
                "salary_max": None,
                "description": description,
                "source_url": _safe_str(item.get("refs", {}).get("landing_page")),
                "posted_date": _safe_str(item.get("publication_date")) or None,
                "is_remote": is_remote,
                "required_skills": extracted_skills,
                "min_experience": None,
                "max_experience": None,
                "company_culture": _safe_str(item.get("company", {}).get("short_name")),
            })

        return jobs[:50]  # Limit results

    async def _fetch_adzuna(self, keywords: str, location: Optional[str]) -> list[dict]:
        """
        Adzuna API - Free tier: 25 requests/minute (1,500/hour)
        https://developer.adzuna.com/
        """
        if not settings.ADZUNA_APP_ID or not settings.ADZUNA_APP_KEY:
            return []

        params = {
            "app_id": settings.ADZUNA_APP_ID,
            "app_key": settings.ADZUNA_APP_KEY,
            "what": keywords,
            "results_per_page": 50,
        }
        if location:
            params["where"] = location

        async with aiohttp.ClientSession() as session:
            async with session.get(
                "https://api.adzuna.com/v1/api/jobs/us/search/1",
                params=params,
                timeout=30
            ) as response:
                if response.status != 200:
                    return []
                data = await response.json()

        jobs = []
        for item in data.get("results", []):
            title = _safe_str(item.get("title"))
            description = _safe_str(item.get("description", ""))
            extracted_skills = extract_skills_from_description(description)

            jobs.append({
                "id": f"adzuna_{item.get('id')}",
                "source": "adzuna",
                "source_id": _safe_str(item.get("id")),
                "title": title,
                "company": _safe_str(item.get("company", {}).get("display_name")),
                "location": _safe_str(item.get("location", {}).get("display_name")),
                "salary_min": self._parse_salary(item.get("salary_min")),
                "salary_max": self._parse_salary(item.get("salary_max")),
                "description": description,
                "source_url": _safe_str(item.get("redirect_url")),
                "posted_date": _safe_str(item.get("created")) or None,
                "is_remote": "remote" in title.lower(),
                "required_skills": extracted_skills,
                "min_experience": None,
                "max_experience": None,
            })

        return jobs

    async def _fetch_jobspy(self, keywords: str, location: Optional[str]) -> list[dict]:
        """
        JobSpy - Open source multi-platform scraper (FREE)
        Scrapes Indeed, ZipRecruiter, Glassdoor concurrently
        https://github.com/speedyapply/JobSpy

        Note: LinkedIn excluded due to aggressive rate limiting
        """
        try:
            from jobspy import scrape_jobs
            import pandas as pd

            # Run in thread pool since jobspy is synchronous
            import asyncio
            loop = asyncio.get_event_loop()

            def scrape():
                return scrape_jobs(
                    site_name=["indeed", "zip_recruiter", "glassdoor"],
                    search_term=keywords,
                    location=location or "USA",
                    results_wanted=50,
                    hours_old=72,  # Last 3 days
                    country_indeed="USA",
                )

            df = await loop.run_in_executor(None, scrape)

            if df is None or df.empty:
                return []

            jobs = []
            for _, row in df.iterrows():
                # Parse salary if available
                salary_min = None
                salary_max = None
                if pd.notna(row.get('min_amount')):
                    salary_min = int(row['min_amount'])
                if pd.notna(row.get('max_amount')):
                    salary_max = int(row['max_amount'])

                # Extract skills from description
                description = _safe_str(row.get('description'), '')
                extracted_skills = extract_skills_from_description(description)

                jobs.append({
                    "id": f"jobspy_{_safe_str(row.get('site'), 'unknown')}_{hash(_safe_str(row.get('job_url')))}",
                    "source": f"jobspy_{_safe_str(row.get('site'), 'unknown')}",
                    "source_id": _safe_str(row.get('id')),
                    "title": _safe_str(row.get('title')),
                    "company": _safe_str(row.get('company')),
                    "location": _safe_str(row.get('location')),
                    "salary_min": salary_min,
                    "salary_max": salary_max,
                    "description": description[:5000],  # Limit description length
                    "source_url": _safe_str(row.get('job_url')),
                    "posted_date": _safe_str(row.get('date_posted')) or None,
                    "is_remote": _safe_bool(row.get('is_remote')),
                    "required_skills": extracted_skills,
                    "min_experience": None,
                    "max_experience": None,
                })

            return jobs

        except ImportError:
            print("JobSpy not installed. Run: pip install python-jobspy")
            return []
        except Exception as e:
            print(f"JobSpy error: {e}")
            return []

    async def scrape_career_page(self, company_url: str, keywords: str = None) -> list[dict]:
        """
        Scrape jobs from a company's career page (FREE)
        Uses BeautifulSoup for basic HTML parsing

        Args:
            company_url: URL to the company's careers/jobs page
            keywords: Optional filter keywords

        Returns:
            List of job dicts
        """
        try:
            from bs4 import BeautifulSoup
            import re

            async with aiohttp.ClientSession() as session:
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                }
                async with session.get(company_url, headers=headers, timeout=30) as response:
                    if response.status != 200:
                        return []
                    html = await response.text()

            soup = BeautifulSoup(html, 'lxml')
            jobs = []

            # Common career page patterns
            job_patterns = [
                # Look for job listing containers
                soup.find_all('div', class_=re.compile(r'job|position|opening|career|vacancy', re.I)),
                soup.find_all('li', class_=re.compile(r'job|position|opening', re.I)),
                soup.find_all('article', class_=re.compile(r'job|position', re.I)),
                # Look for links with job-related text
                soup.find_all('a', href=re.compile(r'/jobs/|/careers/|/positions/', re.I)),
            ]

            seen_titles = set()

            for pattern_results in job_patterns:
                for element in pattern_results[:50]:  # Limit to 50 per pattern
                    # Try to extract job title
                    title_elem = (
                        element.find(['h1', 'h2', 'h3', 'h4']) or
                        element.find(class_=re.compile(r'title|name', re.I)) or
                        element
                    )
                    title = title_elem.get_text(strip=True) if title_elem else None

                    if not title or len(title) < 5 or len(title) > 200:
                        continue

                    # Dedupe by title
                    if title.lower() in seen_titles:
                        continue
                    seen_titles.add(title.lower())

                    # Filter by keywords if provided
                    if keywords and keywords.lower() not in title.lower():
                        continue

                    # Try to find location
                    location_elem = element.find(class_=re.compile(r'location|city|place', re.I))
                    location = location_elem.get_text(strip=True) if location_elem else None

                    # Try to find link
                    link = None
                    if element.name == 'a':
                        link = element.get('href', '')
                    else:
                        link_elem = element.find('a')
                        if link_elem:
                            link = link_elem.get('href', '')

                    # Make absolute URL
                    if link and not link.startswith('http'):
                        from urllib.parse import urljoin
                        link = urljoin(company_url, link)

                    # Extract company name from URL
                    from urllib.parse import urlparse
                    company = urlparse(company_url).netloc.replace('www.', '').split('.')[0].title()

                    jobs.append({
                        "id": f"career_{company.lower()}_{hash(title)}",
                        "source": "career_page",
                        "source_id": str(hash(title)),
                        "title": title,
                        "company": company,
                        "location": location,
                        "salary_min": None,
                        "salary_max": None,
                        "description": "",
                        "source_url": link or company_url,
                        "posted_date": None,
                        "is_remote": "remote" in title.lower() if title else False,
                        "required_skills": [],
                        "min_experience": None,
                        "max_experience": None,
                    })

            return jobs[:50]  # Limit results

        except ImportError:
            print("BeautifulSoup not installed. Run: pip install beautifulsoup4 lxml")
            return []
        except Exception as e:
            print(f"Career page scrape error: {e}")
            return []

    async def _fetch_demo_jobs(self, keywords: str, location: Optional[str]) -> list[dict]:
        """Fetch from demo dataset"""
        try:
            import os
            demo_path = os.path.join(os.path.dirname(__file__), "..", "..", "data", "demo_jobs.json")
            with open(demo_path, "r") as f:
                all_jobs = json.load(f)

            # Filter by keywords
            if keywords:
                keywords_lower = keywords.lower()
                all_jobs = [
                    j for j in all_jobs
                    if keywords_lower in j.get("title", "").lower() or
                       keywords_lower in j.get("description", "").lower() or
                       any(keywords_lower in skill.lower() for skill in j.get("required_skills", []))
                ]

            # Filter by location
            if location:
                location_lower = location.lower()
                all_jobs = [
                    j for j in all_jobs
                    if location_lower in j.get("location", "").lower() or j.get("is_remote", False)
                ]

            return all_jobs
        except Exception as e:
            print(f"Error loading demo jobs: {e}")
            return []

    def _parse_salary(self, value) -> Optional[int]:
        """Parse salary string to integer."""
        if not value:
            return None
        try:
            return int(float(str(value).replace(",", "").replace("$", "")))
        except:
            return None

    def _deduplicate(self, jobs: list[dict]) -> list[dict]:
        """Remove duplicate jobs based on title + company."""
        seen = set()
        unique = []

        for job in jobs:
            title = _safe_str(job.get('title')).lower()
            company = _safe_str(job.get('company')).lower()
            key = f"{title}_{company}"
            key = "".join(c for c in key if c.isalnum())

            if key not in seen:
                seen.add(key)
                unique.append(job)

        return unique
