"""
MatchForge LLM Resume Parser
Extracts structured profile data from resume text using LLM
"""
import os
import json
from typing import Optional


def parse_resume_with_llm(resume_text: str, provider: str = "openai") -> dict:
    """
    Extract structured profile data from resume using LLM.

    Args:
        resume_text: Raw text extracted from resume
        provider: LLM provider (openai, anthropic, or mock for testing)

    Returns:
        Dict with extracted profile fields
    """
    if provider == "mock" or (not os.getenv("OPENAI_API_KEY") and not os.getenv("ANTHROPIC_API_KEY")):
        return _parse_with_keyword_extraction(resume_text)

    if provider == "anthropic" and os.getenv("ANTHROPIC_API_KEY"):
        return _parse_with_anthropic(resume_text)

    if os.getenv("OPENAI_API_KEY"):
        return _parse_with_openai(resume_text)

    # Fallback to keyword extraction
    return _parse_with_keyword_extraction(resume_text)


def _parse_with_openai(resume_text: str) -> dict:
    """Parse resume using OpenAI GPT-4o-mini."""
    try:
        from openai import OpenAI
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

        prompt = _build_extraction_prompt(resume_text)

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a resume parser. Extract structured data and return valid JSON only."},
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"},
            max_tokens=800,
            temperature=0.3
        )

        result = json.loads(response.choices[0].message.content)
        result["_metadata"] = {
            "model": "gpt-4o-mini",
            "tokens_used": response.usage.total_tokens,
            "cost_usd": response.usage.total_tokens * 0.00000015
        }
        return _normalize_result(result)

    except Exception as e:
        print(f"OpenAI parsing error: {e}")
        return _parse_with_keyword_extraction(resume_text)


def _parse_with_anthropic(resume_text: str) -> dict:
    """Parse resume using Anthropic Claude."""
    try:
        from anthropic import Anthropic
        client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

        prompt = _build_extraction_prompt(resume_text)

        response = client.messages.create(
            model="claude-3-haiku-20240307",
            max_tokens=800,
            messages=[
                {"role": "user", "content": prompt}
            ]
        )

        # Extract JSON from response
        content = response.content[0].text
        # Try to find JSON in the response
        if "{" in content:
            json_start = content.index("{")
            json_end = content.rindex("}") + 1
            result = json.loads(content[json_start:json_end])
        else:
            result = json.loads(content)

        result["_metadata"] = {
            "model": "claude-3-haiku",
            "tokens_used": response.usage.input_tokens + response.usage.output_tokens,
            "cost_usd": (response.usage.input_tokens * 0.00000025 + response.usage.output_tokens * 0.00000125)
        }
        return _normalize_result(result)

    except Exception as e:
        print(f"Anthropic parsing error: {e}")
        return _parse_with_keyword_extraction(resume_text)


def _build_extraction_prompt(resume_text: str) -> str:
    """Build the prompt for LLM extraction."""
    # Truncate to avoid token overflow
    truncated = resume_text[:6000] if len(resume_text) > 6000 else resume_text

    return f"""Extract structured information from this resume.

RESUME TEXT:
{truncated}

Return JSON with these fields:
{{
    "skills": ["skill1", "skill2", ...],  // Technical and soft skills found
    "years_experience": number or null,  // Total years of professional experience
    "current_title": "string or null",  // Most recent job title
    "target_titles": ["title1", "title2"],  // Likely target roles based on experience
    "certifications": ["cert1", ...],  // Professional certifications
    "education": [{{"degree": "...", "field": "...", "institution": "..."}}],
    "salary_estimate": {{"min": number, "max": number}} or null,  // Estimated based on experience
    "career_level": "entry|junior|mid|senior|lead|executive",
    "industries": ["industry1", ...],  // Industries worked in
    "locations": ["location1", ...]  // Locations mentioned
}}

Be thorough. Infer skills from context (e.g., "built ML pipelines" implies Python, ML, data engineering).
For years_experience, calculate from work history dates if available.
Return valid JSON only, no explanation."""


def _parse_with_keyword_extraction(resume_text: str) -> dict:
    """
    Fallback parser using keyword extraction.
    Works without LLM but less accurate.
    """
    text_lower = resume_text.lower()

    # Common tech skills to look for
    tech_skills = [
        "python", "java", "javascript", "typescript", "c++", "c#", "go", "rust", "ruby", "php",
        "react", "angular", "vue", "node.js", "django", "flask", "fastapi", "spring",
        "aws", "azure", "gcp", "docker", "kubernetes", "terraform", "ansible",
        "sql", "postgresql", "mysql", "mongodb", "redis", "elasticsearch",
        "git", "ci/cd", "jenkins", "github actions", "gitlab",
        "machine learning", "deep learning", "tensorflow", "pytorch", "nlp",
        "agile", "scrum", "jira", "confluence",
        "linux", "unix", "bash", "powershell",
        "rest api", "graphql", "microservices",
        "security", "networking", "devops", "sre"
    ]

    # Extract skills found in text
    found_skills = []
    for skill in tech_skills:
        if skill in text_lower:
            found_skills.append(skill.title() if len(skill) > 3 else skill.upper())

    # Try to extract years of experience
    years_exp = None
    import re
    exp_patterns = [
        r'(\d+)\+?\s*years?\s*(?:of\s*)?experience',
        r'experience:\s*(\d+)\+?\s*years?',
        r'(\d+)\+?\s*years?\s*in\s*(?:the\s*)?industry'
    ]
    for pattern in exp_patterns:
        match = re.search(pattern, text_lower)
        if match:
            years_exp = int(match.group(1))
            break

    # Common certifications
    certifications = []
    cert_patterns = [
        "aws certified", "azure certified", "gcp certified",
        "cissp", "cism", "cisa", "security+", "comptia",
        "pmp", "scrum master", "csm", "safe",
        "ccna", "ccnp", "ccie",
        "cka", "ckad", "cks"
    ]
    for cert in cert_patterns:
        if cert in text_lower:
            certifications.append(cert.upper() if len(cert) < 6 else cert.title())

    # Determine career level
    career_level = "mid"
    if any(word in text_lower for word in ["senior", "sr.", "lead", "principal", "staff"]):
        career_level = "senior"
    elif any(word in text_lower for word in ["junior", "jr.", "entry", "intern", "graduate"]):
        career_level = "junior"
    elif any(word in text_lower for word in ["director", "vp", "cto", "cio", "executive", "chief"]):
        career_level = "executive"

    return _normalize_result({
        "skills": found_skills[:20],  # Limit to 20 skills
        "years_experience": years_exp,
        "current_title": None,
        "target_titles": [],
        "certifications": certifications,
        "education": [],
        "salary_estimate": None,
        "career_level": career_level,
        "industries": [],
        "locations": [],
        "_metadata": {
            "model": "keyword_extraction",
            "tokens_used": 0,
            "cost_usd": 0
        }
    })


def _normalize_result(result: dict) -> dict:
    """Normalize and validate the extraction result."""
    return {
        "skills": result.get("skills", []) or [],
        "years_experience": result.get("years_experience"),
        "current_title": result.get("current_title"),
        "target_titles": result.get("target_titles", []) or [],
        "certifications": result.get("certifications", []) or [],
        "education": result.get("education", []) or [],
        "salary_estimate": result.get("salary_estimate"),
        "career_level": result.get("career_level", "mid"),
        "industries": result.get("industries", []) or [],
        "locations": result.get("locations", []) or [],
        "_metadata": result.get("_metadata", {})
    }
