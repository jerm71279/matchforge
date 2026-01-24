# MatchForge AI Enhancement Implementation Spec
*Grok-verified January 2026*

## Overview

This document provides implementation specifications for AI enhancements to MatchForge's job matching platform.

---

## Tier 1: LLM-Powered Explainability

### 1.1 Natural Language Match Explanations

**Current State:**
```python
{
    'total_score': 87,
    'components': {
        'skills': 92,
        'experience': 85,
        'salary': 90,
        'location': 80,
        'title': 88,
        'recency': 70
    }
}
```

**Target State:**
```python
{
    'total_score': 87,
    'components': {...},
    'explanation': "You're a strong match for this Senior Developer role. Your 5 years of Python experience directly aligns with their ML team needs, and your salary expectations ($120-140k) fit their budget. The main gap: they prefer AWS experience—adding this certification could boost you to 95%.",
    'action_items': [
        "Consider AWS certification to improve match",
        "Highlight ML projects in your resume"
    ]
}
```

**Implementation:**

```python
# app/services/llm_explainer.py

import os
from openai import OpenAI

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def generate_match_explanation(
    user_profile: dict,
    job: dict,
    match_scores: dict
) -> dict:
    """Generate natural language explanation for match score."""

    prompt = f"""You are a career advisor. Explain why this job matches this candidate.

CANDIDATE PROFILE:
- Skills: {user_profile.get('skills', [])}
- Experience: {user_profile.get('years_experience', 0)} years
- Target titles: {user_profile.get('target_titles', [])}
- Salary range: ${user_profile.get('salary_min', 0):,} - ${user_profile.get('salary_max', 0):,}
- Location preference: {user_profile.get('remote_preference', 'any')}

JOB POSTING:
- Title: {job.get('title')}
- Company: {job.get('company')}
- Required skills: {job.get('required_skills', [])}
- Experience needed: {job.get('min_experience', 0)}-{job.get('max_experience', 'any')} years
- Salary: ${job.get('salary_min', 0):,} - ${job.get('salary_max', 0):,}
- Location: {job.get('location')} (Remote: {job.get('is_remote', False)})

MATCH SCORES:
- Overall: {match_scores['total_score']}%
- Skills: {match_scores['components']['skills']}%
- Experience: {match_scores['components']['experience']}%
- Salary: {match_scores['components']['salary']}%
- Location: {match_scores['components']['location']}%
- Title: {match_scores['components']['title']}%

Provide:
1. A 2-3 sentence explanation of why this is/isn't a good match
2. The single biggest strength of this match
3. The single biggest gap (if any)
4. One specific action item to improve the match

Be conversational, specific, and actionable. Use the candidate's actual skills/experience."""

    response = client.chat.completions.create(
        model="gpt-4o-mini",  # Cost-effective for this use case
        messages=[
            {"role": "system", "content": "You are a helpful career advisor. Be specific and actionable."},
            {"role": "user", "content": prompt}
        ],
        max_tokens=300,
        temperature=0.7
    )

    explanation_text = response.choices[0].message.content

    # Parse structured response (or use function calling for cleaner extraction)
    return {
        "explanation": explanation_text,
        "model": "gpt-4o-mini",
        "tokens_used": response.usage.total_tokens,
        "cost_usd": response.usage.total_tokens * 0.00000015  # GPT-4o-mini pricing
    }
```

**API Endpoint:**

```python
# app/api/jobs.py - Add to existing file

@router.post("/jobs/{job_id}/explain")
async def explain_match(
    job_id: str,
    user_id: str = Depends(get_current_user_id)
):
    """Get natural language explanation for job match."""
    # Get user profile
    profile = await get_user_profile(user_id)

    # Get job
    job = await get_job(job_id)

    # Compute match scores
    matcher = JobMatcher()
    scores = matcher.compute_match_score(profile, job)

    # Generate explanation
    explanation = await generate_match_explanation(profile, job, scores)

    return {
        **scores,
        **explanation
    }
```

**Cost Estimate:**
- GPT-4o-mini: ~$0.15 per 1M input tokens, ~$0.60 per 1M output tokens
- Average explanation: ~500 input + 200 output tokens
- Cost per explanation: ~$0.0002
- 1,000 users × 50 explanations/month = $10/month

---

### 1.2 LLM Resume Parsing

**Purpose:** Extract structured data from resume text with context understanding.

```python
# app/services/llm_resume_parser.py

def parse_resume_with_llm(resume_text: str) -> dict:
    """Extract structured profile data from resume using LLM."""

    prompt = f"""Extract structured information from this resume.

RESUME TEXT:
{resume_text[:4000]}  # Limit to avoid token overflow

Return JSON with:
{{
    "skills": ["skill1", "skill2", ...],  // Technical and soft skills
    "years_experience": number,  // Total years of professional experience
    "job_titles": ["title1", "title2"],  // Previous job titles
    "industries": ["industry1", ...],  // Industries worked in
    "education": [{{"degree": "...", "field": "...", "institution": "..."}}],
    "certifications": ["cert1", ...],
    "achievements": ["achievement1", ...],  // Quantified accomplishments
    "inferred_salary_range": {{"min": number, "max": number}},  // Based on experience
    "career_level": "entry|mid|senior|executive"
}}

Be thorough. Infer skills from context (e.g., "built ML pipelines" implies Python, ML, data engineering)."""

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"},
        max_tokens=500
    )

    return json.loads(response.choices[0].message.content)
```

