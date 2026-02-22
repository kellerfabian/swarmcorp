"""
SwarmCorp — Session Management
Tracks multiple simulation sessions for the dashboard.
"""
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class Session:
    session_id: str
    idea: str
    status: str = "running"  # "running" | "complete" | "error"
    state: Optional[object] = None  # CompanyState (avoid circular import)
    ceo_agent: Optional[object] = None  # CEOAgent
    chat_history: list = field(default_factory=list)
    event_log: list = field(default_factory=list)
    total_cost: float = 0.0
    created_at: str = ""


class SessionManager:
    def __init__(self):
        self.sessions: dict[str, Session] = {}
        self.active_session_id: Optional[str] = None

    def create_session(self, idea: str) -> Session:
        session_id = uuid.uuid4().hex[:12]
        session = Session(
            session_id=session_id,
            idea=idea,
            created_at=datetime.now().isoformat(),
        )
        self.sessions[session_id] = session
        return session

    def get_session(self, session_id: str) -> Optional[Session]:
        return self.sessions.get(session_id)

    def list_sessions(self) -> list[dict]:
        result = []
        for s in self.sessions.values():
            summary = {
                "session_id": s.session_id,
                "idea": s.idea,
                "company_name": "",
                "satisfaction": None,
                "cost": s.total_cost,
                "status": s.status,
            }
            if s.state is not None:
                summary["company_name"] = getattr(s.state, "company_name", "")
                fb = getattr(s.state, "feedback_history", [])
                if fb:
                    summary["satisfaction"] = fb[-1].get("satisfaction_score")
                summary["cost"] = getattr(s.state, "total_cost", s.total_cost)
            result.append(summary)
        return result
