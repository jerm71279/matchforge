"""
MatchForge Coach AI Assistant
Drafts responses for coaching sessions using LLM
"""
import os
import json
from typing import Optional


async def draft_coach_response(
    user_question: str,
    user_profile: dict,
    conversation_history: list[dict],
    provider: str = "auto"
) -> dict:
    """
    Generate a draft response for a coaching question.

    Args:
        user_question: The user's question
        user_profile: User's profile data
        conversation_history: Recent messages in the conversation
        provider: LLM provider (auto, openai, anthropic, mock)

    Returns:
        Dict with draft response and metadata
    """
    # Auto-select provider
    if provider == "auto":
        if os.getenv("ANTHROPIC_API_KEY"):
            provider = "anthropic"
        elif os.getenv("OPENAI_API_KEY"):
            provider = "openai"
        else:
            provider = "mock"

    if provider == "mock":
        return _generate_mock_response(user_question, user_profile)

    if provider == "anthropic":
        return await _generate_anthropic_response(user_question, user_profile, conversation_history)

    if provider == "openai":
        return await _generate_openai_response(user_question, user_profile, conversation_history)

    return _generate_mock_response(user_question, user_profile)


async def _generate_openai_response(
    user_question: str,
    user_profile: dict,
    conversation_history: list[dict]
) -> dict:
    """Generate coach response using OpenAI."""
    try:
        from openai import OpenAI
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

        prompt = _build_coach_prompt(user_question, user_profile, conversation_history)

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are an experienced career coach. Be helpful, specific, and encouraging."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=300,
            temperature=0.7
        )

        draft = response.choices[0].message.content
        needs_review = "[COACH:" in draft or "[verify" in draft.lower()

        return {
            "draft_response": draft,
            "confidence": "needs_review" if needs_review else "high",
            "suggested_followup": _get_followup_suggestion(user_question),
            "metadata": {
                "model": "gpt-4o-mini",
                "tokens_used": response.usage.total_tokens,
                "cost_usd": response.usage.total_tokens * 0.00000015
            }
        }

    except Exception as e:
        print(f"OpenAI coach error: {e}")
        return _generate_mock_response(user_question, user_profile)


async def _generate_anthropic_response(
    user_question: str,
    user_profile: dict,
    conversation_history: list[dict]
) -> dict:
    """Generate coach response using Anthropic Claude."""
    try:
        from anthropic import Anthropic
        client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

        prompt = _build_coach_prompt(user_question, user_profile, conversation_history)

        response = client.messages.create(
            model="claude-3-haiku-20240307",
            max_tokens=300,
            messages=[
                {"role": "user", "content": prompt}
            ],
            system="You are an experienced career coach. Be helpful, specific, and encouraging. Keep responses concise but actionable."
        )

        draft = response.content[0].text
        needs_review = "[COACH:" in draft or "[verify" in draft.lower()

        return {
            "draft_response": draft,
            "confidence": "needs_review" if needs_review else "high",
            "suggested_followup": _get_followup_suggestion(user_question),
            "metadata": {
                "model": "claude-3-haiku",
                "tokens_used": response.usage.input_tokens + response.usage.output_tokens,
                "cost_usd": (response.usage.input_tokens * 0.00000025 + response.usage.output_tokens * 0.00000125)
            }
        }

    except Exception as e:
        print(f"Anthropic coach error: {e}")
        return _generate_mock_response(user_question, user_profile)


