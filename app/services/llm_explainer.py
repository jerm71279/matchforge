"""
MatchForge LLM Explainer Service
Generates natural language explanations for job matches using LLMs
"""
import os
import json
from typing import Optional
from dataclasses import dataclass

# Support multiple LLM providers
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "openai")  # openai, anthropic, or xai


@dataclass
class ExplanationResult:
    """Result of match explanation generation."""
    explanation: str
    strength: str
    gap: str
    action_item: str
    model: str
    tokens_used: int
    cost_usd: float


class LLMExplainer:
    """
    Generates natural language explanations for job match scores.
    Supports OpenAI, Anthropic, and xAI (Grok) as providers.
    """

    def __init__(self, provider: str = None, api_key: str = None):
        self.provider = provider or LLM_PROVIDER
        self.api_key = api_key or self._get_api_key()
        self.client = self._init_client()

    def _get_api_key(self) -> str:
        """Get API key from environment based on provider."""
        key_map = {
            "openai": "OPENAI_API_KEY",
            "anthropic": "ANTHROPIC_API_KEY",
            "xai": "XAI_API_KEY",
        }
        env_var = key_map.get(self.provider, "OPENAI_API_KEY")
        return os.getenv(env_var, "")

    def _init_client(self):
        """Initialize the appropriate LLM client."""
        if self.provider == "openai":
            from openai import OpenAI
            return OpenAI(api_key=self.api_key)
        elif self.provider == "anthropic":
            from anthropic import Anthropic
            return Anthropic(api_key=self.api_key)
        elif self.provider == "xai":
            from openai import OpenAI  # xAI uses OpenAI-compatible API
            return OpenAI(
                api_key=self.api_key,
                base_url="https://api.x.ai/v1"
            )
        else:
            raise ValueError(f"Unknown provider: {self.provider}")

    def _build_prompt(
        self,
        user_profile: dict,
        job: dict,
        match_scores: dict
    ) -> str:
        """Build the explanation prompt."""

        skills = ", ".join(user_profile.get('skills', [])[:10]) or "Not specified"
        target_titles = ", ".join(user_profile.get('target_titles', [])[:3]) or "Not specified"
        job_skills = ", ".join(job.get('required_skills', [])[:10]) or "Not specified"

        return f"""You are a career advisor explaining why a job matches (or doesn't match) a candidate.

CANDIDATE:
- Skills: {skills}
- Experience: {user_profile.get('years_experience', 'Not specified')} years
- Target roles: {target_titles}
- Salary range: ${user_profile.get('salary_min', 0):,} - ${user_profile.get('salary_max', 0):,}
- Location: {user_profile.get('remote_preference', 'flexible')}

JOB:
- Title: {job.get('title', 'Unknown')}
- Company: {job.get('company', 'Unknown')}
- Required skills: {job_skills}
- Experience: {job.get('min_experience', 0)}-{job.get('max_experience', '?')} years
- Salary: ${job.get('salary_min', 0):,} - ${job.get('salary_max', 0):,}
- Remote: {job.get('is_remote', 'Unknown')}

MATCH SCORES (0-100):
- Overall: {match_scores.get('total_score', 0)}%
- Skills: {match_scores.get('components', {}).get('skills', 0)}%
- Experience: {match_scores.get('components', {}).get('experience', 0)}%
- Salary: {match_scores.get('components', {}).get('salary', 0)}%
- Location: {match_scores.get('components', {}).get('location', 0)}%
- Title: {match_scores.get('components', {}).get('title', 0)}%

Respond in this exact JSON format:
{{
    "explanation": "2-3 sentence explanation of why this is/isn't a good match. Be specific about the candidate's actual skills and the job's requirements.",
    "strength": "The single biggest strength (1 sentence)",
    "gap": "The single biggest gap, or 'None identified' if 90%+ match (1 sentence)",
    "action_item": "One specific thing the candidate could do to improve their match (1 sentence)"
}}

Be conversational, specific, and actionable. Reference actual skills and requirements."""

    def generate_explanation(
        self,
        user_profile: dict,
        job: dict,
        match_scores: dict
    ) -> ExplanationResult:
        """
        Generate a natural language explanation for the match score.

        Args:
            user_profile: User's profile data
            job: Job listing data
            match_scores: Output from JobMatcher.compute_match_score()

        Returns:
            ExplanationResult with explanation and metadata
        """
        prompt = self._build_prompt(user_profile, job, match_scores)

        try:
            if self.provider == "openai" or self.provider == "xai":
                response = self._call_openai_compatible(prompt)
            elif self.provider == "anthropic":
                response = self._call_anthropic(prompt)
            else:
                raise ValueError(f"Unknown provider: {self.provider}")

            return response

        except Exception as e:
            # Fallback to template-based explanation
            return self._fallback_explanation(match_scores, str(e))

    def _call_openai_compatible(self, prompt: str) -> ExplanationResult:
        """Call OpenAI or xAI API."""
        model = "gpt-4o-mini" if self.provider == "openai" else "grok-3-mini"

        response = self.client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "You are a helpful career advisor. Always respond with valid JSON."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=400,
            temperature=0.7,
        )

        content = response.choices[0].message.content
        tokens = response.usage.total_tokens

        # Parse JSON response
        try:
            # Handle potential markdown code blocks
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]

            data = json.loads(content.strip())
        except json.JSONDecodeError:
            # If JSON parsing fails, use the raw response
            data = {
                "explanation": content,
                "strength": "See explanation above",
                "gap": "See explanation above",
                "action_item": "Review the detailed explanation"
            }

        # Calculate cost (approximate)
        if self.provider == "openai":
            cost = tokens * 0.00000015  # GPT-4o-mini pricing
        else:
            cost = tokens * 0.000005  # Grok pricing estimate

        return ExplanationResult(
            explanation=data.get("explanation", ""),
            strength=data.get("strength", ""),
            gap=data.get("gap", ""),
            action_item=data.get("action_item", ""),
            model=model,
            tokens_used=tokens,
            cost_usd=cost
        )

    def _call_anthropic(self, prompt: str) -> ExplanationResult:
        """Call Anthropic Claude API."""
        response = self.client.messages.create(
            model="claude-3-haiku-20240307",
            max_tokens=400,
            messages=[{"role": "user", "content": prompt}]
        )

        content = response.content[0].text
        tokens = response.usage.input_tokens + response.usage.output_tokens

        try:
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            data = json.loads(content.strip())
        except json.JSONDecodeError:
            data = {
                "explanation": content,
                "strength": "See explanation above",
                "gap": "See explanation above",
                "action_item": "Review the detailed explanation"
            }

        return ExplanationResult(
            explanation=data.get("explanation", ""),
            strength=data.get("strength", ""),
            gap=data.get("gap", ""),
            action_item=data.get("action_item", ""),
            model="claude-3-haiku",
            tokens_used=tokens,
            cost_usd=tokens * 0.00000025  # Haiku pricing
        )

    def _fallback_explanation(
        self,
        match_scores: dict,
        error: str = ""
    ) -> ExplanationResult:
        """Generate template-based explanation when LLM fails."""
        score = match_scores.get('total_score', 0)
        components = match_scores.get('components', {})

        # Find strongest and weakest
        if components:
            strongest = max(components, key=components.get)
            weakest = min(components, key=components.get)
        else:
            strongest = "skills"
            weakest = "experience"

        if score >= 85:
            explanation = f"This is an excellent match! Your profile aligns well with this role across most factors."
        elif score >= 70:
            explanation = f"This is a good match with some room for improvement. Your {strongest} score is particularly strong."
        elif score >= 50:
            explanation = f"This is a moderate match. Consider focusing on improving your {weakest} alignment."
        else:
            explanation = f"This may not be the best fit. The main gap appears to be in {weakest}."

        return ExplanationResult(
            explanation=explanation,
            strength=f"Your {strongest} alignment is strong at {components.get(strongest, 0)}%",
            gap=f"Consider improving {weakest} (currently {components.get(weakest, 0)}%)" if score < 90 else "None identified",
            action_item=f"Focus on strengthening your {weakest} to improve this match",
            model="fallback-template",
            tokens_used=0,
            cost_usd=0.0
        )


# Convenience function for quick usage
def explain_match(
    user_profile: dict,
    job: dict,
    match_scores: dict,
    provider: str = None
) -> dict:
    """
    Generate a natural language explanation for a job match.

    Example usage:
        from app.services.llm_explainer import explain_match

        explanation = explain_match(
            user_profile={"skills": ["Python", "ML"], "years_experience": 5},
            job={"title": "ML Engineer", "required_skills": ["Python", "TensorFlow"]},
            match_scores={"total_score": 87, "components": {"skills": 92, ...}}
        )
        print(explanation["explanation"])

    Returns:
        Dict with explanation, strength, gap, action_item, and metadata
    """
    explainer = LLMExplainer(provider=provider)
    result = explainer.generate_explanation(user_profile, job, match_scores)

    return {
        "explanation": result.explanation,
        "strength": result.strength,
        "gap": result.gap,
        "action_item": result.action_item,
        "metadata": {
            "model": result.model,
            "tokens_used": result.tokens_used,
            "cost_usd": result.cost_usd
        }
    }
