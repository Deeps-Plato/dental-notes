"""Tests for session persistence layer (SessionStore, SavedSession, SessionStatus).

Tests cover:
- create_session() saves JSON file, returns SavedSession with status RECORDED
- get_session() loads session from JSON, returns None for missing
- list_sessions() returns all sessions sorted by created_at descending
- update_session() writes updated session with new updated_at
- delete_session() removes JSON file
- finalize_session() deletes transcript file + session JSON
- Atomic write via temp file + os.replace
- Enriched SoapNote with medications and va_narrative fields
"""

import json
import os
from pathlib import Path

import pytest


class TestSessionStatus:
    """SessionStatus enum has RECORDED, EXTRACTED, REVIEWED values."""

    def test_recorded_value(self):
        from dental_notes.session.store import SessionStatus

        assert SessionStatus.RECORDED.value == "recorded"

    def test_extracted_value(self):
        from dental_notes.session.store import SessionStatus

        assert SessionStatus.EXTRACTED.value == "extracted"

    def test_reviewed_value(self):
        from dental_notes.session.store import SessionStatus

        assert SessionStatus.REVIEWED.value == "reviewed"


class TestSavedSession:
    """SavedSession Pydantic model validates session data."""

    def test_construction_with_required_fields(self):
        from dental_notes.session.store import SavedSession, SessionStatus

        session = SavedSession(
            session_id="test-123",
            transcript_path="/tmp/test.txt",
            chunks=[("Doctor", "Hello"), ("Patient", "Hi")],
        )
        assert session.session_id == "test-123"
        assert session.status == SessionStatus.RECORDED
        assert session.transcript_path == "/tmp/test.txt"
        assert len(session.chunks) == 2
        assert session.extraction_result is None
        assert session.edited_note is None
        assert session.transcript_dirty is False

    def test_serialization_roundtrip(self):
        from dental_notes.session.store import SavedSession

        session = SavedSession(
            session_id="test-456",
            transcript_path="/tmp/test.txt",
            chunks=[("Doctor", "Open wide")],
        )
        data = json.loads(session.model_dump_json())
        restored = SavedSession.model_validate(data)
        assert restored.session_id == session.session_id
        assert restored.chunks == session.chunks


class TestCreateSession:
    """create_session() persists a new session as JSON."""

    def test_creates_json_file(self, tmp_path: Path):
        from dental_notes.session.store import SessionStore

        store = SessionStore(sessions_dir=tmp_path)
        session = store.create_session(
            chunks=[("Doctor", "Hello")],
            transcript_path="/tmp/transcript.txt",
        )
        json_path = tmp_path / f"{session.session_id}.json"
        assert json_path.exists()

    def test_returns_saved_session_with_recorded_status(self, tmp_path: Path):
        from dental_notes.session.store import SessionStore, SessionStatus

        store = SessionStore(sessions_dir=tmp_path)
        session = store.create_session(
            chunks=[("Doctor", "Hello")],
            transcript_path="/tmp/transcript.txt",
        )
        assert session.status == SessionStatus.RECORDED

    def test_session_has_uuid_id(self, tmp_path: Path):
        from dental_notes.session.store import SessionStore

        store = SessionStore(sessions_dir=tmp_path)
        session = store.create_session(
            chunks=[("Doctor", "Hello")],
            transcript_path="/tmp/transcript.txt",
        )
        # UUID4 format: 8-4-4-4-12 hex chars
        parts = session.session_id.split("-")
        assert len(parts) == 5

    def test_session_stores_chunks(self, tmp_path: Path):
        from dental_notes.session.store import SessionStore

        store = SessionStore(sessions_dir=tmp_path)
        chunks = [("Doctor", "Open wide"), ("Patient", "Okay")]
        session = store.create_session(
            chunks=chunks,
            transcript_path="/tmp/transcript.txt",
        )
        assert session.chunks == chunks


