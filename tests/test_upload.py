"""Tests for meeting audio upload, validation, security, and storage."""
import io
import wave
from pathlib import Path
from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import settings
from app.models.meeting import Meeting
from app.services.storage import delete_stored_file


def create_minimal_wav_bytes(duration_frames: int = 100) -> bytes:
    """Generate a syntactically valid minimal PCM WAV file in memory."""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(16000)
        wf.writeframes(b"\x00\x00" * duration_frames)
    return buf.getvalue()


def test_upload_valid_wav_success(client: TestClient, db_session: Session):
    """Verify that uploading a valid WAV file returns 201 Created and persists the meeting."""
    wav_bytes = create_minimal_wav_bytes(200)
    response = client.post(
        "/meetings/upload",
        files={"file": ("standup_recording.wav", wav_bytes, "audio/wav")},
        data={"title": "Sprint 42 Standup"},
    )

    assert response.status_code == 201
    data = response.json()

    assert data["title"] == "Sprint 42 Standup"
    assert data["status"] == "uploaded"
    assert data["audio_filename"] == "standup_recording.wav"
    assert "id" in data
    # Ensure internal filesystem path is NEVER exposed in API response
    assert "audio_file_path" not in data

    # Verify database persistence
    meeting = db_session.query(Meeting).filter(Meeting.id == data["id"]).first()
    assert meeting is not None
    assert meeting.title == "Sprint 42 Standup"
    assert meeting.status == "uploaded"
    assert meeting.audio_file_path is not None
    assert Path(meeting.audio_file_path).exists()

    # Clean up created file
    delete_stored_file(meeting.audio_file_path)


def test_upload_works_via_api_v1_prefix(client: TestClient):
    """Verify upload is accessible via /api/v1/meetings/upload alias as well."""
    wav_bytes = create_minimal_wav_bytes(50)
    response = client.post(
        "/api/v1/meetings/upload",
        files={"file": ("prefix_test.wav", wav_bytes, "audio/wav")},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["status"] == "uploaded"


def test_upload_unusual_mime_type_accepted(client: TestClient, db_session: Session):
    """
    Clarification 1: Do not reject a valid audio file solely because client-provided MIME is unusual.
    Valid WAV bytes sent with 'application/octet-stream' must be accepted.
    """
    wav_bytes = create_minimal_wav_bytes(100)
    response = client.post(
        "/meetings/upload",
        files={"file": ("audio_sample.wav", wav_bytes, "application/octet-stream")},
        data={"title": "MIME Tolerance Test"},
    )

    assert response.status_code == 201
    data = response.json()
    assert data["status"] == "uploaded"

    meeting = db_session.query(Meeting).filter(Meeting.id == data["id"]).first()
    if meeting and meeting.audio_file_path:
        delete_stored_file(meeting.audio_file_path)


def test_upload_fake_audio_rejected(client: TestClient):
    """
    Technical Requirement 3: Do not treat arbitrary text renamed as .wav as valid audio.
    Must be rejected with 400 Bad Request.
    """
    fake_audio_bytes = b"Hello, I am a plain text file renamed to malicious.wav"
    response = client.post(
        "/meetings/upload",
        files={"file": ("fake_meeting.wav", fake_audio_bytes, "audio/wav")},
    )

    assert response.status_code == 400
    assert "Invalid audio file format" in response.json()["detail"]


def test_upload_invalid_extension_rejected(client: TestClient):
    """Ensure non-audio extensions are rejected."""
    content = b"Some random binary payload"
    response = client.post(
        "/meetings/upload",
        files={"file": ("payload.exe", content, "application/octet-stream")},
    )

    assert response.status_code == 400
    assert "Unsupported file extension" in response.json()["detail"]


def test_upload_empty_file_rejected(client: TestClient):
    """Ensure 0-byte files are rejected."""
    response = client.post(
        "/meetings/upload",
        files={"file": ("empty.wav", b"", "audio/wav")},
    )

    assert response.status_code == 400
    assert "empty" in response.json()["detail"].lower()


def test_upload_oversized_file_rejected(client: TestClient):
    """
    Technical Requirement 5: Enforce upload size limit during streaming read.
    Temporarily setting a small max upload limit to test streaming abort and cleanup.
    """
    wav_bytes = create_minimal_wav_bytes(1000)  # ~2 KB
    small_limit = 500  # 500 bytes

    with patch.object(settings, "MAX_UPLOAD_SIZE_BYTES", small_limit):
        response = client.post(
            "/meetings/upload",
            files={"file": ("oversized.wav", wav_bytes, "audio/wav")},
        )

        assert response.status_code == 413
        assert "exceeds maximum allowed upload size" in response.json()["detail"]


def test_upload_path_traversal_sanitized(client: TestClient, db_session: Session):
    """
    Technical Requirement 6: Never use client filename directly as storage path.
    Prevent path traversal attempts.
    """
    wav_bytes = create_minimal_wav_bytes(50)
    malicious_filename = "../../../etc/passwd_exploit.wav"

    response = client.post(
        "/meetings/upload",
        files={"file": (malicious_filename, wav_bytes, "audio/wav")},
    )

    assert response.status_code == 201
    data = response.json()

    # The returned display name should have any traversal path stripped
    assert ".." not in data["audio_filename"]
    assert "/" not in data["audio_filename"]
    assert "\\" not in data["audio_filename"]

    # Verify the stored file is strictly inside upload directory
    meeting = db_session.query(Meeting).filter(Meeting.id == data["id"]).first()
    assert meeting is not None
    saved_path = Path(meeting.audio_file_path).resolve()
    upload_dir = Path(settings.UPLOAD_DIR).resolve()
    assert saved_path.is_relative_to(upload_dir)

    delete_stored_file(meeting.audio_file_path)


def test_upload_database_failure_cleans_up_file(client: TestClient):
    """
    Clarification 2: If database transaction fails, transaction is rolled back
    and any stored audio file on disk is deleted.
    """
    wav_bytes = create_minimal_wav_bytes(50)

    # Mock Session.commit to raise an exception simulating DB failure
    with patch("sqlalchemy.orm.Session.commit", side_effect=SQLAlchemyError("DB write failed")):
        response = client.post(
            "/meetings/upload",
            files={"file": ("failure_cleanup_test.wav", wav_bytes, "audio/wav")},
        )

        assert response.status_code == 500
        assert "Database transaction failed" in response.json()["detail"]

    # Confirm that no leftover failure_cleanup_test file remains in the upload directory
    upload_dir = Path(settings.UPLOAD_DIR).resolve()
    matching_files = list(upload_dir.glob("*failure_cleanup_test.wav"))
    assert len(matching_files) == 0
