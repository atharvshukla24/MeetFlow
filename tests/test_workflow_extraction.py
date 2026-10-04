"""Tests for workflow extraction, decisions, actions, truthfulness, safe re-analysis, and concurrency."""
import io
import wave
from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.meeting import Meeting
from app.models.action import Action
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
    """Fixture providing a transcribed meeting with default synthetic dialogue."""
    wav_bytes = create_minimal_wav_bytes(100)
    upload_res = client.post(
        "/meetings/upload",
        files={"file": ("workflow_test.wav", wav_bytes, "audio/wav")},
        data={"title": "Workflow Test Meeting"},
    )
    assert upload_res.status_code == 201
    meeting_id = upload_res.json()["id"]

    transcribe_res = client.post(f"/meetings/{meeting_id}/transcribe")
    assert transcribe_res.status_code == 200

    yield upload_res.json()


def test_successful_workflow_extraction(client: TestClient, transcribed_meeting, db_session: Session):
    """
    Verify POST /meetings/{id}/analyze successfully extracts actions, decisions,
    and open questions, marks actions as pending, and persists metadata.
    """
    meeting_id = transcribed_meeting["id"]

    response = client.post(f"/meetings/{meeting_id}/analyze")
    assert response.status_code == 200
    data = response.json()

    assert data["meeting_id"] == meeting_id
    assert data["status"] == "analyzed"
    assert data["extraction_provider"] == "mock"
    assert data["is_mock"] is True
    assert data["summary"] is not None
    assert len(data["summary"]) > 0

    # Verify decisions
    assert len(data["decisions"]) >= 1
    for dec in data["decisions"]:
        assert "evidence" in dec
        assert dec["evidence"] != ""

    # Verify actions
    assert len(data["actions"]) >= 1
    for act in data["actions"]:
        assert act["approval_status"] == "pending"
        assert act["evidence"] != ""
        assert act["type"] in ["task", "email", "message", "reminder", "calendar_event"]

    # Verify database persistence
    meeting = db_session.query(Meeting).filter(Meeting.id == meeting_id).first()
    assert meeting is not None
    assert meeting.status == "analyzed"
    assert meeting.extraction_provider == "mock"
    assert meeting.is_mock is True
    assert len(meeting.actions) == len(data["actions"])

    for act in meeting.actions:
        assert act.approval_status == "pending"

    if meeting.audio_file_path:
        delete_stored_file(meeting.audio_file_path)


def test_get_workflow_success(client: TestClient, transcribed_meeting, db_session: Session):
    """Verify GET /meetings/{id}/workflow retrieves the extracted workflow."""
    meeting_id = transcribed_meeting["id"]

    # Analyze first
    client.post(f"/meetings/{meeting_id}/analyze")

    response = client.get(f"/meetings/{meeting_id}/workflow")
    assert response.status_code == 200
    data = response.json()

    assert data["meeting_id"] == meeting_id
    assert data["status"] == "analyzed"
    assert data["extraction_provider"] == "mock"
    assert data["is_mock"] is True
    assert len(data["actions"]) >= 1

    meeting = db_session.query(Meeting).filter(Meeting.id == meeting_id).first()
    if meeting and meeting.audio_file_path:
        delete_stored_file(meeting.audio_file_path)


def test_workflow_via_api_v1_prefix(client: TestClient, transcribed_meeting, db_session: Session):
    """Verify /api/v1/meetings/{id}/analyze and /api/v1/meetings/{id}/workflow aliases."""
    meeting_id = transcribed_meeting["id"]

    post_res = client.post(f"/api/v1/meetings/{meeting_id}/analyze")
    assert post_res.status_code == 200
    assert post_res.json()["status"] == "analyzed"

    get_res = client.get(f"/api/v1/meetings/{meeting_id}/workflow")
    assert get_res.status_code == 200
    assert get_res.json()["status"] == "analyzed"

    meeting = db_session.query(Meeting).filter(Meeting.id == meeting_id).first()
    if meeting and meeting.audio_file_path:
        delete_stored_file(meeting.audio_file_path)


