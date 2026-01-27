"""
MatchForge Skill Gap Analyzer
Analyzes skill gaps between user profile and target jobs, provides recommendations
"""
import os
import json
from collections import Counter
from typing import Optional


def analyze_skill_gaps(
    user_profile: dict,
    target_jobs: list[dict],
    top_n: int = 5
) -> dict:
    """
    Analyze skill gaps between user skills and target job requirements.

    Args:
        user_profile: User's profile with skills, experience, etc.
        target_jobs: List of job dicts with required_skills
        top_n: Number of top gaps to return

    Returns:
        Dict with skill gaps, recommendations, and potential score improvement
    """
    user_skills = set(s.lower() for s in user_profile.get("skills", []))

    # Aggregate required skills from target jobs
    all_required_skills = []
    for job in target_jobs:
        for skill in job.get("required_skills", []):
            all_required_skills.append(skill.lower())
        # Also check description for common skills
        desc = job.get("description", "").lower()
        for skill in _extract_skills_from_text(desc):
            all_required_skills.append(skill)

    # Count frequency
    skill_frequency = Counter(all_required_skills)

    # Find gaps (skills in jobs but not in user profile)
    gaps = []
    for skill, count in skill_frequency.most_common(30):
        # Check if user has this skill (fuzzy match)
        has_skill = any(_skills_match(skill, us) for us in user_skills)
        if not has_skill:
            gaps.append({
                "skill": skill.title(),
                "demand_score": round(count / max(len(target_jobs), 1) * 100),
                "jobs_requiring": count
            })

    top_gaps = gaps[:top_n]

    # Generate recommendations
    recommendations = _generate_recommendations(
        user_profile,
        top_gaps,
        use_llm=bool(os.getenv("OPENAI_API_KEY") or os.getenv("ANTHROPIC_API_KEY"))
    )

    # Calculate potential improvement
    potential_improvement = min(15, len(top_gaps) * 3)

    return {
        "skill_gaps": top_gaps,
        "all_gaps_count": len(gaps),
        "recommendations": recommendations,
        "potential_score_improvement": f"+{potential_improvement}%",
        "analysis_summary": _generate_summary(user_profile, top_gaps, target_jobs)
    }


def _extract_skills_from_text(text: str) -> list[str]:
    """Extract common tech skills from text."""
    common_skills = [
        "python", "java", "javascript", "typescript", "go", "rust", "c++", "c#",
        "react", "angular", "vue", "node", "django", "flask", "fastapi", "spring",
        "aws", "azure", "gcp", "docker", "kubernetes", "terraform",
        "sql", "postgresql", "mysql", "mongodb", "redis",
        "git", "ci/cd", "jenkins", "agile", "scrum",
        "machine learning", "deep learning", "nlp", "data science",
        "rest api", "graphql", "microservices"
    ]

    found = []
    for skill in common_skills:
        if skill in text:
            found.append(skill)
    return found


def _skills_match(skill1: str, skill2: str) -> bool:
    """Check if two skills match (fuzzy)."""
    s1, s2 = skill1.lower(), skill2.lower()

    # Exact match
    if s1 == s2:
        return True

    # One contains the other
    if s1 in s2 or s2 in s1:
        return True

    # Common variations
    variations = {
        "javascript": ["js", "node.js", "nodejs"],
        "typescript": ["ts"],
        "python": ["py"],
        "kubernetes": ["k8s"],
        "postgresql": ["postgres", "psql"],
        "amazon web services": ["aws"],
        "google cloud": ["gcp"],
        "microsoft azure": ["azure"],
    }

    for canonical, aliases in variations.items():
        if s1 == canonical and s2 in aliases:
            return True
        if s2 == canonical and s1 in aliases:
            return True
        if s1 in aliases and s2 in aliases:
            return True

    return False


def _generate_recommendations(
    user_profile: dict,
    gaps: list[dict],
    use_llm: bool = False
) -> list[dict]:
    """Generate learning recommendations for skill gaps."""
    if use_llm:
        return _generate_llm_recommendations(user_profile, gaps)

    # Fallback to static recommendations
    return _generate_static_recommendations(gaps)


