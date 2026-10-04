"""Unit and integration tests for real Gemini audio-to-text transcription service."""
import io
import wave
from types import SimpleNamespace
from unittest.mock import patch, AsyncMock, MagicMock
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.meeting import Meeting
from app.services.storage import delete_stored_file
from app.services.transcription import (
    GeminiTranscriptionService,
    format_seconds,
    format_gemini_transcript,
    AUDIO_MIME_TYPES,
)


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
def uploaded_wav_meeting(client: TestClient):
    """Fixture providing a freshly uploaded meeting record with physical audio on disk."""
    wav_bytes = create_minimal_wav_bytes(100)
    response = client.post(
        "/meetings/upload",
        files={"file": ("project_sync.wav", wav_bytes, "audio/wav")},
        data={"title": "Q3 Architecture Sync"},
    )
    assert response.status_code == 201
    meeting_data = response.json()
    yield meeting_data


def make_diarized_gemini_response():
    """Create a structured mock response with diarization and word timestamps."""
    part1_words = [
        SimpleNamespace(word="Good", start_offset="2.0s"),
        SimpleNamespace(word="morning", start_offset="2.4s"),
        SimpleNamespace(word="team.", start_offset="2.8s"),
    ]
    part1_audio = SimpleNamespace(
        speaker_label="Sarah",
        words=part1_words,
    )
    part1 = SimpleNamespace(audio_transcription=part1_audio)

    part2_words = [
        SimpleNamespace(word="Hi", start_offset="6.5s"),
        SimpleNamespace(word="Sarah,", start_offset="7.0s"),
        SimpleNamespace(word="I", start_offset="7.4s"),
        SimpleNamespace(word="finished", start_offset="7.8s"),
        SimpleNamespace(word="the", start_offset="8.2s"),
        SimpleNamespace(word="tests.", start_offset="8.6s"),
    ]
    part2_audio = SimpleNamespace(
        speaker_label="Atharv",
        words=part2_words,
    )
    part2 = SimpleNamespace(audio_transcription=part2_audio)

    content = SimpleNamespace(parts=[part1, part2])
    candidate = SimpleNamespace(content=content)
    response = SimpleNamespace(candidates=[candidate], text=None)
    return response


# --- 1. Unit Tests for formatting utilities ---

def test_format_seconds_utility():
    """Verify format_seconds handles various input formats and edge cases."""
    assert format_seconds(0) == "[00:00:00]"
    assert format_seconds(12) == "[00:00:12]"
    assert format_seconds("15.4s") == "[00:00:15]"
    assert format_seconds(75.9) == "[00:01:15]"
    assert format_seconds("3665s") == "[01:01:05]"
    assert format_seconds(None) == ""
    assert format_seconds("invalid") == ""


def test_format_gemini_transcript_diarization():
    """Verify format_gemini_transcript properly formats speaker labels and timestamps."""
    response = make_diarized_gemini_response()
    formatted = format_gemini_transcript(response)

    expected = (
        "[00:00:02] Sarah: Good morning team.\n"
        "[00:00:06] Atharv: Hi Sarah, I finished the tests."
    )
    assert formatted == expected


def test_format_gemini_transcript_plain_text_fallback():
    """Verify format_gemini_transcript falls back to response.text when no diarization parts exist."""
    response = SimpleNamespace(candidates=[], text="Recognized speech without diarization metadata.")
    formatted = format_gemini_transcript(response)
    assert formatted == "Recognized speech without diarization metadata."


def test_format_gemini_transcript_empty_response():
    """Verify format_gemini_transcript returns empty string for empty or None response."""
    assert format_gemini_transcript(None) == ""
    assert format_gemini_transcript(SimpleNamespace(candidates=[], text="")) == ""
    assert format_gemini_transcript(SimpleNamespace(candidates=None, text=None)) == ""


# --- 2. Integration Tests via Meeting Transcribe Endpoint ---

