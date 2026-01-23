"""
MatchForge User Models
User account and profile data
"""
from sqlalchemy import Column, String, Integer, Boolean, DateTime, JSON, Text
from sqlalchemy.sql import func
from datetime import datetime
import uuid

from app.core.database import Base


class User(Base):
    """User account model"""
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    email = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)

    # Profile
    full_name = Column(String(255))
    phone = Column(String(50))

    # Subscription
    subscription_tier = Column(String(50), default="free")  # free, basic, professional, premium
    coaching_sessions_remaining = Column(Integer, default=3)  # Demo: start with 3 sessions

    # Status
    is_active = Column(Boolean, default=True)
    is_verified = Column(Boolean, default=False)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    last_login = Column(DateTime(timezone=True))


class UserProfile(Base):
    """Extended user profile for job matching"""
    __tablename__ = "user_profiles"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), index=True, nullable=False)

    # Resume data (parsed)
    resume_text = Column(Text)
    resume_file_path = Column(String(500))
    resume_updated_at = Column(DateTime(timezone=True))

    # Extracted skills (JSON array)
    skills = Column(JSON, default=list)

    # Experience
    years_experience = Column(Integer)
    current_title = Column(String(255))
    target_titles = Column(JSON, default=list)  # List of desired job titles

    # Preferences
    salary_min = Column(Integer)
    salary_max = Column(Integer)
    preferred_locations = Column(JSON, default=list)  # List of locations
    remote_preference = Column(String(50), default="any")  # remote, hybrid, onsite, any

    # Certifications
    certifications = Column(JSON, default=list)

    # Profile completeness (0-100)
    profile_strength = Column(Integer, default=0)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
