"""
SwarmCorp — Session Management
Tracks multiple simulation sessions for the dashboard.
"""
import json
import os
import re
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
        self.archived_sessions: list[dict] = []

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

        # Append archived sessions (skip duplicates)
        active_ids = {s["session_id"] for s in result}
        for archived in self.archived_sessions:
            if archived["session_id"] not in active_ids:
                result.append(archived)

        return result

    @staticmethod
    def _sanitize_name(name: str) -> str:
        sanitized = re.sub(r'[^\w\s-]', '', name)
        sanitized = re.sub(r'\s+', '_', sanitized.strip())
        return sanitized[:50] or "unnamed"

    def archive_session(self, session_id: str, archive_root: str):
        """Archive a completed session to disk."""
        session = self.sessions.get(session_id)
        if not session or session.status != "complete" or session.state is None:
            return

        state = session.state
        sanitized = self._sanitize_name(
            getattr(state, "company_name", "") or session.idea
        )
        dir_name = f"{session_id}_{sanitized}"
        archive_dir = os.path.join(archive_root, dir_name)
        os.makedirs(archive_dir, exist_ok=True)

        # 1. Full state
        state.save(os.path.join(archive_dir, "state.json"))
        print(f"     💾 state.json")

        # 2. Conversation log
        log_path = os.path.join(archive_dir, "conversation_log.json")
        with open(log_path, "w", encoding="utf-8") as f:
            json.dump(
                getattr(state, "conversation_log", []),
                f, ensure_ascii=False, indent=2,
            )
        print(f"     💾 conversation_log.json ({len(getattr(state, 'conversation_log', []))} Einträge)")

        # 3. Human-readable summary
        summary_path = os.path.join(archive_dir, "summary.md")
        with open(summary_path, "w", encoding="utf-8") as f:
            f.write(state.generate_summary())
        print(f"     💾 summary.md")

        # 4. Lightweight metadata for fast sidebar loading
        fb = getattr(state, "feedback_history", [])
        meta = {
            "session_id": session_id,
            "idea": session.idea,
            "company_name": getattr(state, "company_name", ""),
            "satisfaction": fb[-1].get("satisfaction_score") if fb else None,
            "cost": getattr(state, "total_cost", 0.0),
            "status": "archived",
            "created_at": session.created_at,
            "archived_at": datetime.now().isoformat(),
        }
        meta_path = os.path.join(archive_dir, "session_meta.json")
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)
        print(f"     💾 session_meta.json")
        print(f"     📁 Archiv: {archive_dir}")

    def load_archived_sessions(self, archive_root: str):
        """Scan archive directory and load session metadata for sidebar."""
        self.archived_sessions = []
        if not os.path.isdir(archive_root):
            return

        for entry in sorted(os.listdir(archive_root)):
            entry_path = os.path.join(archive_root, entry)
            if not os.path.isdir(entry_path):
                continue

            meta_path = os.path.join(entry_path, "session_meta.json")
            if os.path.isfile(meta_path):
                try:
                    with open(meta_path, encoding="utf-8") as f:
                        meta = json.load(f)
                    meta["status"] = "archived"
                    self.archived_sessions.append(meta)
                except (json.JSONDecodeError, OSError):
                    continue