def test_gemini_transcription_success(client: TestClient, db_session: Session, uploaded_wav_meeting):
    """
    Test successful transcription using Gemini provider.
    Verifies that real recognized speech is saved, is_mock is False,
    transcription_provider is 'gemini', and no synthetic mock banner is present.
    """
    meeting_id = uploaded_wav_meeting["id"]
    mock_resp = make_diarized_gemini_response()

    with patch.object(settings, "TRANSCRIPTION_PROVIDER", "gemini"), \
         patch.object(settings, "GEMINI_API_KEY", "test-gemini-key-xyz"), \
         patch.object(settings, "GEMINI_TRANSCRIPTION_MODEL", "gemini-3.5-transcribe"), \
         patch("google.genai.Client") as mock_client_cls:

        mock_client = MagicMock()
        mock_file = SimpleNamespace(name="files/sample-audio-token-123")
        mock_client.aio.files.upload = AsyncMock(return_value=mock_file)
        mock_client.aio.files.delete = AsyncMock(return_value=None)
        mock_client.aio.models.generate_content = AsyncMock(return_value=mock_resp)
        mock_client_cls.return_value = mock_client

        response = client.post(f"/meetings/{meeting_id}/transcribe")
        assert response.status_code == 200
        data = response.json()

        assert data["meeting_id"] == meeting_id
        assert data["status"] == "transcribed"
        assert data["transcription_provider"] == "gemini"
        assert data["is_mock"] is False
        assert "[SYNTHETIC SAMPLE TRANSCRIPT" not in data["transcript"]
        assert "[00:00:02] Sarah: Good morning team." in data["transcript"]
        assert "[00:00:06] Atharv: Hi Sarah, I finished the tests." in data["transcript"]

        # Verify DB record
        meeting = db_session.query(Meeting).filter(Meeting.id == meeting_id).first()
        assert meeting.status == "transcribed"
        assert meeting.transcription_provider == "gemini"
        assert meeting.is_mock is False
        assert "[00:00:02] Sarah:" in meeting.transcript

        # Verify file upload and deletion were called
        mock_client.aio.files.upload.assert_awaited_once()
        mock_client.aio.files.delete.assert_awaited_once_with(name="files/sample-audio-token-123")

        # Cleanup disk
        if meeting.audio_file_path:
            delete_stored_file(meeting.audio_file_path)


def test_gemini_transcription_missing_api_key_fails_fast(client: TestClient, db_session: Session, uploaded_wav_meeting):
    """
    Test that if TRANSCRIPTION_PROVIDER='gemini' and GEMINI_API_KEY is missing,
    the API returns HTTP 500 without silently falling back to mock.
    Meeting transitions to 'transcription_failed'.
    """
    meeting_id = uploaded_wav_meeting["id"]

    with patch.object(settings, "TRANSCRIPTION_PROVIDER", "gemini"), \
         patch.object(settings, "GEMINI_API_KEY", ""):

        response = client.post(f"/meetings/{meeting_id}/transcribe")
        assert response.status_code == 500
        assert "Gemini API key is not configured" in response.json()["detail"]

        # Ensure no silent mock fallback occurred
        meeting = db_session.query(Meeting).filter(Meeting.id == meeting_id).first()
        assert meeting.status == "transcription_failed"
        assert meeting.transcript is None

        if meeting.audio_file_path:
            delete_stored_file(meeting.audio_file_path)


def test_gemini_transcription_api_error_returns_502(client: TestClient, db_session: Session, uploaded_wav_meeting):
    """
    Test that an upstream Google GenAI API error returns HTTP 502 Bad Gateway
    and safely marks meeting as 'transcription_failed'.
    """
    meeting_id = uploaded_wav_meeting["id"]

    with patch.object(settings, "TRANSCRIPTION_PROVIDER", "gemini"), \
         patch.object(settings, "GEMINI_API_KEY", "test-gemini-key"), \
         patch("google.genai.Client") as mock_client_cls:

        mock_client = MagicMock()
        mock_file = SimpleNamespace(name="files/audio-token-err")
        mock_client.aio.files.upload = AsyncMock(return_value=mock_file)
        mock_client.aio.files.delete = AsyncMock(return_value=None)
        mock_client.aio.models.generate_content = AsyncMock(
            side_effect=RuntimeError("Google GenAI 503 Backend Service Unavailable")
        )
        mock_client_cls.return_value = mock_client

        response = client.post(f"/meetings/{meeting_id}/transcribe")
        assert response.status_code == 502
        assert "Gemini transcription API request failed" in response.json()["detail"]

        # Verify state transitioned to transcription_failed
        meeting = db_session.query(Meeting).filter(Meeting.id == meeting_id).first()
        assert meeting.status == "transcription_failed"

        # Verify file cleanup occurred even on generate_content failure
        mock_client.aio.files.delete.assert_awaited_once_with(name="files/audio-token-err")

        if meeting.audio_file_path:
            delete_stored_file(meeting.audio_file_path)


