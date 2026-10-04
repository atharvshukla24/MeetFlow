"""Tests for transcript viewing, editing, validation, and banner preservation."""
import io
import wave
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

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
def transcribed_meeting(client: TestClient):
    """Fixture providing an uploaded and transcribed meeting."""
    wav_bytes = create_minimal_wav_bytes(100)
    upload_res = client.post(
        "/meetings/upload",
        files={"file": ("transcript_test.wav", wav_bytes, "audio/wav")},
        data={"title": "Transcript Test Meeting"},
    )
    assert upload_res.status_code == 201
    meeting_id = upload_res.json()["id"]

    transcribe_res = client.post(f"/meetings/{meeting_id}/transcribe")
    assert transcribe_res.status_code == 200

    yield upload_res.json()


def test_get_transcript_success(client: TestClient, transcribed_meeting, db_session: Session):
    """Verify GET /meetings/{id}/transcript returns transcript and metadata."""
    meeting_id = transcribed_meeting["id"]

    response = client.get(f"/meetings/{meeting_id}/transcript")
    assert response.status_code == 200
    data = response.json()

    assert data["meeting_id"] == meeting_id
    assert data["status"] == "transcribed"
    assert data["is_mock"] is True
    assert data["transcription_provider"] == "mock"
    assert "[SYNTHETIC SAMPLE TRANSCRIPT — DEMO ONLY]" in data["transcript"]
    assert "Sarah:" in data["transcript"]
    assert "Atharv:" in data["transcript"]
    assert data["audio_filename"] == "transcript_test.wav"

    meeting = db_session.query(Meeting).filter(Meeting.id == meeting_id).first()
    if meeting and meeting.audio_file_path:
        delete_stored_file(meeting.audio_file_path)


def test_get_transcript_works_via_api_v1_prefix(client: TestClient, transcribed_meeting, db_session: Session):
    """Verify GET works via /api/v1/meetings/{id}/transcript alias."""
    meeting_id = transcribed_meeting["id"]

    response = client.get(f"/api/v1/meetings/{meeting_id}/transcript")
    assert response.status_code == 200
    data = response.json()
    assert data["meeting_id"] == meeting_id
    assert data["is_mock"] is True

    meeting = db_session.query(Meeting).filter(Meeting.id == meeting_id).first()
    if meeting and meeting.audio_file_path:
        delete_stored_file(meeting.audio_file_path)


def test_get_transcript_not_found(client: TestClient):
    """Verify HTTP 404 when meeting ID does not exist."""
    response = client.get("/meetings/00000000-0000-0000-0000-000000000000/transcript")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_get_transcript_not_ready_uploaded(client: TestClient, db_session: Session):
    """Verify HTTP 400 when meeting is in 'uploaded' state and transcript is not yet generated."""
    meeting = Meeting(
        title="Untranscribed Meeting",
        status="uploaded",
        transcript=None,
    )
    db_session.add(meeting)
    db_session.commit()
    db_session.refresh(meeting)

    response = client.get(f"/meetings/{meeting.id}/transcript")
    assert response.status_code == 400
    assert "Transcript is not ready" in response.json()["detail"]


def test_get_transcript_in_progress_transcribing(client: TestClient, db_session: Session):
    """Verify HTTP 409 Conflict when meeting is currently transcribing."""
    meeting = Meeting(
        title="In-Flight Meeting",
        status="transcribing",
        transcript=None,
    )
    db_session.add(meeting)
    db_session.commit()
    db_session.refresh(meeting)

    response = client.get(f"/meetings/{meeting.id}/transcript")
    assert response.status_code == 409
    assert "currently in progress" in response.json()["detail"]


def test_patch_transcript_success_preserves_banner(client: TestClient, transcribed_meeting, db_session: Session):
    """
    Verify PATCH /meetings/{id}/transcript updates transcript text
    and automatically preserves/prepends the synthetic banner if user omitted it.
    """
    meeting_id = transcribed_meeting["id"]
    edited_text = "[00:00:02] Sarah: Good morning team, updated action items.\n[00:00:15] Atharv: I will finalize the API by Thursday."

    response = client.patch(
        f"/meetings/{meeting_id}/transcript",
        json={"transcript": edited_text},
    )
    assert response.status_code == 200
    data = response.json()

    # Verify synthetic banner is automatically prepended
    assert data["transcript"].startswith("[SYNTHETIC SAMPLE TRANSCRIPT — DEMO ONLY]")
    assert edited_text in data["transcript"]
    assert data["is_mock"] is True
    assert data["transcription_provider"] == "mock"

    # Verify database persistence
    meeting = db_session.query(Meeting).filter(Meeting.id == meeting_id).first()
    assert meeting is not None
    assert meeting.transcript == data["transcript"]

    if meeting.audio_file_path:
        delete_stored_file(meeting.audio_file_path)


