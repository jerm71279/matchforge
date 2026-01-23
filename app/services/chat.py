"""
MatchForge Chat Service
WebSocket-based chat for coach sessions
"""
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from fastapi import WebSocket
from dataclasses import dataclass, asdict


@dataclass
class ChatMessage:
    """A single chat message"""
    sender_id: str
    sender_type: str  # "user" or "coach"
    content: str
    timestamp: str
    message_type: str = "text"  # text, system, typing

    def to_dict(self) -> dict:
        return asdict(self)


class ConnectionManager:
    """
    Manages WebSocket connections for coach-user chat sessions.
    """

    def __init__(self):
        # Active connections by session_id
        self.active_connections: Dict[str, List[WebSocket]] = {}
        # Message history (in production, store in database)
        self.message_history: Dict[str, List[dict]] = {}
        # Typing indicators
        self.typing_status: Dict[str, Dict[str, bool]] = {}

    async def connect(self, websocket: WebSocket, session_id: str, user_id: str):
        """Accept and register a WebSocket connection."""
        await websocket.accept()

        if session_id not in self.active_connections:
            self.active_connections[session_id] = []
            self.message_history[session_id] = []
            self.typing_status[session_id] = {}

        self.active_connections[session_id].append(websocket)

        # Send connection confirmation
        await websocket.send_json({
            "type": "connected",
            "session_id": session_id,
            "user_id": user_id,
            "timestamp": datetime.utcnow().isoformat()
        })

        # Send message history
        if self.message_history[session_id]:
            await websocket.send_json({
                "type": "history",
                "messages": self.message_history[session_id]
            })

    def disconnect(self, websocket: WebSocket, session_id: str):
        """Remove a WebSocket connection."""
        if session_id in self.active_connections:
            if websocket in self.active_connections[session_id]:
                self.active_connections[session_id].remove(websocket)

            # Clean up empty sessions
            if not self.active_connections[session_id]:
                del self.active_connections[session_id]

    async def send_to_session(self, session_id: str, message: dict):
        """Broadcast message to all participants in a session."""
        if session_id in self.active_connections:
            disconnected = []
            for connection in self.active_connections[session_id]:
                try:
                    await connection.send_json(message)
                except:
                    disconnected.append(connection)

            # Clean up disconnected
            for conn in disconnected:
                self.disconnect(conn, session_id)

        # Store in history (except typing indicators)
        if message.get("type") == "message":
            if session_id not in self.message_history:
                self.message_history[session_id] = []
            self.message_history[session_id].append(message)

    async def handle_message(self, session_id: str, data: dict):
        """Process incoming message and broadcast to session."""
        msg_type = data.get("type", "message")

        if msg_type == "typing":
            # Typing indicator
            self.typing_status.setdefault(session_id, {})[data.get("sender_id")] = data.get("is_typing", False)
            await self.send_to_session(session_id, {
                "type": "typing",
                "sender_id": data.get("sender_id"),
                "is_typing": data.get("is_typing", False)
            })

        elif msg_type == "message":
            message = ChatMessage(
                sender_id=data.get("sender_id"),
                sender_type=data.get("sender_type", "user"),
                content=data.get("content", ""),
                timestamp=datetime.utcnow().isoformat(),
                message_type="text"
            )
            await self.send_to_session(session_id, {
                "type": "message",
                **message.to_dict()
            })

            # Clear typing indicator
            self.typing_status.setdefault(session_id, {})[data.get("sender_id")] = False

    def get_session_status(self, session_id: str) -> dict:
        """Get status of a chat session."""
        return {
            "session_id": session_id,
            "active_connections": len(self.active_connections.get(session_id, [])),
            "message_count": len(self.message_history.get(session_id, [])),
            "typing": self.typing_status.get(session_id, {})
        }


# Global connection manager instance
chat_manager = ConnectionManager()


class CoachScheduler:
    """
    Simple coach scheduling without external dependencies.
    For MVP - can be replaced with Cal.com integration later.
    """

    def __init__(self):
        # Mock coach availability (in production, from database)
        self.coaches = {
            "coach_1": {
                "name": "Sarah Johnson",
                "expertise": ["resume", "interview", "career_change"],
                "available_hours": list(range(9, 17)),  # 9 AM - 5 PM
            },
            "coach_2": {
                "name": "Mike Chen",
                "expertise": ["salary", "tech", "networking"],
                "available_hours": list(range(10, 18)),  # 10 AM - 6 PM
            }
        }
        # Booked sessions (in production, from database)
        self.bookings: Dict[str, List[datetime]] = {}

    def get_available_slots(
        self,
        coach_id: Optional[str] = None,
        start_date: datetime = None,
        days_ahead: int = 14
    ) -> List[dict]:
        """Get available 30-minute slots."""
        start_date = start_date or datetime.utcnow()
        slots = []

        coaches_to_check = [coach_id] if coach_id else list(self.coaches.keys())

        for cid in coaches_to_check:
            if cid not in self.coaches:
                continue

            coach = self.coaches[cid]
            booked = set(self.bookings.get(cid, []))

            for day_offset in range(days_ahead):
                date = start_date + timedelta(days=day_offset)

                for hour in coach["available_hours"]:
                    for minute in [0, 30]:
                        slot_time = date.replace(hour=hour, minute=minute, second=0, microsecond=0)

                        if slot_time > datetime.utcnow() and slot_time not in booked:
                            slots.append({
                                "coach_id": cid,
                                "coach_name": coach["name"],
                                "start_time": slot_time.isoformat(),
                                "end_time": (slot_time + timedelta(minutes=30)).isoformat(),
                                "expertise": coach["expertise"]
                            })

        return sorted(slots, key=lambda x: x["start_time"])[:50]

    def book_slot(
        self,
        user_id: str,
        coach_id: str,
        start_time: datetime
    ) -> dict:
        """Book a coaching slot."""
        if coach_id not in self.coaches:
            return {"success": False, "error": "Coach not found"}

        if coach_id not in self.bookings:
            self.bookings[coach_id] = []

        if start_time in self.bookings[coach_id]:
            return {"success": False, "error": "Slot already booked"}

        self.bookings[coach_id].append(start_time)

        session_id = f"{user_id}_{coach_id}_{int(start_time.timestamp())}"

        return {
            "success": True,
            "session": {
                "session_id": session_id,
                "coach_id": coach_id,
                "coach_name": self.coaches[coach_id]["name"],
                "start_time": start_time.isoformat(),
                "end_time": (start_time + timedelta(minutes=30)).isoformat(),
                "join_url": f"/chat/{session_id}"
            }
        }

    def cancel_slot(self, coach_id: str, start_time: datetime) -> bool:
        """Cancel a booked slot."""
        if coach_id in self.bookings and start_time in self.bookings[coach_id]:
            self.bookings[coach_id].remove(start_time)
            return True
        return False


# Global scheduler instance
coach_scheduler = CoachScheduler()