def test_gemini_transcription_empty_response_returns_502(client: TestClient, db_session: Session, uploaded_wav_meeting):
    """
    Test that an empty or unparseable response from Gemini returns HTTP 502 Bad Gateway.
    """
    meeting_id = uploaded_wav_meeting["id"]
    empty_resp = SimpleNamespace(candidates=[], text="")

    with patch.object(settings, "TRANSCRIPTION_PROVIDER", "gemini"), \
         patch.object(settings, "GEMINI_API_KEY", "test-gemini-key"), \
         patch("google.genai.Client") as mock_client_cls:

        mock_client = MagicMock()
        mock_file = SimpleNamespace(name="files/audio-empty")
        mock_client.aio.files.upload = AsyncMock(return_value=mock_file)
        mock_client.aio.files.delete = AsyncMock(return_value=None)
        mock_client.aio.models.generate_content = AsyncMock(return_value=empty_resp)
        mock_client_cls.return_value = mock_client

        response = client.post(f"/meetings/{meeting_id}/transcribe")
        assert response.status_code == 502
        assert "empty or unparseable" in response.json()["detail"]

        meeting = db_session.query(Meeting).filter(Meeting.id == meeting_id).first()
        assert meeting.status == "transcription_failed"

        if meeting.audio_file_path:
            delete_stored_file(meeting.audio_file_path)


def test_gemini_transcription_preserves_previous_transcript_on_failure(client: TestClient, db_session: Session, uploaded_wav_meeting):
    """
    Test that if a previously transcribed meeting is re-transcribed and fails,
    its existing transcript is preserved and not overwritten with None or empty text.
    """
    meeting_id = uploaded_wav_meeting["id"]
    previous_content = "[00:00:01] Sarah: Existing valid transcript text from earlier session."

    # Pre-populate meeting with existing transcript
    meeting = db_session.query(Meeting).filter(Meeting.id == meeting_id).first()
    meeting.status = "transcribed"
    meeting.transcript = previous_content
    db_session.commit()

    with patch.object(settings, "TRANSCRIPTION_PROVIDER", "gemini"), \
         patch.object(settings, "GEMINI_API_KEY", "test-key"), \
         patch("google.genai.Client") as mock_client_cls:

        mock_client = MagicMock()
        mock_client.aio.files.upload = AsyncMock(side_effect=RuntimeError("Network timeout during upload"))
        mock_client_cls.return_value = mock_client

        response = client.post(f"/meetings/{meeting_id}/transcribe")
        assert response.status_code == 502

        # Verify state is transcription_failed and previous transcript is restored
        meeting = db_session.query(Meeting).filter(Meeting.id == meeting_id).first()
        assert meeting.status == "transcription_failed"
        assert meeting.transcript == previous_content

        if meeting.audio_file_path:
            delete_stored_file(meeting.audio_file_path)


def test_gemini_transcription_audio_mime_mapping(tmp_path):
    """Verify AUDIO_MIME_TYPES mapping covers expected audio extensions."""
    assert AUDIO_MIME_TYPES[".wav"] == "audio/wav"
    assert AUDIO_MIME_TYPES[".mp3"] == "audio/mp3"
    assert AUDIO_MIME_TYPES[".m4a"] == "audio/m4a"
    assert AUDIO_MIME_TYPES[".aac"] == "audio/aac"
    assert AUDIO_MIME_TYPES[".ogg"] == "audio/ogg"
    assert AUDIO_MIME_TYPES[".flac"] == "audio/flac"


def test_gemini_transcription_fallback_to_part_bytes_when_upload_bypassed(client: TestClient, db_session: Session, uploaded_wav_meeting):
    """
    Test that if client.aio.files.upload fails or is bypassed,
    the service safely falls back to reading file bytes directly via types.Part.from_bytes.
    """
    meeting_id = uploaded_wav_meeting["id"]
    mock_resp = SimpleNamespace(candidates=[], text="Speech transcribed via inline part.")

    with patch.object(settings, "TRANSCRIPTION_PROVIDER", "gemini"), \
         patch.object(settings, "GEMINI_API_KEY", "test-gemini-key"), \
         patch("google.genai.Client") as mock_client_cls:

        mock_client = MagicMock()
        # Upload fails, triggering fallback
        mock_client.aio.files.upload = AsyncMock(side_effect=Exception("Files API not available"))
        mock_client.aio.models.generate_content = AsyncMock(return_value=mock_resp)
        mock_client_cls.return_value = mock_client

        response = client.post(f"/meetings/{meeting_id}/transcribe")
        assert response.status_code == 200
        data = response.json()
        assert data["transcript"] == "Speech transcribed via inline part."
        assert data["is_mock"] is False
        assert data["transcription_provider"] == "gemini"

        meeting = db_session.query(Meeting).filter(Meeting.id == meeting_id).first()
        if meeting.audio_file_path:
            delete_stored_file(meeting.audio_file_path)