def _build_coach_prompt(
    user_question: str,
    user_profile: dict,
    conversation_history: list[dict]
) -> str:
    """Build the prompt for coach response generation."""
    # Format recent conversation
    history_text = ""
    for msg in conversation_history[-5:]:  # Last 5 messages
        sender = "User" if msg.get("sender_type") == "user" else "Coach"
        history_text += f"{sender}: {msg.get('content', '')}\n"

    return f"""You are assisting a career coach. Draft a response to this job seeker's question.

USER PROFILE:
- Experience: {user_profile.get('years_experience', 'Not specified')} years
- Skills: {', '.join(user_profile.get('skills', [])) or 'Not specified'}
- Target roles: {', '.join(user_profile.get('target_titles', [])) or 'Not specified'}
- Career level: {user_profile.get('career_level', 'Not specified')}

RECENT CONVERSATION:
{history_text or 'No previous messages'}

USER'S CURRENT QUESTION:
{user_question}

Draft a helpful response that:
1. Directly addresses their question
2. Provides specific, actionable advice
3. Is encouraging but realistic
4. Suggests a concrete next step
5. Is 2-4 sentences long

If you're uncertain about specific details (like company policies or salary numbers), mark with [COACH: verify this].
Keep the response conversational and supportive."""


def _generate_mock_response(user_question: str, user_profile: dict) -> dict:
    """Generate a template response without LLM."""
    question_lower = user_question.lower()

    # Template responses based on question type
    if any(word in question_lower for word in ["resume", "cv"]):
        draft = "Your resume should highlight your key achievements with quantifiable results. Focus on the skills that match your target roles. Would you like me to review specific sections of your resume?"
    elif any(word in question_lower for word in ["interview", "prepare"]):
        draft = "Great question about interview prep! I recommend researching the company thoroughly, preparing STAR-method stories for behavioral questions, and practicing common technical questions for your field. What type of interview are you preparing for?"
    elif any(word in question_lower for word in ["salary", "negotiate", "compensation"]):
        draft = "Salary negotiation is important! Research market rates on Glassdoor and Levels.fyi for your role and location. Come prepared with your value proposition and be ready to discuss the total compensation package. [COACH: verify current market rates for their specific role]"
    elif any(word in question_lower for word in ["job search", "finding", "looking"]):
        draft = "For your job search, I recommend a multi-pronged approach: networking (80% of jobs are filled through connections), targeted applications to companies you're excited about, and keeping your LinkedIn profile updated. What's been your main job search strategy so far?"
    elif any(word in question_lower for word in ["skill", "learn", "improve"]):
        draft = "Continuous learning is essential! Based on your profile, focusing on high-demand skills in your target field would be valuable. Online platforms like Coursera, Udemy, and YouTube have great resources. What specific skill area interests you most?"
    else:
        draft = "That's a great question. Let me think about the best approach for your situation. Could you tell me more about your specific goals and what challenges you're facing? That will help me give you more targeted advice."

    return {
        "draft_response": draft,
        "confidence": "template",
        "suggested_followup": _get_followup_suggestion(user_question),
        "metadata": {
            "model": "template",
            "tokens_used": 0,
            "cost_usd": 0
        }
    }


def _get_followup_suggestion(question: str) -> str:
    """Suggest a follow-up question based on the topic."""
    question_lower = question.lower()

    if "resume" in question_lower:
        return "Would you like me to review a specific section of your resume?"
    elif "interview" in question_lower:
        return "Would you like to do a mock interview practice?"
    elif "salary" in question_lower:
        return "Do you have a specific offer you'd like help evaluating?"
    elif "skill" in question_lower:
        return "What's your timeline for learning this skill?"
    else:
        return "Is there anything specific you'd like me to elaborate on?"


def get_coaching_topics() -> list[dict]:
    """Return common coaching topics for UI suggestions."""
    return [
        {"topic": "Resume Review", "prompt": "Can you help me improve my resume?"},
        {"topic": "Interview Prep", "prompt": "How should I prepare for interviews?"},
        {"topic": "Salary Negotiation", "prompt": "How do I negotiate a better salary?"},
        {"topic": "Career Change", "prompt": "I'm thinking about changing careers. Where do I start?"},
        {"topic": "Skill Development", "prompt": "What skills should I learn for my target role?"},
        {"topic": "Job Search Strategy", "prompt": "What's the best job search strategy?"},
        {"topic": "Networking", "prompt": "How can I network more effectively?"},
        {"topic": "LinkedIn Profile", "prompt": "How can I improve my LinkedIn profile?"},
    ]
