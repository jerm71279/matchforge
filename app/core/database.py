"""
MatchForge Database Configuration
Async SQLAlchemy setup with PostgreSQL

In DEMO_MODE, uses mock database session to avoid PostgreSQL dependency.
"""
from sqlalchemy.orm import declarative_base
from typing import AsyncGenerator, Optional

from app.core.config import settings

# Base class for models (always needed for model definitions)
Base = declarative_base()

# Only create real database connection if not in demo mode and not skipping DB
engine = None
async_session_maker = None

if not settings.DEMO_MODE and not settings.SKIP_DB:
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

    engine = create_async_engine(
        settings.DATABASE_URL,
        echo=settings.DEBUG,
        future=True,
    )

    async_session_maker = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )


class MockSession:
    """Mock database session for demo mode."""

    async def execute(self, *args, **kwargs):
        """Return empty result for demo mode."""
        class MockResult:
            def scalar_one_or_none(self):
                return None
            def scalars(self):
                class MockScalars:
                    def all(self):
                        return []
                return MockScalars()
        return MockResult()

    def add(self, obj):
        pass

    async def flush(self):
        pass

    async def commit(self):
        pass

    async def rollback(self):
        pass

    async def close(self):
        pass


async def get_db() -> AsyncGenerator:
    """
    Dependency that provides database session.
    In demo mode or when DB is skipped, provides a mock session.
    """
    if settings.DEMO_MODE or settings.SKIP_DB:
        yield MockSession()
        return

    async with async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db():
    """Initialize database tables (skipped in demo mode or when DB is skipped)."""
    if settings.DEMO_MODE or settings.SKIP_DB or engine is None:
        return

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
