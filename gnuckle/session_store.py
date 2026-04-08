"""File-backed session storage for agentic benchmark runs."""

from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

from gnuckle.agentic_types import SessionState


class SessionStore:
    def __init__(self, root_dir: Path):
        self.root_dir = Path(root_dir)
        self.root_dir.mkdir(parents=True, exist_ok=True)

    def _session_path(self, session_id: str) -> Path:
        return self.root_dir / f"{session_id}.json"

    def load_or_create(self, workflow_id: str, session_mode: str) -> SessionState:
        if session_mode == "full_history":
            session_id = f"{workflow_id}_full_history"
            session = self.load(session_id)
            if session is not None:
                return session
        else:
            session_id = f"{workflow_id}_{uuid4().hex[:12]}"

        session = SessionState(
            session_id=session_id,
            workflow_id=workflow_id,
            session_mode=session_mode,
            messages=[],
            episodes_run=0,
        )
        self.save(session)
        return session

    def load(self, session_id: str) -> SessionState | None:
        path = self._session_path(session_id)
        if not path.exists():
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
        return SessionState(
            session_id=data["session_id"],
            workflow_id=data["workflow_id"],
            session_mode=data["session_mode"],
            messages=list(data.get("messages", [])),
            episodes_run=int(data.get("episodes_run", 0)),
        )

    def save(self, session: SessionState) -> Path:
        path = self._session_path(session.session_id)
        path.write_text(json.dumps(session.to_dict(), indent=2), encoding="utf-8")
        return path
