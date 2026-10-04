"""Tests for Action Approval, Rejection, Editing, and Mock Execution."""
import uuid
from datetime import datetime, timezone
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.meeting import Meeting
from app.models.action import Action
from app.main import recover_stuck_actions


@pytest.fixture
def sample_meeting(db_session: Session) -> Meeting:
    """Create a sample meeting in the test database."""
    meeting = Meeting(
        id=str(uuid.uuid4()),
        title="Weekly Team Sync",
        status="analyzed",
        transcript="[00:00:05] Alice: I will update the backend tests by Friday.",
        summary="Sync meeting discussing test suite improvements.",
    )
    db_session.add(meeting)
    db_session.commit()
    db_session.refresh(meeting)
    return meeting


@pytest.fixture
def sample_action(db_session: Session, sample_meeting: Meeting) -> Action:
    """Create a sample pending task action."""
    action = Action(
        id=str(uuid.uuid4()),
        meeting_id=sample_meeting.id,
        type="task",
        description="Update the backend tests by Friday",
        owner="Alice",
        deadline_text="by Friday",
        evidence="[00:00:05] Alice: I will update the backend tests by Friday.",
        confidence="high",
        needs_clarification=False,
        approval_status="pending",
    )
    db_session.add(action)
    db_session.commit()
    db_session.refresh(action)
    return action


@pytest.fixture
def clarification_action(db_session: Session, sample_meeting: Meeting) -> Action:
    """Create an action that requires clarification (missing owner)."""
    action = Action(
        id=str(uuid.uuid4()),
        meeting_id=sample_meeting.id,
        type="task",
        description="Coordinate staging deployment",
        owner=None,
        deadline_text="by Monday",
        evidence="Someone please coordinate staging deployment.",
        confidence="low",
        needs_clarification=True,
        approval_status="pending",
    )
    db_session.add(action)
    db_session.commit()
    db_session.refresh(action)
    return action


# ============================================================================
# 1. ATOMIC APPROVAL TESTS
# ============================================================================

def test_approve_pending_action_success(client: TestClient, sample_action: Action):
    """Pending action transitions cleanly to approved."""
    response = client.post(f"/actions/{sample_action.id}/approve")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == sample_action.id
    assert data["approval_status"] == "approved"


def test_approve_rejected_action_success(client: TestClient, db_session: Session, sample_action: Action):
    """Previously rejected action can be re-approved."""
    sample_action.approval_status = "rejected"
    db_session.commit()

    response = client.post(f"/actions/{sample_action.id}/approve")
    assert response.status_code == 200
    assert response.json()["approval_status"] == "approved"


def test_approve_failed_action_preserves_previous_result(client: TestClient, db_session: Session, sample_action: Action):
    """Approving a failed action for retry transitions to approved and preserves failure diagnostic."""
    sample_action.approval_status = "failed"
    sample_action.execution_result = {
        "status": "failed",
        "error": "Simulated connection error",
        "failed_at": datetime.now(timezone.utc).isoformat(),
    }
    db_session.commit()

    response = client.post(f"/actions/{sample_action.id}/approve")
    assert response.status_code == 200
    data = response.json()
    assert data["approval_status"] == "approved"
    # Prior diagnostic is preserved during approval
    assert data["execution_result"] is not None
    assert data["execution_result"]["error"] == "Simulated connection error"


def test_approve_already_approved_is_idempotent(client: TestClient, db_session: Session, sample_action: Action):
    """Calling approve on an already approved action is idempotent and returns 200."""
    sample_action.approval_status = "approved"
    db_session.commit()

    response = client.post(f"/actions/{sample_action.id}/approve")
    assert response.status_code == 200
    assert response.json()["approval_status"] == "approved"


def test_approve_needs_clarification_rejected_400(client: TestClient, clarification_action: Action):
    """An action needing clarification cannot be approved without resolving clarification."""
    response = client.post(f"/actions/{clarification_action.id}/approve")
    assert response.status_code == 400
    assert "requires clarification" in response.json()["detail"].lower()


def test_approve_succeeded_action_fails_400(client: TestClient, db_session: Session, sample_action: Action):
    """Cannot re-approve an action that already executed and succeeded."""
    sample_action.approval_status = "succeeded"
    sample_action.execution_result = {"status": "success"}
    db_session.commit()

    response = client.post(f"/actions/{sample_action.id}/approve")
    assert response.status_code == 400
    assert "already executed successfully" in response.json()["detail"].lower()


