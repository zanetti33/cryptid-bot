from __future__ import annotations

from threading import Lock
from typing import Callable, Dict, Optional

from spa_recognition.backend.models import SessionState


class SessionStore:
    """In-memory session store used by the SPA backend V1."""

    def __init__(self) -> None:
        self._sessions: Dict[str, SessionState] = {}
        self._lock = Lock()

    def get(self, session_id: str) -> Optional[SessionState]:
        with self._lock:
            return self._sessions.get(session_id)

    def create_or_get(self, session_id: str) -> SessionState:
        with self._lock:
            existing = self._sessions.get(session_id)
            if existing is not None:
                return existing
            created = SessionState(session_id=session_id)
            self._sessions[session_id] = created
            return created

    def upsert(self, session: SessionState) -> SessionState:
        with self._lock:
            self._sessions[session.session_id] = session
            return session

    def update(self, session_id: str, updater: Callable[[SessionState], SessionState]) -> SessionState:
        with self._lock:
            current = self._sessions.get(session_id)
            if current is None:
                current = SessionState(session_id=session_id)
            updated = updater(current)
            self._sessions[session_id] = updated
            return updated

    def reset(self, session_id: str) -> SessionState:
        with self._lock:
            reset_state = SessionState(session_id=session_id)
            self._sessions[session_id] = reset_state
            return reset_state

