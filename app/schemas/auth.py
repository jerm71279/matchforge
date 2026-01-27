"""
MatchForge Auth Schemas
Request/response models for authentication
"""
from pydantic import BaseModel, EmailStr, Field
from typing import Optional
from datetime import datetime


class UserCreate(BaseModel):
    """User registration request"""
    email: EmailStr
    password: str = Field(..., min_length=8)
    full_name: Optional[str] = None


class UserLogin(BaseModel):
    """User login request"""
    email: EmailStr
    password: str


class Token(BaseModel):
    """JWT token response"""
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class TokenPayload(BaseModel):
    """JWT token payload"""
    sub: str
    exp: datetime


class UserResponse(BaseModel):
    """User data response"""
    id: str
    email: str
    full_name: Optional[str]
    subscription_tier: str
    coaching_sessions_remaining: int
    is_verified: bool
    created_at: datetime

    class Config:
        from_attributes = True


class UserProfileUpdate(BaseModel):
    """Update user profile"""
    full_name: Optional[str] = None
    phone: Optional[str] = None
    skills: Optional[list[str]] = None
    years_experience: Optional[int] = None
    current_title: Optional[str] = None
    target_titles: Optional[list[str]] = None
    salary_min: Optional[int] = None
    salary_max: Optional[int] = None
    preferred_locations: Optional[list[str]] = None
    remote_preference: Optional[str] = None  # remote, hybrid, onsite, any
    certifications: Optional[list[str]] = None


class UserProfileResponse(BaseModel):
    """User profile response"""
    user_id: str
    skills: list[str]
    years_experience: Optional[int]
    current_title: Optional[str]
    target_titles: list[str]
    salary_min: Optional[int]
    salary_max: Optional[int]
    preferred_locations: list[str]
    remote_preference: str
    certifications: list[str]
    profile_strength: int
    resume_updated_at: Optional[datetime]

    class Config:
        from_attributes = True