def test_approve_executing_action_fails_409(client: TestClient, db_session: Session, sample_action: Action):
    """Cannot approve an action that is currently executing (concurrency conflict)."""
    sample_action.approval_status = "executing"
    db_session.commit()

    response = client.post(f"/actions/{sample_action.id}/approve")
    assert response.status_code == 409
    assert "currently executing" in response.json()["detail"].lower()


def test_approve_nonexistent_action_404(client: TestClient):
    """Approving an unknown action returns 404."""
    response = client.post(f"/actions/{uuid.uuid4()}/approve")
    assert response.status_code == 404


# ============================================================================
# 2. ATOMIC REJECTION TESTS
# ============================================================================

def test_reject_pending_action_success(client: TestClient, sample_action: Action):
    """Pending action transitions cleanly to rejected."""
    response = client.post(f"/actions/{sample_action.id}/reject")
    assert response.status_code == 200
    assert response.json()["approval_status"] == "rejected"


def test_reject_approved_action_success(client: TestClient, db_session: Session, sample_action: Action):
    """Approved action can be rejected before execution starts (revoking approval)."""
    sample_action.approval_status = "approved"
    db_session.commit()

    response = client.post(f"/actions/{sample_action.id}/reject")
    assert response.status_code == 200
    assert response.json()["approval_status"] == "rejected"


def test_reject_failed_action_success(client: TestClient, db_session: Session, sample_action: Action):
    """Failed action can be rejected to dismiss retry."""
    sample_action.approval_status = "failed"
    db_session.commit()

    response = client.post(f"/actions/{sample_action.id}/reject")
    assert response.status_code == 200
    assert response.json()["approval_status"] == "rejected"


def test_reject_needs_clarification_action_success(client: TestClient, clarification_action: Action):
    """User can reject/discard an action needing clarification rather than fixing it."""
    response = client.post(f"/actions/{clarification_action.id}/reject")
    assert response.status_code == 200
    assert response.json()["approval_status"] == "rejected"


def test_reject_already_rejected_is_idempotent(client: TestClient, db_session: Session, sample_action: Action):
    """Calling reject on an already rejected action is idempotent and returns 200."""
    sample_action.approval_status = "rejected"
    db_session.commit()

    response = client.post(f"/actions/{sample_action.id}/reject")
    assert response.status_code == 200
    assert response.json()["approval_status"] == "rejected"


def test_reject_succeeded_action_fails_400(client: TestClient, db_session: Session, sample_action: Action):
    """Cannot reject an action that already completed successfully."""
    sample_action.approval_status = "succeeded"
    db_session.commit()

    response = client.post(f"/actions/{sample_action.id}/reject")
    assert response.status_code == 400
    assert "already executed successfully" in response.json()["detail"].lower()


def test_reject_executing_action_fails_409(client: TestClient, db_session: Session, sample_action: Action):
    """Cannot reject an action that is currently executing."""
    sample_action.approval_status = "executing"
    db_session.commit()

    response = client.post(f"/actions/{sample_action.id}/reject")
    assert response.status_code == 409
    assert "currently executing" in response.json()["detail"].lower()


def test_reject_nonexistent_action_404(client: TestClient):
    """Rejecting an unknown action returns 404."""
    response = client.post(f"/actions/{uuid.uuid4()}/reject")
    assert response.status_code == 404


# ============================================================================
# 3. PATCH EDITING & CLARIFICATION VALIDATION
# ============================================================================

def test_patch_clear_clarification_without_required_fields_fails_400(client: TestClient, clarification_action: Action):
    """
    Attempting to clear clarification without providing required owner for a task
    must be rejected with 400 Bad Request.
    """
    response = client.patch(
        f"/actions/{clarification_action.id}",
        json={"needs_clarification": False},
    )
    assert response.status_code == 400
    assert "'owner' is required" in response.json()["detail"]


def test_patch_clear_clarification_with_valid_fields_success(client: TestClient, clarification_action: Action):
    """Providing owner and clearing needs_clarification transitions status to 'edited' and enables approval."""
    patch_res = client.patch(
        f"/actions/{clarification_action.id}",
        json={
            "owner": "Dave",
            "needs_clarification": False,
        },
    )
    assert patch_res.status_code == 200
    data = patch_res.json()
    assert data["owner"] == "Dave"
    assert data["needs_clarification"] is False
    assert data["approval_status"] == "edited"

    # Now approval should succeed
    approve_res = client.post(f"/actions/{clarification_action.id}/approve")
    assert approve_res.status_code == 200
    assert approve_res.json()["approval_status"] == "approved"


