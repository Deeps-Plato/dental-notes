"""Session persistence layer for saving and loading dental sessions.

Sessions are stored as JSON files in the sessions directory. Each session
contains transcript chunks, extraction results, and editing state.
Atomic writes via temp file + os.replace prevent data corruption.

Incomplete sessions (crash recovery) are stored as _incomplete_{id}.json
and can be promoted to completed sessions or deleted.
"""

import json
import os
import tempfile
from datetime import date, datetime, timezone
from enum import Enum
from pathlib import Path
from uuid import uuid4

from pydantic import BaseModel, Field

from dental_notes.clinical.models import ExtractionResult


class SessionStatus(str, Enum):
    """Status of a saved session in the review workflow."""

    INCOMPLETE = "incomplete"
    RECORDED = "recorded"
    EXTRACTED = "extracted"
    REVIEWED = "reviewed"
    COMPLETED = "completed"


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

    def list_sessions(
        self,
        filter_date: date | None = None,
        filter_status: SessionStatus | None = None,
    ) -> list[SavedSession]:
        """Return sessions sorted by created_at descending (newest first).

        By default excludes INCOMPLETE sessions for backward compatibility.
        When filter_status is explicitly set to INCOMPLETE, returns only
        incomplete sessions.

        Args:
            filter_date: If set, only return sessions created on this date.
            filter_status: If set, only return sessions with this status.
        """
        sessions: list[SavedSession] = []
        for json_path in self._sessions_dir.glob("*.json"):
            # Skip incomplete files from the main listing
            if json_path.name.startswith("_incomplete_"):
                continue
            data = json.loads(json_path.read_text(encoding="utf-8"))
            session = SavedSession.model_validate(data)

            # Default behavior: exclude INCOMPLETE unless explicitly requested
            if filter_status is None and session.status == SessionStatus.INCOMPLETE:
                continue
            if filter_status is not None and session.status != filter_status:
                continue
            if filter_date is not None and session.created_at.date() != filter_date:
                continue

            sessions.append(session)
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

    def finalize_session(self, session_id: str) -> SavedSession | None:
        """Mark session as COMPLETED, preserving all data.

        The practitioner can return to copy or revise the note later.
        Data is only permanently deleted by scrub_session().
        """
        session = self.get_session(session_id)
        if session is None:
            return None
        session.status = SessionStatus.COMPLETED
        self.update_session(session)
        return session

    def scrub_session(self, session_id: str) -> None:
        """Permanently delete all session data from disk.

        Removes transcript file, session JSON, and any incomplete files.
        This is irreversible — satisfies AUD-02 when practitioner is
        truly finished with the note.
        """
        session = self.get_session(session_id)
        if session is not None:
            Path(session.transcript_path).unlink(missing_ok=True)
        self.delete_session(session_id)
        self.delete_incomplete(session_id)

    def scrub_all_completed(self) -> int:
        """Permanently delete all COMPLETED sessions from disk.

        Returns the count of sessions scrubbed.
        """
        completed = self.list_sessions(filter_status=SessionStatus.COMPLETED)
        for session in completed:
            Path(session.transcript_path).unlink(missing_ok=True)
            self.delete_session(session.session_id)
        return len(completed)

    def scan_incomplete_sessions(self) -> list[SavedSession]:
        """Find all incomplete session files that don't have completed counterparts.

        Globs for _incomplete_*.json, parses each, and skips any whose
        session_id also has a completed {id}.json file.
        """
        results: list[SavedSession] = []
        for json_path in self._sessions_dir.glob("_incomplete_*.json"):
            data = json.loads(json_path.read_text(encoding="utf-8"))
            session = SavedSession.model_validate(data)
            # Skip if a completed session file exists
            completed_path = self._sessions_dir / f"{session.session_id}.json"
            if completed_path.exists():
                continue
            results.append(session)
        return results

    def save_incomplete(
        self,
        session_id: str,
        chunks: list[tuple[str, str]],
        transcript_path: str,
    ) -> None:
        """Write an incomplete session file for crash recovery.

        Creates _incomplete_{session_id}.json with INCOMPLETE status
        using atomic write pattern (temp file + os.replace).
        """
        session = SavedSession(
            session_id=session_id,
            transcript_path=transcript_path,
            chunks=chunks,
            status=SessionStatus.INCOMPLETE,
        )
        json_path = self._sessions_dir / f"_incomplete_{session_id}.json"
        fd, tmp_path = tempfile.mkstemp(
            dir=self._sessions_dir, suffix=".tmp"
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(session.model_dump_json(indent=2))
            os.replace(tmp_path, json_path)
        except BaseException:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
            raise

    def promote_incomplete(self, session_id: str) -> SavedSession:
        """Promote an incomplete session to RECORDED status.

        Reads the _incomplete_ file, changes status to RECORDED,
        writes as {session_id}.json, and deletes the _incomplete_ file.
        """
        incomplete_path = self._sessions_dir / f"_incomplete_{session_id}.json"
        data = json.loads(incomplete_path.read_text(encoding="utf-8"))
        session = SavedSession.model_validate(data)
        session.status = SessionStatus.RECORDED
        session.updated_at = datetime.now(timezone.utc)
        self._write(session)
        incomplete_path.unlink()
        return session

    def delete_incomplete(self, session_id: str) -> None:
        """Remove an incomplete session file from disk."""
        incomplete_path = self._sessions_dir / f"_incomplete_{session_id}.json"
        incomplete_path.unlink(missing_ok=True)

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
