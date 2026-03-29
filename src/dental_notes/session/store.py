"""Session persistence layer for saving and loading dental sessions.

Sessions are stored as JSON files in the sessions directory. Each session
contains transcript chunks, extraction results, and editing state.
Atomic writes via temp file + os.replace prevent data corruption.
"""

import json
import os
import tempfile
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from uuid import uuid4

from pydantic import BaseModel, Field

from dental_notes.clinical.models import ExtractionResult


class SessionStatus(str, Enum):
    """Status of a saved session in the review workflow."""

    RECORDED = "recorded"
    EXTRACTED = "extracted"
    REVIEWED = "reviewed"


class SavedSession(BaseModel):
    """A persisted dental appointment session.

    Tracks transcript chunks, extraction results, user edits, and
    workflow status through the review pipeline.
    """

    session_id: str = Field(default_factory=lambda: str(uuid4()))
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    status: SessionStatus = SessionStatus.RECORDED
    transcript_path: str
    chunks: list[tuple[str, str]]
    extraction_result: ExtractionResult | None = None
    edited_note: dict | None = None
    transcript_dirty: bool = False
    appointment_type: str = "general"
    patient_summary: dict | None = None


class SessionStore:
    """Persists sessions as JSON files with atomic writes.

    Each session is stored as {session_id}.json in the sessions directory.
    Writes use a temp file + os.replace pattern to prevent partial writes.
    """

    def __init__(self, sessions_dir: Path) -> None:
        self._sessions_dir = sessions_dir
        self._sessions_dir.mkdir(parents=True, exist_ok=True)

    def create_session(
        self,
        chunks: list[tuple[str, str]],
        transcript_path: str,
    ) -> SavedSession:
        """Create and persist a new session with RECORDED status."""
        session = SavedSession(
            transcript_path=transcript_path,
            chunks=chunks,
        )
        self._write(session)
        return session

    def get_session(self, session_id: str) -> SavedSession | None:
        """Load a session from its JSON file, or None if not found."""
        json_path = self._sessions_dir / f"{session_id}.json"
        if not json_path.exists():
            return None
        data = json.loads(json_path.read_text(encoding="utf-8"))
        return SavedSession.model_validate(data)

    def list_sessions(self) -> list[SavedSession]:
        """Return all sessions sorted by created_at descending (newest first)."""
        sessions: list[SavedSession] = []
        for json_path in self._sessions_dir.glob("*.json"):
            data = json.loads(json_path.read_text(encoding="utf-8"))
            sessions.append(SavedSession.model_validate(data))
        sessions.sort(key=lambda s: s.created_at, reverse=True)
        return sessions

    def update_session(self, session: SavedSession) -> None:
        """Write updated session back to disk with refreshed updated_at."""
        session.updated_at = datetime.now(timezone.utc)
        self._write(session)

    def delete_session(self, session_id: str) -> None:
        """Remove a session JSON file from disk."""
        json_path = self._sessions_dir / f"{session_id}.json"
        json_path.unlink(missing_ok=True)

    def finalize_session(self, session_id: str) -> None:
        """Delete transcript file and session JSON (ephemeral cleanup).

        Uses missing_ok=True so already-deleted transcripts don't raise.
        Satisfies AUD-02: transcript deleted after note finalization.
        """
        session = self.get_session(session_id)
        if session is not None:
            Path(session.transcript_path).unlink(missing_ok=True)
        self.delete_session(session_id)

    def _write(self, session: SavedSession) -> None:
        """Atomic write: temp file in sessions_dir, then os.replace.

        This prevents partial writes from corrupting session data if the
        process is interrupted mid-write.
        """
        json_path = self._sessions_dir / f"{session.session_id}.json"
        fd, tmp_path = tempfile.mkstemp(
            dir=self._sessions_dir, suffix=".tmp"
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(session.model_dump_json(indent=2))
            os.replace(tmp_path, json_path)
        except BaseException:
            # Clean up temp file on any failure
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
            raise