def test_patch_clear_clarification_email_requires_valid_email(client: TestClient, db_session: Session, sample_meeting: Meeting):
    """Email action requires a valid recipient_email when clearing clarification."""
    email_action = Action(
        id=str(uuid.uuid4()),
        meeting_id=sample_meeting.id,
        type="email",
        description="Send update to team",
        owner="Alice",
        recipient_email=None,
        draft_subject="Weekly Notes",
        needs_clarification=True,
        approval_status="pending",
    )
    db_session.add(email_action)
    db_session.commit()

    # Attempt with invalid email string
    res = client.patch(f"/actions/{email_action.id}", json={"needs_clarification": False, "recipient_email": "invalid"})
    assert res.status_code == 400
    assert "valid 'recipient_email' is required" in res.json()["detail"]

    # Provide valid email
    res_ok = client.patch(f"/actions/{email_action.id}", json={"needs_clarification": False, "recipient_email": "team@example.com"})
    assert res_ok.status_code == 200
    assert res_ok.json()["needs_clarification"] is False


def test_patch_clear_clarification_reminder_requires_deadline(client: TestClient, db_session: Session, sample_meeting: Meeting):
    """Reminder action requires deadline_text when clearing clarification."""
    reminder = Action(
        id=str(uuid.uuid4()),
        meeting_id=sample_meeting.id,
        type="reminder",
        description="Check database backup status",
        deadline_text=None,
        needs_clarification=True,
        approval_status="pending",
    )
    db_session.add(reminder)
    db_session.commit()

    res = client.patch(f"/actions/{reminder.id}", json={"needs_clarification": False})
    assert res.status_code == 400
    assert "'deadline_text' is required" in res.json()["detail"]