class TestGetSession:
    """get_session() loads a session from its JSON file."""

    def test_loads_existing_session(self, tmp_path: Path):
        from dental_notes.session.store import SessionStore

        store = SessionStore(sessions_dir=tmp_path)
        created = store.create_session(
            chunks=[("Doctor", "Hello")],
            transcript_path="/tmp/transcript.txt",
        )
        loaded = store.get_session(created.session_id)
        assert loaded is not None
        assert loaded.session_id == created.session_id
        assert loaded.chunks == created.chunks

    def test_returns_none_for_missing_session(self, tmp_path: Path):
        from dental_notes.session.store import SessionStore

        store = SessionStore(sessions_dir=tmp_path)
        result = store.get_session("nonexistent-id")
        assert result is None


class TestListSessions:
    """list_sessions() returns all sessions sorted by created_at descending."""

    def test_returns_empty_list_when_no_sessions(self, tmp_path: Path):
        from dental_notes.session.store import SessionStore

        store = SessionStore(sessions_dir=tmp_path)
        assert store.list_sessions() == []

    def test_returns_sessions_sorted_descending(self, tmp_path: Path):
        import time

        from dental_notes.session.store import SessionStore

        store = SessionStore(sessions_dir=tmp_path)
        s1 = store.create_session(
            chunks=[("Doctor", "First")],
            transcript_path="/tmp/t1.txt",
        )
        time.sleep(0.05)  # Ensure different timestamps
        s2 = store.create_session(
            chunks=[("Doctor", "Second")],
            transcript_path="/tmp/t2.txt",
        )
        sessions = store.list_sessions()
        assert len(sessions) == 2
        # Most recent first
        assert sessions[0].session_id == s2.session_id
        assert sessions[1].session_id == s1.session_id

    def test_returns_all_sessions(self, tmp_path: Path):
        from dental_notes.session.store import SessionStore

        store = SessionStore(sessions_dir=tmp_path)
        for i in range(3):
            store.create_session(
                chunks=[("Doctor", f"Session {i}")],
                transcript_path=f"/tmp/t{i}.txt",
            )
        sessions = store.list_sessions()
        assert len(sessions) == 3


class TestUpdateSession:
    """update_session() writes updated session back to disk."""

    def test_updates_session_on_disk(self, tmp_path: Path):
        from dental_notes.session.store import SessionStore, SessionStatus

        store = SessionStore(sessions_dir=tmp_path)
        session = store.create_session(
            chunks=[("Doctor", "Hello")],
            transcript_path="/tmp/transcript.txt",
        )
        session.status = SessionStatus.EXTRACTED
        store.update_session(session)

        reloaded = store.get_session(session.session_id)
        assert reloaded is not None
        assert reloaded.status == SessionStatus.EXTRACTED

    def test_updates_updated_at_timestamp(self, tmp_path: Path):
        from dental_notes.session.store import SessionStore, SessionStatus

        store = SessionStore(sessions_dir=tmp_path)
        session = store.create_session(
            chunks=[("Doctor", "Hello")],
            transcript_path="/tmp/transcript.txt",
        )
        original_updated = session.updated_at
        session.status = SessionStatus.REVIEWED
        store.update_session(session)

        reloaded = store.get_session(session.session_id)
        assert reloaded is not None
        assert reloaded.updated_at > original_updated


class TestDeleteSession:
    """delete_session() removes the JSON file from disk."""

    def test_removes_json_file(self, tmp_path: Path):
        from dental_notes.session.store import SessionStore

        store = SessionStore(sessions_dir=tmp_path)
        session = store.create_session(
            chunks=[("Doctor", "Hello")],
            transcript_path="/tmp/transcript.txt",
        )
        store.delete_session(session.session_id)
        assert not (tmp_path / f"{session.session_id}.json").exists()

    def test_delete_nonexistent_session_succeeds(self, tmp_path: Path):
        from dental_notes.session.store import SessionStore

        store = SessionStore(sessions_dir=tmp_path)
        # Should not raise
        store.delete_session("nonexistent-id")