def test_extraction_from_different_transcript(client: TestClient, db_session: Session):
    """
    Safeguard 4 & Point 5: Mock extractor processes actual transcript passed to it,
    not static sample output. Verify items correspond strictly to custom dialogue.
    """
    custom_transcript = """[00:00:02] Dave: Good morning team. We decided to postpone the beta deployment to Tuesday.
[00:00:15] Alice: Understood. I will update the API documentation by Wednesday.
[00:00:30] Bob: Did we finalize whether to notify customer support?
[00:00:45] Dave: That remains an open question."""

    meeting = Meeting(
        title="Custom Architecture Sync",
        status="transcribed",
        transcript=custom_transcript,
    )
    db_session.add(meeting)
    db_session.commit()
    db_session.refresh(meeting)

    response = client.post(f"/meetings/{meeting.id}/analyze")
    assert response.status_code == 200
    data = response.json()

    # Verify decisions derived from custom transcript
    decisions = data["decisions"]
    assert len(decisions) == 1
    assert "postpone the beta deployment to tuesday" in decisions[0]["description"].lower()
    assert decisions[0]["evidence"] == "[00:00:02] Dave: Good morning team. We decided to postpone the beta deployment to Tuesday."

    # Verify action derived from custom transcript
    actions = data["actions"]
    assert len(actions) == 1
    assert actions[0]["owner"] == "Alice"
    assert "update the api documentation" in actions[0]["description"].lower()
    assert actions[0]["deadline_text"] == "by Wednesday"
    assert actions[0]["evidence"] == "[00:00:15] Alice: Understood. I will update the API documentation by Wednesday."

    # Verify open question
    open_questions = data["open_questions"]
    assert len(open_questions) >= 1
    assert "whether to notify customer support" in open_questions[0]["question"].lower()

    # Ensure no phantom Atharv tasks exist
    for act in actions:
        assert act["owner"] != "Atharv"


def test_mock_conservative_no_fabrication_for_ambiguous_or_quoted_questions(client: TestClient, db_session: Session):
    """
    Safeguard 4: Conversational queries, quoted speech, and unassigned requests
    must be handled conservatively without inventing owners or treating pleasantries as open questions.
    """
    conservative_transcript = """[00:00:01] Sarah: Hello everyone, could you give us an update?
[00:00:10] Alice: She asked "is the server ready?" but I said no.
[00:00:20] Bob: Someone wondered if we decided to cancel.
[00:00:30] Sarah: Someone needs to verify the backup logs."""

    meeting = Meeting(
        title="Conservative Test",
        status="transcribed",
        transcript=conservative_transcript,
    )
    db_session.add(meeting)
    db_session.commit()
    db_session.refresh(meeting)

    response = client.post(f"/meetings/{meeting.id}/analyze")
    assert response.status_code == 200
    data = response.json()

    # Conversational greeting and quoted speech must NOT be extracted as open questions
    assert len(data["open_questions"]) == 0

    # Quoted/hypothetical decision must NOT be extracted as a decision
    assert len(data["decisions"]) == 0

    # "Someone needs to verify the backup logs" should have owner None and needs_clarification True
    actions = data["actions"]
    assert len(actions) == 1
    assert actions[0]["owner"] is None
    assert actions[0]["needs_clarification"] is True
    assert "verify the backup logs" in actions[0]["description"].lower()


def test_retry_after_analysis_failed(client: TestClient, db_session: Session):
    """
    Safeguard 2 & Point 2: Meetings in 'analysis_failed' can be re-run directly via /analyze.
    """
    valid_transcript = "[00:00:02] Atharv: I will complete the backend API by Friday."
    meeting = Meeting(
        title="Failed Analysis Retry Meeting",
        status="analysis_failed",
        transcript=valid_transcript,
    )
    db_session.add(meeting)
    db_session.commit()
    db_session.refresh(meeting)

    response = client.post(f"/meetings/{meeting.id}/analyze")
    assert response.status_code == 200
    data = response.json()

    assert data["status"] == "analyzed"
    assert len(data["actions"]) == 1
    assert data["actions"][0]["owner"] == "Atharv"


def test_safe_reanalysis_preserves_previous_workflow_on_failure(client: TestClient, transcribed_meeting, db_session: Session):
    """
    Safeguards 2 & 3: If re-analysis fails, previous actions and workflow data
    must NOT be deleted, and the meeting's exact previous status ('analyzed') is restored.
    """
    meeting_id = transcribed_meeting["id"]

    # 1. First successful analysis
    initial_res = client.post(f"/meetings/{meeting_id}/analyze")
    assert initial_res.status_code == 200
    initial_actions = initial_res.json()["actions"]
    assert len(initial_actions) >= 1
    initial_action_ids = [a["id"] for a in initial_actions]

    # 2. Re-analysis with simulated extraction exception
    with patch(
        "app.services.extraction.MockExtractionService.extract_workflow",
        side_effect=RuntimeError("Simulated LLM pipeline crash"),
    ):
        fail_res = client.post(f"/meetings/{meeting_id}/analyze")
        assert fail_res.status_code == 500
        assert "Workflow extraction failed" in fail_res.json()["detail"]

    # 3. Verify in SQLite that the meeting reverted to exact previous status 'analyzed'
    meeting = db_session.query(Meeting).filter(Meeting.id == meeting_id).first()
    assert meeting is not None
    assert meeting.status == "analyzed"

    # 4. Verify all previous actions are completely preserved
    current_actions = db_session.query(Action).filter(Action.meeting_id == meeting_id).all()
    assert len(current_actions) == len(initial_actions)
    current_action_ids = [a.id for a in current_actions]
    assert set(current_action_ids) == set(initial_action_ids)

    if meeting.audio_file_path:
        delete_stored_file(meeting.audio_file_path)