def test_patch_approved_action_revokes_approval_to_edited(client: TestClient, db_session: Session, sample_action: Action):
    """Editing an approved action revokes approval and sets status to 'edited'."""
    sample_action.approval_status = "approved"
    db_session.commit()

    response = client.patch(
        f"/actions/{sample_action.id}",
        json={"description": "Updated backend test requirements"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["approval_status"] == "edited"
    assert data["description"] == "Updated backend test requirements"


def test_patch_executing_action_fails_409(client: TestClient, db_session: Session, sample_action: Action):
    """Cannot edit an action that is currently executing."""
    sample_action.approval_status = "executing"
    db_session.commit()

    response = client.patch(f"/actions/{sample_action.id}", json={"description": "New description"})
    assert response.status_code == 409
    assert "currently executing" in response.json()["detail"].lower()


def test_patch_succeeded_action_fails_400(client: TestClient, db_session: Session, sample_action: Action):
    """Cannot edit an action that has already succeeded."""
    sample_action.approval_status = "succeeded"
    db_session.commit()

    response = client.patch(f"/actions/{sample_action.id}", json={"description": "New description"})
    assert response.status_code == 400
    assert "already succeeded" in response.json()["detail"].lower()


def test_patch_nonexistent_action_404(client: TestClient):
    """Editing an unknown action returns 404."""
    response = client.patch(f"/actions/{uuid.uuid4()}", json={"description": "Test"})
    assert response.status_code == 404


# ============================================================================
# 4. EXECUTION PRECONDITIONS & ERROR HANDLING
# ============================================================================

def test_execute_pending_action_fails_400(client: TestClient, sample_action: Action):
    """Executing a pending (unapproved) action must fail with 400 Bad Request."""
    response = client.post(f"/actions/{sample_action.id}/execute")
    assert response.status_code == 400
    assert "must be approved before execution" in response.json()["detail"].lower()


def test_execute_rejected_action_fails_400(client: TestClient, db_session: Session, sample_action: Action):
    """Executing a rejected action must fail with 400 Bad Request."""
    sample_action.approval_status = "rejected"
    db_session.commit()

    response = client.post(f"/actions/{sample_action.id}/execute")
    assert response.status_code == 400
    assert "cannot execute a rejected action" in response.json()["detail"].lower()


def test_execute_needs_clarification_action_fails_400(client: TestClient, clarification_action: Action):
    """Executing an action requiring clarification must fail with 400 Bad Request."""
    response = client.post(f"/actions/{clarification_action.id}/execute")
    assert response.status_code == 400
    assert "requires clarification" in response.json()["detail"].lower()


def test_execute_failed_action_fails_400(client: TestClient, db_session: Session, sample_action: Action):
    """Directly executing a failed action without re-approving must fail with 400."""
    sample_action.approval_status = "failed"
    db_session.commit()

    response = client.post(f"/actions/{sample_action.id}/execute")
    assert response.status_code == 400
    assert "must be approved before retrying" in response.json()["detail"].lower()


def test_execute_nonexistent_action_404(client: TestClient):
    """Executing an unknown action returns 404."""
    response = client.post(f"/actions/{uuid.uuid4()}/execute")
    assert response.status_code == 404


# ============================================================================
# 5. SUCCESSFUL MOCK EXECUTION TESTS
# ============================================================================

def test_execute_approved_task_action_success(client: TestClient, db_session: Session, sample_action: Action):
    """Executing an approved task action produces structured mock execution payload."""
    sample_action.approval_status = "approved"
    db_session.commit()

    response = client.post(f"/actions/{sample_action.id}/execute")
    assert response.status_code == 200
    data = response.json()

    assert data["approval_status"] == "succeeded"
    res = data["execution_result"]
    assert res is not None
    assert res["status"] == "success"
    assert res["provider"] == "mock"
    assert res["is_mock"] is True
    assert res["simulated_action"] == "create_task"
    assert "Alice" in res["message"]
    assert "task_id" in res["details"]
    assert res["details"]["assignee"] == "Alice"


def test_execute_approved_email_action_success(client: TestClient, db_session: Session, sample_meeting: Meeting):
    """Executing an approved email action produces structured simulated email payload."""
    email_action = Action(
        id=str(uuid.uuid4()),
        meeting_id=sample_meeting.id,
        type="email",
        description="Send sprint goals summary to eng team",
        owner="Alice",
        recipient_email="eng-team@example.com",
        draft_subject="Sprint Goals Finalized",
        draft_body="Hi team, here are the finalized sprint commitments from today's sync.",
        approval_status="approved",
        needs_clarification=False,
    )
    db_session.add(email_action)
    db_session.commit()

    response = client.post(f"/actions/{email_action.id}/execute")
    assert response.status_code == 200
    data = response.json()

    assert data["approval_status"] == "succeeded"
    res = data["execution_result"]
    assert res["simulated_action"] == "send_email"
    assert res["details"]["recipient"] == "eng-team@example.com"
    assert res["details"]["subject"] == "Sprint Goals Finalized"
    assert "No real email was sent" in res["message"]


def test_execute_approved_reminder_action_success(client: TestClient, db_session: Session, sample_meeting: Meeting):
    """Executing an approved reminder action produces simulated schedule details."""
    reminder = Action(
        id=str(uuid.uuid4()),
        meeting_id=sample_meeting.id,
        type="reminder",
        description="Verify staging metrics before release",
        owner="Bob",
        deadline_text="next Tuesday at 9 AM",
        approval_status="approved",
        needs_clarification=False,
    )
    db_session.add(reminder)
    db_session.commit()

    response = client.post(f"/actions/{reminder.id}/execute")
    assert response.status_code == 200
    data = response.json()

    assert data["approval_status"] == "succeeded"
    res = data["execution_result"]
    assert res["simulated_action"] == "schedule_reminder"
    assert res["details"]["scheduled_time"] == "next Tuesday at 9 AM"


# ============================================================================
# 6. DUPLICATE EXECUTION PREVENTION
# ============================================================================

def test_repeated_execution_returns_409_conflict(client: TestClient, db_session: Session, sample_action: Action):
    """
    Subsequent execution attempt on a succeeded action returns 409 Conflict.
    Preserves original execution_result untouched.
    """
    sample_action.approval_status = "approved"
    db_session.commit()

    first_res = client.post(f"/actions/{sample_action.id}/execute")
    assert first_res.status_code == 200
    initial_executed_at = first_res.json()["execution_result"]["executed_at"]

    second_res = client.post(f"/actions/{sample_action.id}/execute")
    assert second_res.status_code == 409
    assert "duplicate execution is prevented" in second_res.json()["detail"].lower()

    # Verify original execution_result is untouched
    get_res = client.get(f"/actions/{sample_action.id}")
    assert get_res.json()["approval_status"] == "succeeded"
    assert get_res.json()["execution_result"]["executed_at"] == initial_executed_at


# ============================================================================
# 7. RETRY WITH HISTORY PRESERVATION
# ============================================================================

def test_retry_execution_preserves_previous_failure(client: TestClient, db_session: Session, sample_action: Action):
    """
    Retrying an action that failed archives prior failure diagnostic into previous_result.
    """
    # 1. Action failed previously
    sample_action.approval_status = "failed"
    sample_action.execution_result = {
        "status": "failed",
        "error": "Simulated initial timeout",
        "failed_at": "2026-10-04T12:00:00Z",
    }
    db_session.commit()

    # 2. User approves retry
    approve_res = client.post(f"/actions/{sample_action.id}/approve")
    assert approve_res.status_code == 200
    assert approve_res.json()["approval_status"] == "approved"

    # 3. User executes retried action
    exec_res = client.post(f"/actions/{sample_action.id}/execute")
    assert exec_res.status_code == 200
    data = exec_res.json()

    assert data["approval_status"] == "succeeded"
    res = data["execution_result"]
    assert res["status"] == "success"
    assert res["retry_count"] == 1
    assert res["previous_result"] is not None
    assert res["previous_result"]["error"] == "Simulated initial timeout"


# ============================================================================
# 8. STARTUP RECOVERY SWEEP (SINGLE-WORKER)
# ============================================================================

def test_startup_recovery_sweep_marks_stuck_actions_failed(db_session: Session, sample_meeting: Meeting):
    """
    Actions abandoned in 'executing' state are marked 'failed' by the startup sweep
    with uncertain outcome diagnostics.
    """
    # Clear any residual executing actions from previous concurrency tests
    recover_stuck_actions(target_session=db_session)

    stuck_action = Action(
        id=str(uuid.uuid4()),
        meeting_id=sample_meeting.id,
        type="task",
        description="Database indexing migration",
        approval_status="executing",
        needs_clarification=False,
    )
    db_session.add(stuck_action)
    db_session.commit()

    recovered = recover_stuck_actions(target_session=db_session)
    assert recovered == 1

    db_session.refresh(stuck_action)
    assert stuck_action.approval_status == "failed"
    assert stuck_action.execution_result is not None
    assert "outcome is uncertain" in stuck_action.execution_result["error"].lower()


def test_startup_recovery_sweep_is_idempotent(db_session: Session):
    """Running recovery sweep when no actions are executing affects 0 rows."""
    count = recover_stuck_actions(target_session=db_session)
    assert count == 0


# ============================================================================
# 9. GET DETAILS & ROUTE PREFIX CONSISTENCY
# ============================================================================

def test_get_action_success_and_404(client: TestClient, sample_action: Action):
    """GET /actions/{id} returns details; 404 for unknown."""
    ok_res = client.get(f"/actions/{sample_action.id}")
    assert ok_res.status_code == 200
    assert ok_res.json()["id"] == sample_action.id

    not_found = client.get(f"/actions/{uuid.uuid4()}")
    assert not_found.status_code == 404


def test_actions_accessible_via_both_prefixes(client: TestClient, sample_action: Action):
    """Both unversioned and /api/v1 prefixes work seamlessly at runtime."""
    res_root = client.get(f"/actions/{sample_action.id}")
    assert res_root.status_code == 200

    res_v1 = client.get(f"/api/v1/actions/{sample_action.id}")
    assert res_v1.status_code == 200
    assert res_v1.json()["id"] == res_root.json()["id"]


def test_openapi_schema_has_no_duplicate_routes(client: TestClient):
    """
    Inspects /openapi.json to ensure Swagger displays each route only once under /api/v1/...
    and that unversioned root mounts are hidden from the OpenAPI schema.
    """
    response = client.get("/openapi.json")
    assert response.status_code == 200
    schema = response.json()
    paths = schema.get("paths", {})

    # Endpoints must appear under /api/v1/
    assert "/api/v1/meetings/upload" in paths
    assert "/api/v1/actions/{action_id}/approve" in paths
    assert "/api/v1/actions/{action_id}/execute" in paths

    # Endpoints must NOT be duplicated without /api/v1/ prefix in OpenAPI schema
    assert "/meetings/upload" not in paths
    assert "/actions/{action_id}/approve" not in paths
    assert "/actions/{action_id}/execute" not in paths