def test_new_meeting_starts_with_no_transcript(client: TestClient, db_session: Session):
    """
    Requirement 1: Newly uploaded meeting must have NO transcript and is_mock=False
    before transcription is explicitly executed.
    """
    wav_bytes = create_minimal_wav_bytes(100)
    response = client.post(
        "/meetings/upload",
        files={"file": ("fresh_recording.wav", wav_bytes, "audio/wav")},
        data={"title": "Fresh Meeting Without Transcript"},
    )
    assert response.status_code == 201
    meeting_data = response.json()
    meeting_id = meeting_data["id"]

    # Verify detail response has no transcript and no mock provider
    detail_res = client.get(f"/meetings/{meeting_id}")
    assert detail_res.status_code == 200
    detail = detail_res.json()

    assert detail["status"] == "uploaded"
    assert detail["transcript"] is None
    assert detail["summary"] is None
    assert detail["transcription_provider"] is None
    assert detail["extraction_provider"] is None
    assert detail["is_mock"] is False

    meeting = db_session.query(Meeting).filter(Meeting.id == meeting_id).first()
    if meeting and meeting.audio_file_path:
        delete_stored_file(meeting.audio_file_path)


def test_gemini_receives_actual_uploaded_audio_path_and_model(client: TestClient, db_session: Session, uploaded_wav_meeting):
    """
    Requirements 2 & 3: Gemini provider is selected and receives the actual stored audio file path
    and configured GEMINI_TRANSCRIPTION_MODEL.
    """
    meeting_id = uploaded_wav_meeting["id"]
    mock_resp = make_diarized_gemini_response()

    with patch.object(settings, "TRANSCRIPTION_PROVIDER", "gemini"), \
         patch.object(settings, "GEMINI_API_KEY", "test-gemini-key"), \
         patch.object(settings, "GEMINI_TRANSCRIPTION_MODEL", "gemini-3.5-transcribe"), \
         patch("google.genai.Client") as mock_client_cls:

        mock_client = MagicMock()
        mock_file = SimpleNamespace(name="files/sample-audio-1")
        mock_client.aio.files.upload = AsyncMock(return_value=mock_file)
        mock_client.aio.files.delete = AsyncMock(return_value=None)
        mock_client.aio.models.generate_content = AsyncMock(return_value=mock_resp)
        mock_client_cls.return_value = mock_client

        response = client.post(f"/meetings/{meeting_id}/transcribe")
        assert response.status_code == 200

        # Verify upload received the real file path on disk
        meeting = db_session.query(Meeting).filter(Meeting.id == meeting_id).first()
        mock_client.aio.files.upload.assert_awaited_once()
        call_kwargs = mock_client.aio.files.upload.call_args.kwargs
        assert call_kwargs["file"] == meeting.audio_file_path

        # Verify model used was gemini-3.5-transcribe
        gen_kwargs = mock_client.aio.models.generate_content.call_args.kwargs
        assert gen_kwargs["model"] == "gemini-3.5-transcribe"

        if meeting.audio_file_path:
            delete_stored_file(meeting.audio_file_path)


def test_gemma_receives_real_saved_transcript_and_failure_creates_no_sample_actions(client: TestClient, db_session: Session):
    """
    Requirements 8 & 9: Gemma receives the real saved transcript, and API failure
    never substitutes demo/sample actions.
    """
    real_transcript = "[00:00:01] Alex: We decided to deploy the staging server on Wednesday."
    meeting = Meeting(
        title="Real Pipeline Meeting",
        status="transcribed",
        transcript=real_transcript,
        transcription_provider="gemini",
        is_mock=False,
    )
    db_session.add(meeting)
    db_session.commit()
    db_session.refresh(meeting)

    with patch.object(settings, "EXTRACTION_PROVIDER", "gemma"), \
         patch.object(settings, "GEMINI_API_KEY", "test-key"), \
         patch.object(settings, "GEMMA_MODEL", "gemma-4-26b-a4b-it"), \
         patch("google.genai.Client") as mock_client_cls:

        mock_client = MagicMock()
        # Simulate Gemma API failure
        mock_client.aio.models.generate_content = AsyncMock(
            side_effect=RuntimeError("Google GenAI 503 Service Unavailable")
        )
        mock_client_cls.return_value = mock_client

        response = client.post(f"/meetings/{meeting.id}/analyze")
        assert response.status_code == 502
        assert "Gemma API request failed" in response.json()["detail"]

        # Verify no sample actions or synthetic decisions were created in database
        db_meeting = db_session.query(Meeting).filter(Meeting.id == meeting.id).first()
        assert db_meeting.status == "transcribed"
        assert len(db_meeting.actions) == 0
        assert db_meeting.summary is None