def test_patch_transcript_works_via_api_v1_prefix(client: TestClient, transcribed_meeting, db_session: Session):
    """Verify PATCH works via /api/v1/meetings/{id}/transcript."""
    meeting_id = transcribed_meeting["id"]
    new_text = "[00:00:02] Sarah: Tested via prefix."

    response = client.patch(
        f"/api/v1/meetings/{meeting_id}/transcript",
        json={"transcript": new_text},
    )
    assert response.status_code == 200
    data = response.json()
    assert new_text in data["transcript"]

    meeting = db_session.query(Meeting).filter(Meeting.id == meeting_id).first()
    if meeting and meeting.audio_file_path:
        delete_stored_file(meeting.audio_file_path)


def test_patch_transcript_preserves_existing_banner_without_duplication(client: TestClient, transcribed_meeting, db_session: Session):
    """Verify that if the user explicitly submits the synthetic banner, it is not duplicated."""
    meeting_id = transcribed_meeting["id"]
    explicit_text = "[SYNTHETIC SAMPLE TRANSCRIPT — DEMO ONLY]\n[00:00:02] Sarah: Standup started."

    response = client.patch(
        f"/meetings/{meeting_id}/transcript",
        json={"transcript": explicit_text},
    )
    assert response.status_code == 200
    data = response.json()

    # Count occurrences of the banner - must be exactly 1
    assert data["transcript"].count("[SYNTHETIC SAMPLE TRANSCRIPT — DEMO ONLY]") == 1
    assert data["transcript"] == explicit_text

    meeting = db_session.query(Meeting).filter(Meeting.id == meeting_id).first()
    if meeting and meeting.audio_file_path:
        delete_stored_file(meeting.audio_file_path)


def test_patch_transcript_forbids_client_metadata_spoofing(client: TestClient, transcribed_meeting, db_session: Session):
    """
    Clarification 1: is_mock and transcription_provider are server-controlled.
    Extra fields in request body must be rejected with 422 Unprocessable Entity.
    """
    meeting_id = transcribed_meeting["id"]

    response = client.patch(
        f"/meetings/{meeting_id}/transcript",
        json={"transcript": "Valid text", "is_mock": False},
    )
    assert response.status_code == 422

    meeting = db_session.query(Meeting).filter(Meeting.id == meeting_id).first()
    if meeting and meeting.audio_file_path:
        delete_stored_file(meeting.audio_file_path)


def test_patch_transcript_empty_or_whitespace_rejected(client: TestClient, transcribed_meeting, db_session: Session):
    """Verify that empty string or whitespace-only transcript is rejected with 422."""
    meeting_id = transcribed_meeting["id"]

    # Empty string
    res1 = client.patch(f"/meetings/{meeting_id}/transcript", json={"transcript": ""})
    assert res1.status_code == 422

    # Whitespace only
    res2 = client.patch(f"/meetings/{meeting_id}/transcript", json={"transcript": "   \n\t  "})
    assert res2.status_code == 422

    meeting = db_session.query(Meeting).filter(Meeting.id == meeting_id).first()
    if meeting and meeting.audio_file_path:
        delete_stored_file(meeting.audio_file_path)


def test_patch_transcript_not_found(client: TestClient):
    """Verify HTTP 404 when meeting does not exist."""
    response = client.patch(
        "/meetings/00000000-0000-0000-0000-000000000000/transcript",
        json={"transcript": "Valid transcript"},
    )
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_patch_transcript_not_transcribed_uploaded(client: TestClient, db_session: Session):
    """Verify HTTP 400 when attempting to edit a meeting that has not been transcribed."""
    meeting = Meeting(
        title="Untranscribed Meeting",
        status="uploaded",
        transcript=None,
    )
    db_session.add(meeting)
    db_session.commit()
    db_session.refresh(meeting)

    response = client.patch(
        f"/meetings/{meeting.id}/transcript",
        json={"transcript": "Premature edit"},
    )
    assert response.status_code == 400
    assert "not in 'transcribed' status" in response.json()["detail"]


def test_patch_transcript_transcribing_conflict(client: TestClient, db_session: Session):
    """Verify HTTP 409 Conflict when attempting to edit while transcription is in progress."""
    meeting = Meeting(
        title="In-Flight Meeting",
        status="transcribing",
        transcript=None,
    )
    db_session.add(meeting)
    db_session.commit()
    db_session.refresh(meeting)

    response = client.patch(
        f"/meetings/{meeting.id}/transcript",
        json={"transcript": "Race condition edit"},
    )
    assert response.status_code == 409
    assert "Cannot edit transcript while transcription is in progress" in response.json()["detail"]
