"""Unit and integration tests for Gemma workflow extraction via Google Gemini API."""
import json
from unittest.mock import patch, AsyncMock, MagicMock
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.meeting import Meeting
from app.models.action import Action
from app.services.extraction import GemmaExtractionService, validate_evidence_in_transcript
from app.schemas.workflow import WorkflowExtractionContract, DecisionItem, OpenQuestionItem, ExtractedActionItem


SAMPLE_TRANSCRIPT = (
    "[00:00:05] Maria: Welcome team. We decided to launch the customer pilot on October 15th.\n"
    "[00:00:20] Kevin: Got it. I will configure the staging database by Friday.\n"
    "[00:00:35] Sarah: Please send an email update to stakeholders@example.com by tomorrow.\n"
    "[00:00:50] Maria: Did we finalize whether the security review is required before launch?\n"
    "[00:01:05] Kevin: That remains an open question."
)


def make_mock_gemma_response(data: dict):
    """Create a mock GenerateContentResponse with the given dict as JSON text."""
    mock_resp = MagicMock()
    mock_resp.text = json.dumps(data)
    return mock_resp


@pytest.fixture
def gemma_meeting(db_session: Session) -> Meeting:
    """Fixture providing a transcribed meeting for Gemma extraction tests."""
    meeting = Meeting(
        title="Gemma Pilot Planning",
        status="transcribed",
        transcript=SAMPLE_TRANSCRIPT,
    )
    db_session.add(meeting)
    db_session.commit()
    db_session.refresh(meeting)
    return meeting


def test_gemma_extraction_success(client: TestClient, gemma_meeting: Meeting, db_session: Session):
    """
    Test successful structured Gemma workflow extraction.
    Verifies that summary, decisions, actions, and open questions are correctly parsed,
    grounded, saved to SQLite, and marked with extraction_provider='gemma' and is_mock=False.
    """
    gemma_payload = {
        "summary": "The team agreed on the pilot launch date and assigned staging database setup and email updates.",
        "decisions": [
            {
                "description": "Launch the customer pilot on October 15th.",
                "evidence": "[00:00:05] Maria: Welcome team. We decided to launch the customer pilot on October 15th.",
            }
        ],
        "actions": [
            {
                "type": "task",
                "description": "Configure the staging database.",
                "owner": "Kevin",
                "deadline_text": "by Friday",
                "recipient_email": None,
                "draft_subject": None,
                "draft_body": None,
                "evidence": "[00:00:20] Kevin: Got it. I will configure the staging database by Friday.",
                "confidence": "high",
                "needs_clarification": False,
                "approval_status": "pending",
            },
            {
                "type": "email",
                "description": "Send email update to stakeholders.",
                "owner": "Sarah",
                "deadline_text": "by tomorrow",
                "recipient_email": "stakeholders@example.com",
                "draft_subject": "Pilot Launch Update",
                "draft_body": "Hi Stakeholders, the pilot is scheduled for Oct 15.",
                "evidence": "[00:00:35] Sarah: Please send an email update to stakeholders@example.com by tomorrow.",
                "confidence": "high",
                "needs_clarification": False,
                "approval_status": "pending",
            },
        ],
        "open_questions": [
            {
                "question": "Whether security review is required before launch?",
                "evidence": "[00:00:50] Maria: Did we finalize whether the security review is required before launch?",
            }
        ],
    }

    mock_resp = make_mock_gemma_response(gemma_payload)

    with patch.object(settings, "EXTRACTION_PROVIDER", "gemma"), \
         patch.object(settings, "GEMINI_API_KEY", "mock-test-key-12345"), \
         patch.object(settings, "GEMMA_MODEL", "gemma-4-26b-a4b-it"), \
         patch("google.genai.Client") as mock_client_cls:

        mock_client = MagicMock()
        mock_client.aio.models.generate_content = AsyncMock(return_value=mock_resp)
        mock_client_cls.return_value = mock_client

        response = client.post(f"/meetings/{gemma_meeting.id}/analyze")
        assert response.status_code == 200
        data = response.json()

        assert data["meeting_id"] == gemma_meeting.id
        assert data["status"] == "analyzed"
        assert data["extraction_provider"] == "gemma"
        assert data["is_mock"] is False
        assert "pilot launch" in data["summary"].lower()

        # Verify decisions
        assert len(data["decisions"]) == 1
        assert "october 15th" in data["decisions"][0]["description"].lower()

        # Verify actions
        assert len(data["actions"]) == 2
        for action in data["actions"]:
            assert action["approval_status"] == "pending"
            assert action["evidence"] != ""

        # Verify database state
        db_meeting = db_session.query(Meeting).filter(Meeting.id == gemma_meeting.id).first()
        assert db_meeting.extraction_provider == "gemma"
        assert db_meeting.is_mock is False
        assert len(db_meeting.actions) == 2


