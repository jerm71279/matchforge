"""
MatchForge Configuration
Environment-based settings management
"""
from pydantic_settings import BaseSettings
from typing import Optional
import secrets


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""

    # App
    APP_NAME: str = "MatchForge"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = False

    # API
    API_V1_PREFIX: str = "/api/v1"

    # Security
    SECRET_KEY: str = secrets.token_urlsafe(32)
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24 hours
    ALGORITHM: str = "HS256"

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/matchforge"

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # Job APIs
    USAJOBS_API_KEY: Optional[str] = None
    USAJOBS_EMAIL: Optional[str] = None
    ADZUNA_APP_ID: Optional[str] = None
    ADZUNA_APP_KEY: Optional[str] = None

    # Demo mode (use mock data instead of real APIs)
    DEMO_MODE: bool = False

    # Skip database connection (allows real job APIs without PostgreSQL)
    SKIP_DB: bool = True

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
