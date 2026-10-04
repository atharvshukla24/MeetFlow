"""Tests for mock transcription service, atomic concurrency, and error handling."""
import io
import wave
from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.meeting import Meeting
from app.services.storage import delete_stored_file


def create_minimal_wav_bytes(duration_frames: int = 100) -> bytes:
    """Generate a valid minimal PCM WAV file in memory."""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(16000)
        wf.writeframes(b"\x00\x00" * duration_frames)
    return buf.getvalue()


@pytest.fixture
def uploaded_meeting(client: TestClient):
    """Fixture providing a freshly uploaded meeting record with physical audio on disk."""
    wav_bytes = create_minimal_wav_bytes(100)
    response = client.post(
        "/meetings/upload",
        files={"file": ("sync_meeting.wav", wav_bytes, "audio/wav")},
        data={"title": "Weekly Planning"},
    )
    assert response.status_code == 201
    meeting_data = response.json()
    yield meeting_data


def test_transcribe_successful(client: TestClient, db_session: Session, uploaded_meeting):
    """Verify that calling transcribe succeeds and explicitly labels mock output."""
    meeting_id = uploaded_meeting["id"]

    response = client.post(f"/meetings/{meeting_id}/transcribe")
    assert response.status_code == 200
    data = response.json()

    assert data["meeting_id"] == meeting_id
    assert data["status"] == "transcribed"
    assert data["transcription_provider"] == "mock"
    assert data["is_mock"] is True
    assert "[SYNTHETIC SAMPLE TRANSCRIPT — DEMO ONLY]" in data["transcript"]
    assert "Sarah:" in data["transcript"]
    assert "Atharv:" in data["transcript"]
    assert "[00:00:" in data["transcript"]

    # Verify database persistence
    meeting = db_session.query(Meeting).filter(Meeting.id == meeting_id).first()
    assert meeting is not None
    assert meeting.status == "transcribed"
    assert meeting.transcript == data["transcript"]

    if meeting.audio_file_path:
        delete_stored_file(meeting.audio_file_path)


def test_transcribe_works_via_api_v1_prefix(client: TestClient, db_session: Session, uploaded_meeting):
    """Verify endpoint is accessible via /api/v1/meetings/{meeting_id}/transcribe."""
    meeting_id = uploaded_meeting["id"]

    response = client.post(f"/api/v1/meetings/{meeting_id}/transcribe")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "transcribed"
    assert data["is_mock"] is True

    meeting = db_session.query(Meeting).filter(Meeting.id == meeting_id).first()
    if meeting and meeting.audio_file_path:
        delete_stored_file(meeting.audio_file_path)


def test_retranscribe_idempotent_success(client: TestClient, db_session: Session, uploaded_meeting):
    """Verify that re-transcribing an already transcribed meeting succeeds safely."""
    meeting_id = uploaded_meeting["id"]

    # First transcription
    res1 = client.post(f"/meetings/{meeting_id}/transcribe")
    assert res1.status_code == 200

    # Second transcription (re-run / refresh)
    res2 = client.post(f"/meetings/{meeting_id}/transcribe")
    assert res2.status_code == 200
    assert res2.json()["status"] == "transcribed"

    meeting = db_session.query(Meeting).filter(Meeting.id == meeting_id).first()
    if meeting and meeting.audio_file_path:
        delete_stored_file(meeting.audio_file_path)


def test_transcribe_atomic_concurrency_conflict(client: TestClient, db_session: Session, uploaded_meeting):
    """
    Verify that if a meeting is already in 'transcribing' state,
    the atomic conditional update results in rowcount 0 and returns 409 Conflict.
    """
    meeting_id = uploaded_meeting["id"]

    # Set status directly to 'transcribing'
    meeting = db_session.query(Meeting).filter(Meeting.id == meeting_id).first()
    meeting.status = "transcribing"
    db_session.commit()

    response = client.post(f"/meetings/{meeting_id}/transcribe")
    assert response.status_code == 409
    assert "already in progress" in response.json()["detail"].lower()

    if meeting and meeting.audio_file_path:
        delete_stored_file(meeting.audio_file_path)


def test_transcribe_missing_audio_record(client: TestClient, db_session: Session):
    """Verify HTTP 400 when meeting record has no audio_file_path."""
    meeting = Meeting(
        title="No Audio Meeting",
        status="uploaded",
        audio_file_path=None,
    )
    db_session.add(meeting)
    db_session.commit()
    db_session.refresh(meeting)

    response = client.post(f"/meetings/{meeting.id}/transcribe")
    assert response.status_code == 400
    assert "No audio recording" in response.json()["detail"]


def test_transcribe_physical_audio_missing_from_disk(client: TestClient, db_session: Session):
    """Verify HTTP 404 when meeting references an audio file that does not exist on disk."""
    meeting = Meeting(
        title="Deleted File Meeting",
        status="uploaded",
        audio_file_path="uploads/completely_non_existent_file.wav",
    )
    db_session.add(meeting)
    db_session.commit()
    db_session.refresh(meeting)

    response = client.post(f"/meetings/{meeting.id}/transcribe")
    assert response.status_code == 404
    assert "Audio file missing from server storage" in response.json()["detail"]


def test_transcribe_invalid_meeting_id(client: TestClient):
    """Verify HTTP 404 when meeting ID does not exist."""
    response = client.post("/meetings/00000000-0000-0000-0000-000000000000/transcribe")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_transcribe_provider_misconfiguration(client: TestClient, db_session: Session, uploaded_meeting):
    """
    Verify that an unsupported TRANSCRIPTION_PROVIDER raises 500
    and does NOT silently fall back to mock.
    """
    meeting_id = uploaded_meeting["id"]

    with patch.object(settings, "TRANSCRIPTION_PROVIDER", "unsupported_cloud_stt"):
        response = client.post(f"/meetings/{meeting_id}/transcribe")
        assert response.status_code == 500
        assert "not supported" in response.json()["detail"].lower()

    meeting = db_session.query(Meeting).filter(Meeting.id == meeting_id).first()
    if meeting and meeting.audio_file_path:
        delete_stored_file(meeting.audio_file_path)


def test_transcribe_failure_recovery_marks_transcription_failed(client: TestClient, db_session: Session, uploaded_meeting):
    """
    Verify that an unexpected transcription error transitions meeting to 'transcription_failed'
    so it is never left stuck in 'transcribing', and subsequent retry succeeds.
    """
    meeting_id = uploaded_meeting["id"]

    # Simulate runtime transcription failure
    with patch(
        "app.services.transcription.MockTranscriptionService.transcribe",
        side_effect=RuntimeError("Simulated audio decoder crash"),
    ):
        response = client.post(f"/meetings/{meeting_id}/transcribe")
        assert response.status_code == 500
        assert "Transcription failed" in response.json()["detail"]

    # Verify state was changed to transcription_failed, NOT left in transcribing
    meeting = db_session.query(Meeting).filter(Meeting.id == meeting_id).first()
    assert meeting is not None
    assert meeting.status == "transcription_failed"

    # Verify that a subsequent retry succeeds (transcription_failed is in allowed start statuses)
    retry_response = client.post(f"/meetings/{meeting_id}/transcribe")
    assert retry_response.status_code == 200
    assert retry_response.json()["status"] == "transcribed"

    meeting = db_session.query(Meeting).filter(Meeting.id == meeting_id).first()
    if meeting and meeting.audio_file_path:
        delete_stored_file(meeting.audio_file_path)