def test_gemma_missing_api_key_fails_fast(client: TestClient, gemma_meeting: Meeting, db_session: Session):
    """
    Test that if EXTRACTION_PROVIDER='gemma' and GEMINI_API_KEY is empty,
    the API returns HTTP 500 without silently falling back to mock.
    Meeting status is safely preserved as 'transcribed'.
    """
    with patch.object(settings, "EXTRACTION_PROVIDER", "gemma"), \
         patch.object(settings, "GEMINI_API_KEY", ""):

        response = client.post(f"/meetings/{gemma_meeting.id}/analyze")
        assert response.status_code == 500
        assert "Gemini API key is not configured" in response.json()["detail"]

        # Ensure no silent mock fallback occurred
        db_meeting = db_session.query(Meeting).filter(Meeting.id == gemma_meeting.id).first()
        assert db_meeting.status == "transcribed"
        assert len(db_meeting.actions) == 0


def test_gemma_api_request_failure_returns_502(client: TestClient, gemma_meeting: Meeting, db_session: Session):
    """
    Test that if the Google GenAI API request raises an exception (e.g. network/auth error),
    the server returns HTTP 502 with a descriptive error and restores previous status.
    """
    with patch.object(settings, "EXTRACTION_PROVIDER", "gemma"), \
         patch.object(settings, "GEMINI_API_KEY", "mock-test-key"), \
         patch("google.genai.Client") as mock_client_cls:

        mock_client = MagicMock()
        mock_client.aio.models.generate_content = AsyncMock(
            side_effect=RuntimeError("Google GenAI 503: Model overloaded")
        )
        mock_client_cls.return_value = mock_client

        response = client.post(f"/meetings/{gemma_meeting.id}/analyze")
        assert response.status_code == 502
        assert "Gemma API request failed" in response.json()["detail"]

        # Verify meeting status was safely restored
        db_meeting = db_session.query(Meeting).filter(Meeting.id == gemma_meeting.id).first()
        assert db_meeting.status == "transcribed"


def test_gemma_invalid_or_malformed_json_returns_502(client: TestClient, gemma_meeting: Meeting, db_session: Session):
    """
    Test that if the model returns non-JSON or malformed schema output,
    the server returns HTTP 502 and restores previous meeting status.
    """
    mock_resp = MagicMock()
    mock_resp.text = "Sorry, I cannot parse this meeting transcript into JSON format."

    with patch.object(settings, "EXTRACTION_PROVIDER", "gemma"), \
         patch.object(settings, "GEMINI_API_KEY", "mock-test-key"), \
         patch("google.genai.Client") as mock_client_cls:

        mock_client = MagicMock()
        mock_client.aio.models.generate_content = AsyncMock(return_value=mock_resp)
        mock_client_cls.return_value = mock_client

        response = client.post(f"/meetings/{gemma_meeting.id}/analyze")
        assert response.status_code == 502
        assert "invalid or malformed structured output" in response.json()["detail"].lower()

        # Status restored
        db_meeting = db_session.query(Meeting).filter(Meeting.id == gemma_meeting.id).first()
        assert db_meeting.status == "transcribed"


def test_gemma_missing_required_info_enforces_clarification(client: TestClient, gemma_meeting: Meeting):
    """
    Test that if Gemma returns an action missing required information (e.g. unassigned owner or missing email),
    MeetFlow's post-validation rules strictly enforce needs_clarification=True.
    """
    gemma_payload = {
        "summary": "Meeting discussion.",
        "decisions": [],
        "actions": [
            {
                "type": "task",
                "description": "Configure staging database.",
                "owner": None,  # Missing owner
                "deadline_text": None,
                "evidence": "[00:00:20] Kevin: Got it. I will configure the staging database by Friday.",
                "confidence": "medium",
                "needs_clarification": False,  # Model mistakenly said False
                "approval_status": "pending",
            },
            {
                "type": "email",
                "description": "Send email update.",
                "owner": "Sarah",
                "recipient_email": None,  # Missing email
                "evidence": "[00:00:35] Sarah: Please send an email update to stakeholders@example.com by tomorrow.",
                "confidence": "medium",
                "needs_clarification": False,  # Model mistakenly said False
                "approval_status": "pending",
            },
        ],
        "open_questions": [],
    }

    mock_resp = make_mock_gemma_response(gemma_payload)

    with patch.object(settings, "EXTRACTION_PROVIDER", "gemma"), \
         patch.object(settings, "GEMINI_API_KEY", "mock-test-key"), \
         patch("google.genai.Client") as mock_client_cls:

        mock_client = MagicMock()
        mock_client.aio.models.generate_content = AsyncMock(return_value=mock_resp)
        mock_client_cls.return_value = mock_client

        response = client.post(f"/meetings/{gemma_meeting.id}/analyze")
        assert response.status_code == 200
        actions = response.json()["actions"]

        # Task without owner must be marked needs_clarification=True
        assert actions[0]["needs_clarification"] is True

        # Email without recipient_email must be marked needs_clarification=True
        assert actions[1]["needs_clarification"] is True