class TestFinalizeSession:
    """finalize_session() deletes transcript file and session JSON."""

    def test_deletes_transcript_file(self, tmp_path: Path):
        from dental_notes.session.store import SessionStore

        transcript_path = tmp_path / "transcript.txt"
        transcript_path.write_text("Doctor: Hello\nPatient: Hi")
        store = SessionStore(sessions_dir=tmp_path / "sessions")
        session = store.create_session(
            chunks=[("Doctor", "Hello")],
            transcript_path=str(transcript_path),
        )
        store.finalize_session(session.session_id)
        assert not transcript_path.exists()

    def test_deletes_session_json_file(self, tmp_path: Path):
        from dental_notes.session.store import SessionStore

        sessions_dir = tmp_path / "sessions"
        transcript_path = tmp_path / "transcript.txt"
        transcript_path.write_text("test")
        store = SessionStore(sessions_dir=sessions_dir)
        session = store.create_session(
            chunks=[("Doctor", "Hello")],
            transcript_path=str(transcript_path),
        )
        session_id = session.session_id
        store.finalize_session(session_id)
        assert not (sessions_dir / f"{session_id}.json").exists()

    def test_finalize_with_already_deleted_transcript_succeeds(
        self, tmp_path: Path
    ):
        from dental_notes.session.store import SessionStore

        sessions_dir = tmp_path / "sessions"
        store = SessionStore(sessions_dir=sessions_dir)
        session = store.create_session(
            chunks=[("Doctor", "Hello")],
            transcript_path="/tmp/nonexistent-file.txt",
        )
        # Should not raise even though transcript doesn't exist
        store.finalize_session(session.session_id)


class TestAtomicWrite:
    """SessionStore uses atomic write: temp file + os.replace."""

    def test_atomic_write_produces_valid_json(self, tmp_path: Path):
        from dental_notes.session.store import SessionStore

        store = SessionStore(sessions_dir=tmp_path)
        session = store.create_session(
            chunks=[("Doctor", "Hello")],
            transcript_path="/tmp/transcript.txt",
        )
        json_path = tmp_path / f"{session.session_id}.json"
        # File should be valid JSON
        data = json.loads(json_path.read_text())
        assert data["session_id"] == session.session_id

    def test_no_temp_files_left_behind(self, tmp_path: Path):
        from dental_notes.session.store import SessionStore

        store = SessionStore(sessions_dir=tmp_path)
        store.create_session(
            chunks=[("Doctor", "Hello")],
            transcript_path="/tmp/transcript.txt",
        )
        # No .tmp files should remain
        tmp_files = list(tmp_path.glob("*.tmp"))
        assert len(tmp_files) == 0


class TestSavedSessionNewFields:
    """SavedSession has appointment_type and patient_summary fields."""

    def test_appointment_type_defaults_to_general(self):
        from dental_notes.session.store import SavedSession

        session = SavedSession(
            session_id="test-new-1",
            transcript_path="/tmp/test.txt",
            chunks=[("Doctor", "Hello")],
        )
        assert session.appointment_type == "general"

    def test_appointment_type_accepts_custom_value(self):
        from dental_notes.session.store import SavedSession

        session = SavedSession(
            session_id="test-new-2",
            transcript_path="/tmp/test.txt",
            chunks=[("Doctor", "Hello")],
            appointment_type="restorative",
        )
        assert session.appointment_type == "restorative"

    def test_patient_summary_defaults_to_none(self):
        from dental_notes.session.store import SavedSession

        session = SavedSession(
            session_id="test-new-3",
            transcript_path="/tmp/test.txt",
            chunks=[("Doctor", "Hello")],
        )
        assert session.patient_summary is None

    def test_patient_summary_accepts_dict(self):
        from dental_notes.session.store import SavedSession

        summary = {
            "what_we_did": "Fixed a cavity.",
            "whats_next": "Come back in two weeks.",
            "home_care": "Brush gently.",
        }
        session = SavedSession(
            session_id="test-new-4",
            transcript_path="/tmp/test.txt",
            chunks=[("Doctor", "Hello")],
            patient_summary=summary,
        )
        assert session.patient_summary == summary

    def test_json_roundtrip_with_new_fields(self):
        from dental_notes.session.store import SavedSession

        summary = {
            "what_we_did": "Cleaned your teeth.",
            "whats_next": "See you in six months.",
            "home_care": "Floss daily.",
        }
        session = SavedSession(
            session_id="test-new-5",
            transcript_path="/tmp/test.txt",
            chunks=[("Doctor", "Hello")],
            appointment_type="hygiene_recall",
            patient_summary=summary,
        )
        data = json.loads(session.model_dump_json())
        restored = SavedSession.model_validate(data)
        assert restored.appointment_type == "hygiene_recall"
        assert restored.patient_summary == summary

    def test_backward_compat_old_sessions_load(self):
        """Old sessions without new fields should still load correctly."""
        from dental_notes.session.store import SavedSession

        # Simulate old session JSON without new fields
        old_data = {
            "session_id": "old-session-1",
            "created_at": "2026-03-28T12:00:00Z",
            "updated_at": "2026-03-28T12:00:00Z",
            "status": "recorded",
            "transcript_path": "/tmp/old.txt",
            "chunks": [["Doctor", "Hello"]],
            "extraction_result": None,
            "edited_note": None,
            "transcript_dirty": False,
        }
        session = SavedSession.model_validate(old_data)
        assert session.appointment_type == "general"
        assert session.patient_summary is None


