"""
MatchForge Auth API
User registration, login, and profile management
"""
from datetime import timedelta, datetime
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import uuid

from app.core.database import get_db
from app.core.security import (
    get_password_hash, verify_password, create_access_token, get_current_user_id
)
from app.core.config import settings
from app.models.user import User, UserProfile
from app.schemas.auth import (
    UserCreate, UserLogin, Token, UserResponse, UserProfileUpdate, UserProfileResponse
)

router = APIRouter(prefix="/auth", tags=["Authentication"])

# Demo mode in-memory storage with pre-seeded demo user
_demo_users = {}
_demo_profiles = {}

def _use_mock_auth():
    """Check if we should use mock auth (demo mode or skipping DB)."""
    return settings.DEMO_MODE or settings.SKIP_DB

def _init_demo_users():
    """Pre-seed demo user for easy testing."""
    if _use_mock_auth() and "demo@matchforge.com" not in _demo_users:
        _demo_users["demo@matchforge.com"] = {
            "id": "demo-user-001",
            "email": "demo@matchforge.com",
            "full_name": "Demo User",
            "hashed_password": get_password_hash("DemoPass123"),
            "is_active": True,
            "subscription_tier": "free",
            "coaching_sessions_remaining": 3,
            "is_verified": True,
            "created_at": datetime.utcnow(),
        }
        # Pre-seed demo profile with sample data for meaningful matching
        _demo_profiles["demo-user-001"] = {
            "user_id": "demo-user-001",
            "skills": ["Python", "JavaScript", "SQL", "AWS", "Docker", "React"],
            "years_experience": 5,
            "current_title": "Software Engineer",
            "target_titles": ["Senior Software Engineer", "Tech Lead", "Staff Engineer"],
            "salary_min": 120000,
            "salary_max": 180000,
            "preferred_locations": ["San Francisco", "Austin", "Remote"],
            "remote_preference": "remote",
            "certifications": ["AWS Solutions Architect"],
            "profile_strength": 85,
            "resume_text": None,
            "resume_updated_at": None,
        }

_init_demo_users()


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(user_data: UserCreate, db: AsyncSession = Depends(get_db)):
    """Register a new user account."""
    # Demo mode: use in-memory storage
    if _use_mock_auth():
        if user_data.email in _demo_users:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered"
            )

        user_id = str(uuid.uuid4())
        now = datetime.utcnow()
        _demo_users[user_data.email] = {
            "id": user_id,
            "email": user_data.email,
            "full_name": user_data.full_name,
            "hashed_password": get_password_hash(user_data.password),
            "is_active": True,
            "subscription_tier": "free",
            "coaching_sessions_remaining": 0,
            "is_verified": False,
            "created_at": now,
        }

        return UserResponse(
            id=user_id,
            email=user_data.email,
            full_name=user_data.full_name,
            subscription_tier="free",
            coaching_sessions_remaining=0,
            is_verified=False,
            created_at=now,
        )

    # Production mode: use database
    result = await db.execute(select(User).where(User.email == user_data.email))
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )

    # Create user
    user = User(
        email=user_data.email,
        hashed_password=get_password_hash(user_data.password),
        full_name=user_data.full_name,
    )
    db.add(user)
    await db.flush()

    # Create empty profile
    profile = UserProfile(user_id=user.id)
    db.add(profile)

    return user


@router.post("/login", response_model=Token)
async def login(credentials: UserLogin, db: AsyncSession = Depends(get_db)):
    """Login and get access token."""
    # Demo mode: check in-memory storage
    if _use_mock_auth():
        user = _demo_users.get(credentials.email)

        if not user or not verify_password(credentials.password, user["hashed_password"]):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect email or password",
                headers={"WWW-Authenticate": "Bearer"},
            )

        access_token = create_access_token(subject=user["id"])

        return Token(
            access_token=access_token,
            token_type="bearer",
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
        )

    # Production mode: use database
    result = await db.execute(select(User).where(User.email == credentials.email))
    user = result.scalar_one_or_none()

    if not user or not verify_password(credentials.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is disabled"
        )

    access_token = create_access_token(subject=user.id)

    return Token(
        access_token=access_token,
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    )


@router.get("/me", response_model=UserResponse)
async def get_current_user(
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db)
):
    """Get current user info."""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return user


@router.get("/profile", response_model=UserProfileResponse)
async def get_profile(
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db)
):
    """Get user profile for job matching."""
    # Demo/mock mode
    if _use_mock_auth():
        profile = _demo_profiles.get(user_id, _get_default_profile(user_id))
        return UserProfileResponse(**profile)

    result = await db.execute(select(UserProfile).where(UserProfile.user_id == user_id))
    profile = result.scalar_one_or_none()

    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")

    return profile


@router.put("/profile", response_model=UserProfileResponse)
async def update_profile(
    profile_data: UserProfileUpdate,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db)
):
    """Update user profile."""
    # Demo/mock mode
    if _use_mock_auth():
        profile = _demo_profiles.get(user_id, _get_default_profile(user_id))
        update_data = profile_data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            if field in profile:
                profile[field] = value
        profile["profile_strength"] = _calculate_mock_profile_strength(profile)
        _demo_profiles[user_id] = profile
        return UserProfileResponse(**profile)

    result = await db.execute(select(UserProfile).where(UserProfile.user_id == user_id))
    profile = result.scalar_one_or_none()

    if not profile:
        profile = UserProfile(user_id=user_id)

    # Update fields
    update_data = profile_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(profile, field, value)

    # Recalculate profile strength
    profile.profile_strength = calculate_profile_strength(profile)

    db.add(profile)
    await db.flush()

    return profile


def _get_default_profile(user_id: str) -> dict:
    """Return default empty profile for mock mode."""
    return {
        "user_id": user_id,
        "skills": [],
        "years_experience": None,
        "current_title": None,
        "target_titles": [],
        "salary_min": None,
        "salary_max": None,
        "preferred_locations": [],
        "remote_preference": "any",
        "certifications": [],
        "profile_strength": 0,
        "resume_updated_at": None,
    }


def _calculate_mock_profile_strength(profile: dict) -> int:
    """Calculate profile completeness for mock mode."""
    score = 0
    skills = profile.get("skills", [])
    if skills and len(skills) >= 5:
        score += 25
    elif skills:
        score += 10
    if profile.get("years_experience"):
        score += 15
    if profile.get("target_titles"):
        score += 15
    if profile.get("salary_min") or profile.get("salary_max"):
        score += 10
    if profile.get("preferred_locations"):
        score += 10
    if profile.get("certifications"):
        score += 10
    return min(100, score)


def calculate_profile_strength(profile: UserProfile) -> int:
    """Calculate profile completeness score (0-100)."""
    score = 0

    if profile.skills and len(profile.skills) >= 5:
        score += 25
    elif profile.skills:
        score += 10

    if profile.years_experience:
        score += 15

    if profile.target_titles and len(profile.target_titles) >= 1:
        score += 15

    if profile.salary_min or profile.salary_max:
        score += 10

    if profile.preferred_locations:
        score += 10

    if profile.resume_text:
        score += 15

    if profile.certifications:
        score += 10

    return min(100, score)
