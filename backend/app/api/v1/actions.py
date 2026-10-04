"""Action management and execution API endpoints."""
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, status, HTTPException
from sqlalchemy import update
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.models.action import Action
from app.schemas.action import ActionResponse, ActionUpdate
from app.services.execution import get_execution_service

logger = logging.getLogger("meetflow.actions")

router = APIRouter(prefix="/actions", tags=["actions"])


ALLOWED_EDIT_STATUSES = ["pending", "edited", "approved", "rejected", "failed", "needs_clarification"]
ALLOWED_APPROVE_STATUSES = ["pending", "edited", "rejected", "failed"]
ALLOWED_REJECT_STATUSES = ["pending", "edited", "approved", "failed", "needs_clarification"]


@router.get(
    "",
    response_model=List[ActionResponse],
    status_code=status.HTTP_200_OK,
    summary="List Actions",
    description="Retrieve all extracted actions ordered by creation date descending.",
)
def list_actions(
    db: Session = Depends(get_db),
):
    """Retrieve all extracted actions ordered by creation date descending."""
    return db.query(Action).order_by(Action.created_at.desc()).all()


@router.get(
    "/{action_id}",
    response_model=ActionResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Action Details",
    description="Retrieve status, metadata, and execution result for an action.",
)
def get_action(
    action_id: str,
    db: Session = Depends(get_db),
):
    """Retrieve action details by ID."""
    action = db.query(Action).filter(Action.id == action_id).first()
    if not action:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Action '{action_id}' not found.",
        )
    return action


@router.patch(
    "/{action_id}",
    response_model=ActionResponse,
    status_code=status.HTTP_200_OK,
    summary="Edit Proposed Action",
    description="Edit action fields and resolve clarification. Revokes approval if previously approved.",
)
def update_action(
    action_id: str,
    update_data: ActionUpdate,
    db: Session = Depends(get_db),
):
    """
    User edit on an action item.
    Enforces business validation if attempting to clear needs_clarification.
    Atomic conditional update prevents racing with an active execution.
    Editing an approved action resets its status to 'edited'.
    """
    action = db.query(Action).filter(Action.id == action_id).first()
    if not action:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Action '{action_id}' not found.",
        )

    if action.approval_status == "executing":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot edit an action that is currently executing.",
        )

    if action.approval_status == "succeeded":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot edit an action that has already succeeded.",
        )

    # Determine effective values to validate clarification resolution
    effective_type = update_data.type or action.type or "task"
    effective_owner = update_data.owner if update_data.owner is not None else action.owner
    effective_desc = update_data.description if update_data.description is not None else action.description
    effective_email = update_data.recipient_email if update_data.recipient_email is not None else action.recipient_email
    effective_subject = update_data.draft_subject if update_data.draft_subject is not None else action.draft_subject
    effective_deadline = update_data.deadline_text if update_data.deadline_text is not None else action.deadline_text

    target_needs_clarification = action.needs_clarification
    if update_data.needs_clarification is not None:
        if update_data.needs_clarification is False:
            # Validate required fields before allowing clarification to be cleared
            if effective_type == "task":
                if not effective_owner or not effective_owner.strip():
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Cannot clear clarification for task: 'owner' is required.",
                    )
                if not effective_desc or not effective_desc.strip():
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Cannot clear clarification for task: 'description' is required.",
                    )

            elif effective_type == "email":
                if not effective_email or not effective_email.strip() or "@" not in effective_email:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Cannot clear clarification for email: valid 'recipient_email' is required.",
                    )
                if (not effective_subject or not effective_subject.strip()) and (not effective_desc or not effective_desc.strip()):
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Cannot clear clarification for email: 'draft_subject' or 'description' is required.",
                    )

            elif effective_type in ("reminder", "calendar_event"):
                if not effective_deadline or not effective_deadline.strip():
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Cannot clear clarification for {effective_type}: 'deadline_text' is required.",
                    )

            target_needs_clarification = False
        else:
            target_needs_clarification = True

    # Determine new status: any edit transitions status to 'edited'
    # If the user explicitly requested a status in update_data, validate it, otherwise default to 'edited'
    new_status = "edited"
    if update_data.approval_status is not None:
        if update_data.approval_status in ("executing", "succeeded"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot set approval_status to '{update_data.approval_status}' via edit.",
            )
        new_status = update_data.approval_status

    # Build values dictionary for update
    update_values: Dict[str, Any] = {
        "approval_status": new_status,
        "needs_clarification": target_needs_clarification,
        "updated_at": datetime.now(timezone.utc),
    }
    if update_data.type is not None:
        update_values["type"] = update_data.type
    if update_data.description is not None:
        update_values["description"] = update_data.description
    if update_data.owner is not None:
        update_values["owner"] = update_data.owner
    if update_data.deadline_text is not None:
        update_values["deadline_text"] = update_data.deadline_text
    if update_data.recipient_email is not None:
        update_values["recipient_email"] = update_data.recipient_email
    if update_data.draft_subject is not None:
        update_values["draft_subject"] = update_data.draft_subject
    if update_data.draft_body is not None:
        update_values["draft_body"] = update_data.draft_body

    # Atomic conditional update requiring status in ALLOWED_EDIT_STATUSES
    stmt = (
        update(Action)
        .where(
            Action.id == action_id,
            Action.approval_status.in_(ALLOWED_EDIT_STATUSES),
        )
        .values(**update_values)
    )
    result = db.execute(stmt)
    db.commit()

    if result.rowcount == 0:
        db.refresh(action)
        if action.approval_status == "executing":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Cannot edit an action that is currently executing.",
            )
        if action.approval_status == "succeeded":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot edit an action that has already succeeded.",
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot edit action with status '{action.approval_status}'.",
        )

    db.refresh(action)
    return action