# --- Phase 5: INCOMPLETE status + filtering + recovery ---


class TestIncompleteStatus:
    """SessionStatus.INCOMPLETE exists and works with SavedSession."""

    def test_incomplete_status_value(self):
        from dental_notes.session.store import SessionStatus

        assert SessionStatus.INCOMPLETE.value == "incomplete"

    def test_incomplete_status_ordering(self):
        """INCOMPLETE comes before RECORDED in enum ordering."""
        from dental_notes.session.store import SessionStatus

        members = list(SessionStatus)
        incomplete_idx = members.index(SessionStatus.INCOMPLETE)
        recorded_idx = members.index(SessionStatus.RECORDED)
        assert incomplete_idx < recorded_idx

    def test_saved_session_accepts_incomplete_status(self):
        from dental_notes.session.store import SavedSession, SessionStatus

        session = SavedSession(
            session_id="test-incomplete-1",
            transcript_path="/tmp/test.txt",
            chunks=[("Doctor", "Hello")],
            status=SessionStatus.INCOMPLETE,
        )
        assert session.status == SessionStatus.INCOMPLETE

    def test_incomplete_session_json_roundtrip(self):
        import json

        from dental_notes.session.store import SavedSession, SessionStatus

        session = SavedSession(
            session_id="test-incomplete-2",
            transcript_path="/tmp/test.txt",
            chunks=[("Doctor", "Hello")],
            status=SessionStatus.INCOMPLETE,
        )
        data = json.loads(session.model_dump_json())
        restored = SavedSession.model_validate(data)
        assert restored.status == SessionStatus.INCOMPLETE


class TestListSessionsFiltering:
    """list_sessions() supports date and status filtering."""

    def test_no_filters_excludes_incomplete(self, tmp_path: Path):
        """list_sessions() without filters excludes INCOMPLETE sessions."""
        from dental_notes.session.store import (
            SavedSession,
            SessionStatus,
            SessionStore,
        )

        store = SessionStore(sessions_dir=tmp_path)
        # Create a normal session
        store.create_session(
            chunks=[("Doctor", "Hello")],
            transcript_path="/tmp/t1.txt",
        )
        # Create an incomplete session via save_incomplete
        store.save_incomplete(
            session_id="incomplete-1",
            chunks=[("Doctor", "In progress")],
            transcript_path="/tmp/t2.txt",
        )
        sessions = store.list_sessions()
        assert len(sessions) == 1
        assert sessions[0].status != SessionStatus.INCOMPLETE

    def test_filter_by_status(self, tmp_path: Path):
        """list_sessions(filter_status=...) returns only matching status."""
        from dental_notes.session.store import SessionStatus, SessionStore

        store = SessionStore(sessions_dir=tmp_path)
        s1 = store.create_session(
            chunks=[("Doctor", "First")],
            transcript_path="/tmp/t1.txt",
        )
        s2 = store.create_session(
            chunks=[("Doctor", "Second")],
            transcript_path="/tmp/t2.txt",
        )
        # Update one to EXTRACTED
        s2.status = SessionStatus.EXTRACTED
        store.update_session(s2)
        sessions = store.list_sessions(filter_status=SessionStatus.RECORDED)
        assert len(sessions) == 1
        assert sessions[0].session_id == s1.session_id

    def test_filter_by_date(self, tmp_path: Path):
        """list_sessions(filter_date=...) returns only sessions from that date."""
        from datetime import date, datetime, timezone

        from dental_notes.session.store import SavedSession, SessionStore

        store = SessionStore(sessions_dir=tmp_path)
        # Create today's session
        today_session = store.create_session(
            chunks=[("Doctor", "Today")],
            transcript_path="/tmp/t1.txt",
        )
        # Use the UTC date from the created session for filtering
        today_utc = today_session.created_at.date()

        # Create an old session by writing directly
        old_session = SavedSession(
            session_id="old-session-1",
            created_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
            updated_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
            transcript_path="/tmp/old.txt",
            chunks=[("Doctor", "Old")],
        )
        store._write(old_session)

        sessions = store.list_sessions(filter_date=today_utc)
        assert len(sessions) == 1
        assert sessions[0].chunks[0][1] == "Today"