def test_atomic_concurrency_conflict_on_analyze(client: TestClient, transcribed_meeting, db_session: Session):
    """
    Safeguard 5: Atomic conditional update returns 409 Conflict
    if status is already 'analyzing'.
    """
    meeting_id = transcribed_meeting["id"]

    # Set status directly to 'analyzing'
    meeting = db_session.query(Meeting).filter(Meeting.id == meeting_id).first()
    meeting.status = "analyzing"
    db_session.commit()

    response = client.post(f"/meetings/{meeting_id}/analyze")
    assert response.status_code == 409
    assert "already in progress" in response.json()["detail"].lower()

    if meeting.audio_file_path:
        delete_stored_file(meeting.audio_file_path)


def test_analyze_precondition_untranscribed(client: TestClient, db_session: Session):
    """Verify HTTP 400 when attempting to analyze a meeting in 'uploaded' status."""
    meeting = Meeting(
        title="Untranscribed Meeting",
        status="uploaded",
        transcript=None,
    )
    db_session.add(meeting)
    db_session.commit()
    db_session.refresh(meeting)

    response = client.post(f"/meetings/{meeting.id}/analyze")
    assert response.status_code == 400
    assert "must be transcribed before workflow extraction" in response.json()["detail"]


def test_analyze_precondition_empty_transcript(client: TestClient, db_session: Session):
    """Verify HTTP 400 when meeting is marked 'transcribed' but has empty transcript."""
    meeting = Meeting(
        title="Empty Transcript Meeting",
        status="transcribed",
        transcript="   \n   ",
    )
    db_session.add(meeting)
    db_session.commit()
    db_session.refresh(meeting)

    response = client.post(f"/meetings/{meeting.id}/analyze")
    assert response.status_code == 400
    assert "no transcript content" in response.json()["detail"].lower()


def test_analyze_meeting_not_found(client: TestClient):
    """Verify HTTP 404 when meeting ID does not exist."""
    response = client.post("/meetings/00000000-0000-0000-0000-000000000000/analyze")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_get_workflow_unextracted(client: TestClient, transcribed_meeting, db_session: Session):
    """Verify HTTP 400 when GET /workflow is called before analysis has run."""
    meeting_id = transcribed_meeting["id"]

    response = client.get(f"/meetings/{meeting_id}/workflow")
    assert response.status_code == 400
    assert "Workflow has not been extracted yet" in response.json()["detail"]

    meeting = db_session.query(Meeting).filter(Meeting.id == meeting_id).first()
    if meeting and meeting.audio_file_path:
        delete_stored_file(meeting.audio_file_path)


def test_get_workflow_in_progress(client: TestClient, transcribed_meeting, db_session: Session):
    """Verify HTTP 409 when GET /workflow is called while status is 'analyzing'."""
    meeting_id = transcribed_meeting["id"]

    meeting = db_session.query(Meeting).filter(Meeting.id == meeting_id).first()
    meeting.status = "analyzing"
    db_session.commit()

    response = client.get(f"/meetings/{meeting_id}/workflow")
    assert response.status_code == 409
    assert "currently in progress" in response.json()["detail"]

    if meeting.audio_file_path:
        delete_stored_file(meeting.audio_file_path)


def test_provider_misconfiguration(client: TestClient, transcribed_meeting, db_session: Session):
    """Verify HTTP 500 without silent fallback if EXTRACTION_PROVIDER is unsupported."""
    meeting_id = transcribed_meeting["id"]

    with patch.object(settings, "EXTRACTION_PROVIDER", "unsupported_gemma_beta"):
        response = client.post(f"/meetings/{meeting_id}/analyze")
        assert response.status_code == 500
        assert "not supported" in response.json()["detail"].lower()

    meeting = db_session.query(Meeting).filter(Meeting.id == meeting_id).first()
    if meeting and meeting.audio_file_path:
        delete_stored_file(meeting.audio_file_path)