def test_gemma_evidence_grounding_mismatch_fails_safely(client: TestClient, gemma_meeting: Meeting, db_session: Session):
    """
    Test that if Gemma outputs an evidence excerpt not verbatim in the transcript,
    the grounding check catches it, returns HTTP 502, and safely restores status.
    """
    hallucinated_payload = {
        "summary": "Meeting summary.",
        "decisions": [
            {
                "description": "A totally made up decision not in transcript.",
                "evidence": "Fake Speaker: We all decided to deploy to Kubernetes immediately.",
            }
        ],
        "actions": [],
        "open_questions": [],
    }

    mock_resp = make_mock_gemma_response(hallucinated_payload)

    with patch.object(settings, "EXTRACTION_PROVIDER", "gemma"), \
         patch.object(settings, "GEMINI_API_KEY", "mock-test-key"), \
         patch("google.genai.Client") as mock_client_cls:

        mock_client = MagicMock()
        mock_client.aio.models.generate_content = AsyncMock(return_value=mock_resp)
        mock_client_cls.return_value = mock_client

        response = client.post(f"/meetings/{gemma_meeting.id}/analyze")
        assert response.status_code == 502
        assert "grounding check failed" in response.json()["detail"].lower()

        db_meeting = db_session.query(Meeting).filter(Meeting.id == gemma_meeting.id).first()
        assert db_meeting.status == "transcribed"


def test_gemma_safe_reanalysis_preserves_previous_workflow_on_failure(
    client: TestClient,
    gemma_meeting: Meeting,
    db_session: Session,
):
    """
    Test that if a previously analyzed meeting is re-analyzed with Gemma and the API fails,
    the previous workflow and actions remain intact and the status reverts to 'analyzed'.
    """
    initial_payload = {
        "summary": "Initial successful summary.",
        "decisions": [
            {
                "description": "Launch customer pilot.",
                "evidence": "[00:00:05] Maria: Welcome team. We decided to launch the customer pilot on October 15th.",
            }
        ],
        "actions": [
            {
                "type": "task",
                "description": "Configure staging database.",
                "owner": "Kevin",
                "deadline_text": "by Friday",
                "evidence": "[00:00:20] Kevin: Got it. I will configure the staging database by Friday.",
                "confidence": "high",
                "needs_clarification": False,
                "approval_status": "pending",
            }
        ],
        "open_questions": [],
    }

    mock_resp = make_mock_gemma_response(initial_payload)

    with patch.object(settings, "EXTRACTION_PROVIDER", "gemma"), \
         patch.object(settings, "GEMINI_API_KEY", "mock-test-key"), \
         patch("google.genai.Client") as mock_client_cls:

        mock_client = MagicMock()
        mock_client.aio.models.generate_content = AsyncMock(return_value=mock_resp)
        mock_client_cls.return_value = mock_client

        # 1. First analysis succeeds
        res1 = client.post(f"/meetings/{gemma_meeting.id}/analyze")
        assert res1.status_code == 200
        initial_actions = res1.json()["actions"]
        assert len(initial_actions) == 1
        initial_action_id = initial_actions[0]["id"]

        # 2. Second analysis fails
        mock_client.aio.models.generate_content = AsyncMock(
            side_effect=RuntimeError("Google GenAI RateLimitError: quota exceeded")
        )

        res2 = client.post(f"/meetings/{gemma_meeting.id}/analyze")
        assert res2.status_code == 502

        # 3. Status reverts to 'analyzed' and previous action is still present
        db_meeting = db_session.query(Meeting).filter(Meeting.id == gemma_meeting.id).first()
        assert db_meeting.status == "analyzed"
        assert len(db_meeting.actions) == 1
        assert db_meeting.actions[0].id == initial_action_id


