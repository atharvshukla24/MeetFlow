"""Mock execution service for action items."""
import uuid
import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, Tuple, Optional
from datetime import datetime, timezone

from app.core.config import settings
from app.models.action import Action

logger = logging.getLogger("meetflow.execution")


class BaseExecutionService(ABC):
    """Abstract base class for action execution providers."""
    provider_name: str = "base"

    @abstractmethod
    async def execute_action(self, action: Action) -> Tuple[Dict[str, Any], bool]:
        """
        Execute an action.

        Returns:
            Tuple[Dict[str, Any], bool]: (execution_result_payload, is_mock)
        """
        pass


class MockExecutionService(BaseExecutionService):
    """
    Deterministic mock execution service for local development and testing.
    Strictly mock-only: performs zero SMTP, external network requests, or real API calls.
    Generates structured, type-aware synthetic execution payloads.
    Preserves diagnostic history if retrying an action that previously failed.
    """
    provider_name: str = "mock"

    async def execute_action(self, action: Action) -> Tuple[Dict[str, Any], bool]:
        """
        Simulate execution of an action item in-memory.
        """
        logger.info(f"Simulating mock execution for action {action.id} of type '{action.type}'.")

        # Check for previous failure results to preserve history upon retry
        previous_result: Optional[Dict[str, Any]] = None
        retry_count = 0
        if action.execution_result and isinstance(action.execution_result, dict):
            previous_result = action.execution_result
            retry_count = action.execution_result.get("retry_count", 0) + 1

        action_type = (action.type or "task").lower()

        if action_type == "email":
            recipient = action.recipient_email or "unspecified@example.com"
            subject = action.draft_subject or action.description
            body_preview = (action.draft_body[:120] + "...") if action.draft_body and len(action.draft_body) > 120 else (action.draft_body or action.description)
            simulated_action = "send_email"
            message = f"Simulated email delivery to '{recipient}' completed successfully. No real email was sent."
            details = {
                "recipient": recipient,
                "subject": subject,
                "body_preview": body_preview,
                "delivery_channel": "mock_smtp_simulated",
            }

        elif action_type == "task":
            assignee = action.owner or "Unassigned"
            task_id = f"mock-task-{uuid.uuid4().hex[:8]}"
            simulated_action = "create_task"
            message = f"Simulated task created for '{assignee}' in local queue."
            details = {
                "task_id": task_id,
                "title": action.description,
                "assignee": assignee,
                "deadline": action.deadline_text,
                "tracker": "mock_internal_tracker",
            }

        elif action_type in ("reminder", "calendar_event"):
            event_id = f"mock-event-{uuid.uuid4().hex[:8]}"
            target = action.owner or "Team"
            scheduled_time = action.deadline_text or "Next available review"
            simulated_action = "schedule_reminder" if action_type == "reminder" else "schedule_calendar_event"
            message = f"Simulated {action_type.replace('_', ' ')} scheduled for '{scheduled_time}'."
            details = {
                "event_id": event_id,
                "title": action.description,
                "target": target,
                "scheduled_time": scheduled_time,
                "calendar": "mock_local_calendar",
            }

        else:
            simulated_action = "generic_action"
            message = f"Simulated action execution completed for '{action.description}'."
            details = {
                "action_id": action.id,
                "type": action_type,
                "description": action.description,
                "owner": action.owner,
            }

        now_iso = datetime.now(timezone.utc).isoformat()
        result_payload: Dict[str, Any] = {
            "status": "success",
            "provider": self.provider_name,
            "is_mock": True,
            "simulated_action": simulated_action,
            "executed_at": now_iso,
            "message": message,
            "details": details,
        }

        # Preserve failure diagnostic if this was a retry
        if previous_result:
            result_payload["previous_result"] = previous_result
            result_payload["retry_count"] = retry_count

        return result_payload, True


def get_execution_service() -> BaseExecutionService:
    """
    Factory resolving configured execution provider.
    Fails explicitly if configured provider is unsupported (no silent fallback).
    """
    provider = settings.EXECUTION_PROVIDER.lower().strip()
    if provider == "mock":
        return MockExecutionService()

    raise ValueError(
        f"Unsupported execution provider: '{settings.EXECUTION_PROVIDER}'. "
        "MeetFlow MVP only supports 'mock' execution at this time."
    )
