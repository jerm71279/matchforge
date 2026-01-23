"""
MatchForge Coaching API
Coach scheduling and chat sessions
"""
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional

from app.core.database import get_db
from app.core.security import get_current_user_id
from app.models.user import User
from app.models.feedback import CoachSession
from app.schemas.feedback import CoachSessionCreate, CoachSessionResponse, CoachSessionFeedback
from app.services.chat import chat_manager, coach_scheduler

router = APIRouter(prefix="/coaching", tags=["Coaching"])


@router.get("/slots")
async def get_available_slots(
    coach_id: Optional[str] = None,
    days_ahead: int = 14,
    user_id: str = Depends(get_current_user_id)
):
    """
    Get available coaching slots.

    Returns 30-minute slots for the next 14 days.
    """
    slots = coach_scheduler.get_available_slots(
        coach_id=coach_id,
        days_ahead=days_ahead
    )
    return {"slots": slots}


@router.post("/book", response_model=dict)
async def book_session(
    booking: CoachSessionCreate,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db)
):
    """
    Book a coaching session.

    Requires available coaching sessions in user's subscription.
    """
    # Check user has sessions remaining
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if user.coaching_sessions_remaining <= 0:
        raise HTTPException(
            status_code=402,
            detail="No coaching sessions remaining. Please upgrade your plan."
        )

    # Parse datetime
    start_time = booking.scheduled_start

    # Find available coach if not specified
    coach_id = booking.coach_id
    if not coach_id:
        slots = coach_scheduler.get_available_slots()
        if not slots:
            raise HTTPException(status_code=404, detail="No coaches available")
        coach_id = slots[0]["coach_id"]

    # Book the slot
    result = coach_scheduler.book_slot(user_id, coach_id, start_time)

    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["error"])

    # Decrement user's sessions
    user.coaching_sessions_remaining -= 1
    db.add(user)

    # Create session record
    session = CoachSession(
        user_id=user_id,
        coach_id=coach_id,
        session_type=booking.session_type,
        scheduled_start=start_time,
        scheduled_end=start_time.replace(minute=start_time.minute + 30),
        status="scheduled"
    )
    db.add(session)
    await db.flush()

    return result


@router.get("/sessions", response_model=list[CoachSessionResponse])
async def get_sessions(
    status: Optional[str] = None,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db)
):
    """Get user's coaching sessions."""
    query = select(CoachSession).where(CoachSession.user_id == user_id)

    if status:
        query = query.where(CoachSession.status == status)

    query = query.order_by(CoachSession.scheduled_start.desc())

    result = await db.execute(query)
    sessions = result.scalars().all()

    # Add join URLs
    response = []
    for session in sessions:
        session_dict = {
            "id": session.id,
            "user_id": session.user_id,
            "coach_id": session.coach_id,
            "session_type": session.session_type,
            "scheduled_start": session.scheduled_start,
            "scheduled_end": session.scheduled_end,
            "status": session.status,
            "join_url": f"/chat/{session.user_id}_{session.coach_id}_{int(session.scheduled_start.timestamp())}" if session.status == "scheduled" else None
        }
        response.append(session_dict)

    return response


@router.post("/sessions/{session_id}/cancel")
async def cancel_session(
    session_id: str,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db)
):
    """
    Cancel a coaching session.

    Refund if cancelled >24 hours in advance.
    """
    result = await db.execute(
        select(CoachSession).where(
            CoachSession.id == session_id,
            CoachSession.user_id == user_id
        )
    )
    session = result.scalar_one_or_none()

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    if session.status != "scheduled":
        raise HTTPException(status_code=400, detail="Cannot cancel this session")

    hours_until = (session.scheduled_start - datetime.utcnow()).total_seconds() / 3600

    session.status = "cancelled"
    db.add(session)

    # Refund if >24 hours notice
    refunded = False
    if hours_until >= 24:
        user_result = await db.execute(select(User).where(User.id == user_id))
        user = user_result.scalar_one_or_none()
        if user:
            user.coaching_sessions_remaining += 1
            db.add(user)
            refunded = True

    # Remove from scheduler
    coach_scheduler.cancel_slot(session.coach_id, session.scheduled_start)

    return {
        "success": True,
        "refunded": refunded,
        "message": "Session cancelled" + (" and refunded" if refunded else " (no refund - less than 24h notice)")
    }


@router.post("/sessions/{session_id}/feedback")
async def rate_session(
    session_id: str,
    feedback: CoachSessionFeedback,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db)
):
    """Rate a completed coaching session."""
    result = await db.execute(
        select(CoachSession).where(
            CoachSession.id == session_id,
            CoachSession.user_id == user_id
        )
    )
    session = result.scalar_one_or_none()

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    session.user_rating = feedback.rating
    session.user_feedback = feedback.feedback
    db.add(session)

    return {"success": True}


@router.websocket("/chat/{session_id}")
async def chat_websocket(websocket: WebSocket, session_id: str):
    """
    WebSocket endpoint for real-time coach chat.

    Session ID format: {user_id}_{coach_id}_{timestamp}

    Message format (send):
    {
        "type": "message" | "typing",
        "sender_id": "user_123",
        "sender_type": "user" | "coach",
        "content": "Hello!",  // for message
        "is_typing": true     // for typing
    }

    Message format (receive):
    {
        "type": "message" | "typing" | "history" | "connected",
        ...
    }
    """
    # Extract user_id from session_id for demo
    parts = session_id.split("_")
    user_id = parts[0] if parts else "anonymous"

    await chat_manager.connect(websocket, session_id, user_id)

    try:
        while True:
            data = await websocket.receive_json()
            await chat_manager.handle_message(session_id, data)

    except WebSocketDisconnect:
        chat_manager.disconnect(websocket, session_id)

        # Notify others of disconnect
        await chat_manager.send_to_session(session_id, {
            "type": "system",
            "content": f"User disconnected",
            "timestamp": datetime.utcnow().isoformat()
        })