def test_reanalysis_preserves_approved_and_executed_actions(
    client: TestClient,
    gemma_meeting: Meeting,
    db_session: Session,
):
    """
    Test that re-analysis never overwrites or deletes actions that have already been
    approved or executed (succeeded/failed).
    """
    initial_payload = {
        "summary": "Initial summary.",
        "decisions": [
            {
                "description": "Pilot launch agreed.",
                "evidence": "[00:00:05] Maria: Welcome team. We decided to launch the customer pilot on October 15th.",
            }
        ],
        "actions": [
            {
                "type": "task",
                "description": "Configure staging database.",
                "owner": "Kevin",
                "deadline_text": "by Friday",
                "evidence": "[00:00:20] Kevin: Got it. I will configure the staging database by Friday.",
                "confidence": "high",
                "needs_clarification": False,
                "approval_status": "pending",
            },
            {
                "type": "email",
                "description": "Send stakeholder email.",
                "owner": "Sarah",
                "recipient_email": "stakeholders@example.com",
                "evidence": "[00:00:35] Sarah: Please send an email update to stakeholders@example.com by tomorrow.",
                "confidence": "high",
                "needs_clarification": False,
                "approval_status": "pending",
            },
        ],
        "open_questions": [],
    }

    mock_resp1 = make_mock_gemma_response(initial_payload)

    with patch.object(settings, "EXTRACTION_PROVIDER", "gemma"), \
         patch.object(settings, "GEMINI_API_KEY", "mock-test-key"), \
         patch("google.genai.Client") as mock_client_cls:

        mock_client = MagicMock()
        mock_client.aio.models.generate_content = AsyncMock(return_value=mock_resp1)
        mock_client_cls.return_value = mock_client

        # 1. Analyze meeting
        res = client.post(f"/meetings/{gemma_meeting.id}/analyze")
        assert res.status_code == 200
        actions = res.json()["actions"]
        assert len(actions) == 2

        action_1_id = actions[0]["id"]
        action_2_id = actions[1]["id"]

        # 2. Approve action 1 and execute action 2
        app_res = client.post(f"/actions/{action_1_id}/approve")
        assert app_res.status_code == 200
        assert app_res.json()["approval_status"] == "approved"

        app_res2 = client.post(f"/actions/{action_2_id}/approve")
        assert app_res2.status_code == 200
        exec_res = client.post(f"/actions/{action_2_id}/execute")
        assert exec_res.status_code == 200
        assert exec_res.json()["approval_status"] == "succeeded"

        # 3. Re-analyze meeting with a new extraction payload
        new_payload = {
            "summary": "Updated summary from re-analysis.",
            "decisions": [
                {
                    "description": "Pilot launch agreed.",
                    "evidence": "[00:00:05] Maria: Welcome team. We decided to launch the customer pilot on October 15th.",
                }
            ],
            "actions": [
                {
                    "type": "task",
                    "description": "New extracted action item.",
                    "owner": "Kevin",
                    "deadline_text": "by Friday",
                    "evidence": "[00:00:20] Kevin: Got it. I will configure the staging database by Friday.",
                    "confidence": "high",
                    "needs_clarification": False,
                    "approval_status": "pending",
                }
            ],
            "open_questions": [],
        }

        mock_client.aio.models.generate_content = AsyncMock(
            return_value=make_mock_gemma_response(new_payload)
        )

        reanalyze_res = client.post(f"/meetings/{gemma_meeting.id}/analyze")
        assert reanalyze_res.status_code == 200

        # Verify that approved action_1 and executed action_2 were NOT deleted or overwritten
        current_actions = db_session.query(Action).filter(Action.meeting_id == gemma_meeting.id).all()
        current_action_map = {a.id: a for a in current_actions}

        assert action_1_id in current_action_map
        assert current_action_map[action_1_id].approval_status == "approved"

        assert action_2_id in current_action_map
        assert current_action_map[action_2_id].approval_status == "succeeded"
        assert current_action_map[action_2_id].execution_result is not None


def test_gemma_service_empty_transcript():
    """Unit test for GemmaExtractionService handling empty transcript gracefully."""
    import asyncio
    service = GemmaExtractionService(api_key="mock-key", model_name="gemma-4-26b-a4b-it")
    contract, is_mock = asyncio.run(service.extract_workflow(""))
    assert is_mock is False
    assert contract.summary == "Empty meeting transcript with no actionable content."
    assert len(contract.actions) == 0