def _generate_static_recommendations(gaps: list[dict]) -> list[dict]:
    """Generate static recommendations without LLM."""
    # Learning resources by skill category
    resources = {
        "python": {
            "resource": "Python.org Tutorial + Real Python",
            "time_to_learn": "2-4 weeks for basics",
            "certification": "PCEP (Python Institute)"
        },
        "aws": {
            "resource": "AWS Skill Builder (free) + A Cloud Guru",
            "time_to_learn": "4-8 weeks for Solutions Architect",
            "certification": "AWS Solutions Architect Associate"
        },
        "docker": {
            "resource": "Docker's Official Tutorial + KodeKloud",
            "time_to_learn": "1-2 weeks",
            "certification": "Docker Certified Associate"
        },
        "kubernetes": {
            "resource": "Kubernetes.io Tutorial + KodeKloud CKA Course",
            "time_to_learn": "4-6 weeks",
            "certification": "CKA (Certified Kubernetes Administrator)"
        },
        "react": {
            "resource": "React.dev Tutorial + Scrimba",
            "time_to_learn": "3-4 weeks",
            "certification": "Meta Front-End Developer (Coursera)"
        },
        "sql": {
            "resource": "SQLBolt + Mode Analytics SQL Tutorial",
            "time_to_learn": "1-2 weeks for basics",
            "certification": "Oracle SQL Certification"
        },
        "machine learning": {
            "resource": "Andrew Ng's ML Course (Coursera) + Fast.ai",
            "time_to_learn": "8-12 weeks",
            "certification": "Google ML Engineer"
        },
        "terraform": {
            "resource": "HashiCorp Learn + KodeKloud",
            "time_to_learn": "2-3 weeks",
            "certification": "HashiCorp Terraform Associate"
        }
    }

    recommendations = []
    for gap in gaps:
        skill_lower = gap["skill"].lower()

        # Find matching resource
        rec = None
        for key, value in resources.items():
            if key in skill_lower or skill_lower in key:
                rec = value
                break

        if rec:
            recommendations.append({
                "skill": gap["skill"],
                "priority": "high" if gap["demand_score"] > 50 else "medium",
                "resource": rec["resource"],
                "time_estimate": rec["time_to_learn"],
                "certification": rec.get("certification"),
                "resume_tip": f"Add projects using {gap['skill']} to demonstrate hands-on experience"
            })
        else:
            recommendations.append({
                "skill": gap["skill"],
                "priority": "high" if gap["demand_score"] > 50 else "medium",
                "resource": f"Search '{gap['skill']} tutorial' on YouTube/Udemy",
                "time_estimate": "Varies",
                "certification": None,
                "resume_tip": f"Add '{gap['skill']}' to your skills after completing a project"
            })

    return recommendations


def _generate_llm_recommendations(user_profile: dict, gaps: list[dict]) -> list[dict]:
    """Generate recommendations using LLM."""
    try:
        if os.getenv("OPENAI_API_KEY"):
            from openai import OpenAI
            client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

            prompt = f"""You are a career advisor. Generate specific learning recommendations for these skill gaps.

USER PROFILE:
- Current skills: {user_profile.get('skills', [])}
- Experience: {user_profile.get('years_experience', 0)} years
- Target roles: {user_profile.get('target_titles', [])}

SKILL GAPS (by demand):
{json.dumps(gaps, indent=2)}

For each skill gap, provide JSON array with:
{{
    "skill": "skill name",
    "priority": "high|medium|low",
    "resource": "specific free/low-cost resource name",
    "time_estimate": "realistic time to become proficient",
    "certification": "relevant certification if applicable",
    "resume_tip": "how to demonstrate this skill on resume"
}}

Return JSON array only, no explanation."""

            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
                max_tokens=600,
                temperature=0.5
            )

            result = json.loads(response.choices[0].message.content)
            if isinstance(result, dict) and "recommendations" in result:
                return result["recommendations"]
            elif isinstance(result, list):
                return result
            return _generate_static_recommendations(gaps)

    except Exception as e:
        print(f"LLM recommendation error: {e}")

    return _generate_static_recommendations(gaps)


def _generate_summary(user_profile: dict, gaps: list[dict], jobs: list[dict]) -> str:
    """Generate a summary of the skill gap analysis."""
    user_skills_count = len(user_profile.get("skills", []))
    gap_count = len(gaps)

    if gap_count == 0:
        return "Your skills align well with the target jobs. Focus on deepening expertise in your existing skills."

    top_gap = gaps[0]["skill"] if gaps else "N/A"

    return f"Analyzed {len(jobs)} jobs. Found {gap_count} skill gaps. Top priority: {top_gap} (found in {gaps[0]['jobs_requiring']} jobs). You have {user_skills_count} skills listed."