class TestSaveIncomplete:
    """save_incomplete() writes _incomplete_{id}.json with INCOMPLETE status."""

    def test_creates_incomplete_file(self, tmp_path: Path):
        from dental_notes.session.store import SessionStore

        store = SessionStore(sessions_dir=tmp_path)
        store.save_incomplete(
            session_id="inc-1",
            chunks=[("Doctor", "Hello")],
            transcript_path="/tmp/t.txt",
        )
        assert (tmp_path / "_incomplete_inc-1.json").exists()

    def test_incomplete_file_has_incomplete_status(self, tmp_path: Path):
        import json

        from dental_notes.session.store import SessionStore

        store = SessionStore(sessions_dir=tmp_path)
        store.save_incomplete(
            session_id="inc-2",
            chunks=[("Doctor", "Hello")],
            transcript_path="/tmp/t.txt",
        )
        data = json.loads(
            (tmp_path / "_incomplete_inc-2.json").read_text()
        )
        assert data["status"] == "incomplete"


class TestScanIncomplete:
    """scan_incomplete_sessions() finds incomplete session files."""

    def test_returns_incomplete_sessions(self, tmp_path: Path):
        from dental_notes.session.store import SessionStore

        store = SessionStore(sessions_dir=tmp_path)
        store.save_incomplete(
            session_id="inc-a",
            chunks=[("Doctor", "Hello")],
            transcript_path="/tmp/ta.txt",
        )
        store.save_incomplete(
            session_id="inc-b",
            chunks=[("Doctor", "World")],
            transcript_path="/tmp/tb.txt",
        )
        results = store.scan_incomplete_sessions()
        assert len(results) == 2

    def test_skips_completed_sessions(self, tmp_path: Path):
        """If a completed {id}.json exists alongside _incomplete_{id}.json, skip it."""
        from dental_notes.session.store import SessionStore

        store = SessionStore(sessions_dir=tmp_path)
        store.save_incomplete(
            session_id="inc-c",
            chunks=[("Doctor", "Hello")],
            transcript_path="/tmp/tc.txt",
        )
        # Also create a completed session with same ID
        store.create_session.__func__  # just verify it exists
        # Write a completed session file manually
        completed = store.create_session(
            chunks=[("Doctor", "Hello completed")],
            transcript_path="/tmp/tc2.txt",
        )
        # Manually create an incomplete with same ID as the completed one
        store.save_incomplete(
            session_id=completed.session_id,
            chunks=[("Doctor", "incomplete version")],
            transcript_path="/tmp/tc3.txt",
        )
        results = store.scan_incomplete_sessions()
        # Only inc-c should be returned, not the one with matching completed
        ids = [s.session_id for s in results]
        assert "inc-c" in ids
        assert completed.session_id not in ids

    def test_returns_empty_when_none(self, tmp_path: Path):
        from dental_notes.session.store import SessionStore

        store = SessionStore(sessions_dir=tmp_path)
        assert store.scan_incomplete_sessions() == []