---

## Tier 2: Skill Gap Analysis

### 2.1 Actionable Improvement Recommendations

```python
# app/services/skill_gap_analyzer.py

def analyze_skill_gaps(
    user_profile: dict,
    target_jobs: list[dict],
    top_n: int = 5
) -> dict:
    """Analyze skill gaps across target jobs and recommend improvements."""

    # Aggregate required skills from target jobs
    all_required_skills = []
    for job in target_jobs:
        all_required_skills.extend(job.get('required_skills', []))

    # Count frequency
    from collections import Counter
    skill_frequency = Counter(all_required_skills)

    # Find gaps
    user_skills_lower = [s.lower() for s in user_profile.get('skills', [])]
    gaps = []
    for skill, count in skill_frequency.most_common(20):
        if skill.lower() not in user_skills_lower:
            gaps.append({
                "skill": skill,
                "demand_score": count / len(target_jobs) * 100,
                "jobs_requiring": count
            })

    # Use LLM to generate learning recommendations
    prompt = f"""Based on these skill gaps for someone targeting {user_profile.get('target_titles', ['tech roles'])}:

MISSING SKILLS (by demand):
{gaps[:top_n]}

CURRENT SKILLS:
{user_profile.get('skills', [])}

Recommend:
1. Which skill to learn first (highest ROI)
2. Specific free/low-cost resources to learn it
3. How long it typically takes to become proficient
4. How to demonstrate this skill on a resume

Be specific with resource names (Coursera, YouTube channels, certifications)."""

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=400
    )

    return {
        "skill_gaps": gaps[:top_n],
        "recommendations": response.choices[0].message.content,
        "potential_score_improvement": f"+{min(15, len(gaps) * 3)}%"
    }
```

---

## Tier 2: LLM Coach Assistant

### 2.2 AI-Assisted Coaching Responses

```python
# app/services/coach_assistant.py

async def draft_coach_response(
    user_question: str,
    user_profile: dict,
    conversation_history: list[dict]
) -> dict:
    """Generate draft response for human coach to review."""

    prompt = f"""You are assisting a career coach. Draft a response to this job seeker's question.

USER PROFILE:
- Experience: {user_profile.get('years_experience', 0)} years
- Skills: {user_profile.get('skills', [])}
- Target roles: {user_profile.get('target_titles', [])}

CONVERSATION HISTORY:
{conversation_history[-5:]}  # Last 5 messages

USER'S QUESTION:
{user_question}

Draft a helpful, specific response that:
1. Directly addresses their question
2. Provides actionable advice
3. Is encouraging but realistic
4. Suggests a specific next step

Mark any parts where you're uncertain with [COACH: verify this].
Keep response under 150 words."""

    response = client.chat.completions.create(
        model="claude-3-haiku-20240307",  # Fast, cheap, good at drafts
        messages=[{"role": "user", "content": prompt}],
        max_tokens=250
    )

    return {
        "draft_response": response.choices[0].message.content,
        "confidence": "high" if "[COACH:" not in response.choices[0].message.content else "needs_review",
        "suggested_followup": "Would you like me to elaborate on any part of this?"
    }
```

---

## Environment Variables Required

```bash
# .env additions
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...

# Optional: for better embeddings
VOYAGE_API_KEY=...
```

---

## Cost Summary

| Feature | Model | Cost/1K requests | Monthly (1K users) |
|---------|-------|------------------|-------------------|
| Match explanations | GPT-4o-mini | $0.20 | $10 |
| Resume parsing | GPT-4o-mini | $0.15 | $5 |
| Skill gap analysis | GPT-4o-mini | $0.25 | $8 |
| Coach assistant | Claude Haiku | $0.30 | $15 |
| **Total** | | | **~$38/month** |

At $19/user average revenue, AI costs are **0.2% of revenue** at 1K users.

---

## Implementation Priority

1. **Week 1:** Natural language match explanations (highest user value)
2. **Week 2:** LLM resume parsing (improves match quality)
3. **Week 3-4:** Skill gap analysis (coaching value)
4. **Month 2:** Coach assistant (operational efficiency)

---

## Testing Checklist

- [ ] Explanation quality review (human eval of 50 samples)
- [ ] Resume parsing accuracy (compare to manual extraction)
- [ ] Latency testing (<2s for explanations)
- [ ] Cost monitoring dashboard
- [ ] Fallback handling (when API fails)
- [ ] Rate limiting (prevent abuse)
