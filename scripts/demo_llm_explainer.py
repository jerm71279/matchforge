#!/usr/bin/env python3
"""
Demo script for LLM Match Explainer
Run: python scripts/demo_llm_explainer.py
"""
import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.job_matcher import JobMatcher
from app.services.llm_explainer import explain_match, LLMExplainer


def demo_explanation():
    """Demonstrate the LLM explainer with sample data."""

    # Sample user profile
    user_profile = {
        "skills": ["Python", "Machine Learning", "TensorFlow", "SQL", "Docker"],
        "years_experience": 5,
        "target_titles": ["ML Engineer", "Data Scientist", "AI Engineer"],
        "salary_min": 120000,
        "salary_max": 160000,
        "remote_preference": "remote",
        "preferred_locations": ["San Francisco", "New York", "Remote"]
    }

    # Sample job posting
    job = {
        "id": "demo-123",
        "title": "Senior Machine Learning Engineer",
        "company": "TechCorp AI",
        "description": "We're looking for an experienced ML engineer to join our AI team. You'll work on cutting-edge NLP and computer vision projects.",
        "required_skills": ["Python", "TensorFlow", "PyTorch", "AWS", "Kubernetes"],
        "min_experience": 4,
        "max_experience": 8,
        "salary_min": 130000,
        "salary_max": 180000,
        "location": "San Francisco, CA",
        "is_remote": True,
        "posted_date": "2026-01-20"
    }

    print("=" * 60)
    print("MATCHFORGE LLM EXPLAINER DEMO")
    print("=" * 60)

    # Step 1: Compute match scores
    print("\n1. Computing match scores...")
    matcher = JobMatcher()
    match_scores = matcher.compute_match_score(user_profile, job)

    print(f"\n   Match Score: {match_scores['total_score']}%")
    print("   Components:")
    for component, score in match_scores['components'].items():
        print(f"   - {component.capitalize()}: {score}%")

    # Step 2: Generate LLM explanation
    print("\n2. Generating LLM explanation...")

    # Check which provider to use
    if os.getenv("XAI_API_KEY"):
        provider = "xai"
        print("   Using: xAI (Grok)")
    elif os.getenv("OPENAI_API_KEY"):
        provider = "openai"
        print("   Using: OpenAI (GPT-4o-mini)")
    elif os.getenv("ANTHROPIC_API_KEY"):
        provider = "anthropic"
        print("   Using: Anthropic (Claude Haiku)")
    else:
        provider = None
        print("   Using: Fallback template (no API key found)")

    try:
        result = explain_match(user_profile, job, match_scores, provider=provider)

        print("\n" + "=" * 60)
        print("EXPLANATION")
        print("=" * 60)
        print(f"\n{result['explanation']}")

        print(f"\n✅ STRENGTH: {result['strength']}")
        print(f"\n⚠️  GAP: {result['gap']}")
        print(f"\n📋 ACTION: {result['action_item']}")

        print("\n" + "-" * 60)
        print("METADATA")
        print("-" * 60)
        print(f"Model: {result['metadata']['model']}")
        print(f"Tokens: {result['metadata']['tokens_used']}")
        print(f"Cost: ${result['metadata']['cost_usd']:.6f}")

    except Exception as e:
        print(f"\n❌ Error: {e}")
        print("\nFalling back to template-based explanation...")

        explainer = LLMExplainer()
        result = explainer._fallback_explanation(match_scores)
        print(f"\n{result.explanation}")

    print("\n" + "=" * 60)
    print("Demo complete!")


def demo_comparison():
    """Compare explanations across different match levels."""

    print("\n" + "=" * 60)
    print("COMPARISON: HIGH vs LOW MATCH")
    print("=" * 60)

    # High match profile
    high_match_profile = {
        "skills": ["Python", "TensorFlow", "PyTorch", "AWS", "Kubernetes", "NLP"],
        "years_experience": 6,
        "target_titles": ["ML Engineer"],
        "salary_min": 130000,
        "salary_max": 170000,
        "remote_preference": "remote"
    }

    # Low match profile
    low_match_profile = {
        "skills": ["Java", "Spring Boot", "MySQL"],
        "years_experience": 2,
        "target_titles": ["Backend Developer"],
        "salary_min": 80000,
        "salary_max": 100000,
        "remote_preference": "onsite"
    }

    job = {
        "title": "Senior ML Engineer",
        "company": "AI Startup",
        "required_skills": ["Python", "TensorFlow", "AWS"],
        "min_experience": 5,
        "max_experience": 10,
        "salary_min": 150000,
        "salary_max": 200000,
        "is_remote": True
    }

    matcher = JobMatcher()

    print("\n--- HIGH MATCH CANDIDATE ---")
    high_scores = matcher.compute_match_score(high_match_profile, job)
    print(f"Score: {high_scores['total_score']}%")

    print("\n--- LOW MATCH CANDIDATE ---")
    low_scores = matcher.compute_match_score(low_match_profile, job)
    print(f"Score: {low_scores['total_score']}%")


if __name__ == "__main__":
    # Load environment variables
    from dotenv import load_dotenv
    load_dotenv()

    demo_explanation()
    demo_comparison()