@router.post(
    "/{action_id}/approve",
    response_model=ActionResponse,
    status_code=status.HTTP_200_OK,
    summary="Approve Action",
    description="Approve an action for execution. Fails if clarification is required.",
)
def approve_action(
    action_id: str,
    db: Session = Depends(get_db),
):
    """
    Approve an individual action.
    Uses atomic conditional update to guarantee consistency against races.
    Blocks approval if clarification is unresolved.
    Idempotent if already approved.
    """
    stmt = (
        update(Action)
        .where(
            Action.id == action_id,
            Action.approval_status.in_(ALLOWED_APPROVE_STATUSES),
            Action.needs_clarification == False,
        )
        .values(
            approval_status="approved",
            updated_at=datetime.now(timezone.utc),
        )
    )
    result = db.execute(stmt)
    db.commit()

    if result.rowcount == 0:
        action = db.query(Action).filter(Action.id == action_id).first()
        if not action:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Action '{action_id}' not found.",
            )
        if action.approval_status == "approved":
            return action  # Idempotent 200 OK
        if action.approval_status == "executing":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Action is currently executing.",
            )
        if action.approval_status == "succeeded":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Action has already executed successfully and cannot be re-approved.",
            )
        if action.approval_status == "needs_clarification" or action.needs_clarification:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Action requires clarification before it can be approved. Please resolve clarification first via PATCH.",
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot approve action with current status '{action.approval_status}'.",
        )

    action = db.query(Action).filter(Action.id == action_id).first()
    return action


@router.post(
    "/{action_id}/reject",
    response_model=ActionResponse,
    status_code=status.HTTP_200_OK,
    summary="Reject Action",
    description="Reject an action, revoking approval or dismissing an item.",
)
def reject_action(
    action_id: str,
    db: Session = Depends(get_db),
):
    """
    Reject an individual action.
    Uses atomic conditional update.
    Idempotent if already rejected.
    """
    stmt = (
        update(Action)
        .where(
            Action.id == action_id,
            Action.approval_status.in_(ALLOWED_REJECT_STATUSES),
        )
        .values(
            approval_status="rejected",
            updated_at=datetime.now(timezone.utc),
        )
    )
    result = db.execute(stmt)
    db.commit()

    if result.rowcount == 0:
        action = db.query(Action).filter(Action.id == action_id).first()
        if not action:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Action '{action_id}' not found.",
            )
        if action.approval_status == "rejected":
            return action  # Idempotent 200 OK
        if action.approval_status == "executing":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Action is currently executing.",
            )
        if action.approval_status == "succeeded":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Action has already executed successfully and cannot be rejected.",
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot reject action with current status '{action.approval_status}'.",
        )

    action = db.query(Action).filter(Action.id == action_id).first()
    return action


@router.post(
    "/{action_id}/execute",
    response_model=ActionResponse,
    status_code=status.HTTP_200_OK,
    summary="Execute Approved Action",
    description="Execute an individual approved action using mock execution engine.",
)
async def execute_action(
    action_id: str,
    db: Session = Depends(get_db),
):
    """
    Execute an individual action.
    Requires action to be in 'approved' status.
    Uses atomic conditional update to claim execution lock and prevent duplicate execution.
    Executes purely mock simulation; records failure diagnostics safely on error.
    """
    # Atomic conditional update claiming the execution lock
    stmt = (
        update(Action)
        .where(
            Action.id == action_id,
            Action.approval_status == "approved",
            Action.needs_clarification == False,
        )
        .values(
            approval_status="executing",
            updated_at=datetime.now(timezone.utc),
        )
    )
    result = db.execute(stmt)
    db.commit()

    if result.rowcount == 0:
        action = db.query(Action).filter(Action.id == action_id).first()
        if not action:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Action '{action_id}' not found.",
            )
        if action.approval_status == "executing":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Action execution is already in progress.",
            )
        if action.approval_status == "succeeded":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Action has already been executed successfully. Duplicate execution is prevented.",
            )
        if action.approval_status == "needs_clarification" or action.needs_clarification:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot execute an action that requires clarification.",
            )
        if action.approval_status in ("pending", "edited"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Action must be approved before execution. Current status: '{action.approval_status}'.",
            )
        if action.approval_status == "rejected":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot execute a rejected action.",
            )
        if action.approval_status == "failed":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Action previously failed execution. It must be approved before retrying.",
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot execute action with status '{action.approval_status}'.",
        )

    # Action lock claimed. Run mock execution in-memory.
    action = db.query(Action).filter(Action.id == action_id).first()
    service = get_execution_service()

    try:
        execution_payload, is_mock = await service.execute_action(action)
        action.approval_status = "succeeded"
        action.execution_result = execution_payload
        action.updated_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(action)
        logger.info(f"Action {action_id} executed successfully (mock).")
    except Exception as exc:
        logger.exception(f"Unexpected error during mock execution for action {action_id}: {exc}")
        action.approval_status = "failed"
        action.execution_result = {
            "status": "failed",
            "provider": service.provider_name,
            "is_mock": True,
            "error": str(exc),
            "failed_at": datetime.now(timezone.utc).isoformat(),
        }
        action.updated_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(action)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Action execution failed during simulated processing.",
        )

    return action