class TestPromoteIncomplete:
    """promote_incomplete() renames incomplete file to completed with RECORDED status."""

    def test_promotes_to_recorded(self, tmp_path: Path):
        from dental_notes.session.store import SessionStatus, SessionStore

        store = SessionStore(sessions_dir=tmp_path)
        store.save_incomplete(
            session_id="promo-1",
            chunks=[("Doctor", "Hello")],
            transcript_path="/tmp/t.txt",
        )
        result = store.promote_incomplete("promo-1")
        assert result.status == SessionStatus.RECORDED
        assert result.session_id == "promo-1"

    def test_removes_incomplete_file(self, tmp_path: Path):
        from dental_notes.session.store import SessionStore

        store = SessionStore(sessions_dir=tmp_path)
        store.save_incomplete(
            session_id="promo-2",
            chunks=[("Doctor", "Hello")],
            transcript_path="/tmp/t.txt",
        )
        store.promote_incomplete("promo-2")
        assert not (tmp_path / "_incomplete_promo-2.json").exists()

    def test_creates_completed_file(self, tmp_path: Path):
        from dental_notes.session.store import SessionStore

        store = SessionStore(sessions_dir=tmp_path)
        store.save_incomplete(
            session_id="promo-3",
            chunks=[("Doctor", "Hello")],
            transcript_path="/tmp/t.txt",
        )
        store.promote_incomplete("promo-3")
        assert (tmp_path / "promo-3.json").exists()


class TestDeleteIncomplete:
    """delete_incomplete() removes the _incomplete_ file."""

    def test_deletes_incomplete_file(self, tmp_path: Path):
        from dental_notes.session.store import SessionStore

        store = SessionStore(sessions_dir=tmp_path)
        store.save_incomplete(
            session_id="del-1",
            chunks=[("Doctor", "Hello")],
            transcript_path="/tmp/t.txt",
        )
        store.delete_incomplete("del-1")
        assert not (tmp_path / "_incomplete_del-1.json").exists()

    def test_delete_nonexistent_incomplete_succeeds(self, tmp_path: Path):
        from dental_notes.session.store import SessionStore

        store = SessionStore(sessions_dir=tmp_path)
        # Should not raise
        store.delete_incomplete("nonexistent-id")


class TestEnrichedSoapNote:
    """SoapNote includes medications and va_narrative fields."""

    def test_medications_defaults_to_empty_list(self):
        from dental_notes.clinical.models import SoapNote

        note = SoapNote(
            subjective="s",
            objective="o",
            assessment="a",
            plan="p",
            cdt_codes=[],
            clinical_discussion=[],
        )
        assert note.medications == []

    def test_medications_accepts_list_of_strings(self):
        from dental_notes.clinical.models import SoapNote

        note = SoapNote(
            subjective="s",
            objective="o",
            assessment="a",
            plan="p",
            cdt_codes=[],
            clinical_discussion=[],
            medications=["Amoxicillin 500mg TID x7 days", "Ibuprofen 600mg PRN"],
        )
        assert len(note.medications) == 2
        assert "Amoxicillin" in note.medications[0]

    def test_va_narrative_defaults_to_none(self):
        from dental_notes.clinical.models import SoapNote

        note = SoapNote(
            subjective="s",
            objective="o",
            assessment="a",
            plan="p",
            cdt_codes=[],
            clinical_discussion=[],
        )
        assert note.va_narrative is None

    def test_va_narrative_accepts_string(self):
        from dental_notes.clinical.models import SoapNote

        note = SoapNote(
            subjective="s",
            objective="o",
            assessment="a",
            plan="p",
            cdt_codes=[],
            clinical_discussion=[],
            va_narrative="Tooth #14: Class II caries, MO surface. Indicated: composite restoration.",
        )
        assert "Tooth #14" in note.va_narrative

    def test_extraction_result_with_enriched_soap_note(self):
        from dental_notes.clinical.models import (
            ExtractionResult,
            SoapNote,
            SpeakerChunk,
        )

        result = ExtractionResult(
            soap_note=SoapNote(
                subjective="s",
                objective="o",
                assessment="a",
                plan="p",
                cdt_codes=[],
                clinical_discussion=[],
                medications=["Amoxicillin 500mg"],
                va_narrative="Tooth #14: caries",
            ),
            speaker_chunks=[
                SpeakerChunk(chunk_id=0, speaker="Doctor", text="Hello")
            ],
            clinical_summary="Visit summary.",
        )
        assert result.soap_note.medications == ["Amoxicillin 500mg"]
        assert result.soap_note.va_narrative == "Tooth #14: caries"
