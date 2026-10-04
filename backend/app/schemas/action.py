"""Pydantic schemas for actions."""
from typing import Optional, Literal, Dict, Any
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field

ActionType = Literal["task", "email", "message", "reminder", "calendar_event"]
ApprovalStatus = Literal[
    "pending",
    "edited",
    "approved",
    "rejected",
    "executing",
    "succeeded",
    "failed",
    "needs_clarification",
]


class ActionBase(BaseModel):
    """Base schema for action items."""
    type: ActionType = Field(default="task", description="Action type")
    description: str = Field(..., description="Action description")
    owner: Optional[str] = Field(default=None, description="Responsible person (never invented)")
    deadline_text: Optional[str] = Field(default=None, description="Spoken or confirmed deadline text")
    recipient_email: Optional[str] = Field(default=None, description="Recipient email address if explicitly stated")
    draft_subject: Optional[str] = Field(default=None, description="Draft email/message subject")
    draft_body: Optional[str] = Field(default=None, description="Draft email/message body content")
    evidence: Optional[str] = Field(default=None, description="Transcript excerpt backing this action")
    confidence: Optional[str] = Field(default="medium", description="Confidence level: high, medium, low")
    needs_clarification: bool = Field(default=False, description="Flag indicating missing critical details")
    approval_status: ApprovalStatus = Field(default="pending", description="Current workflow state")


class ActionCreate(ActionBase):
    """Schema for creating a new action."""
    meeting_id: str


class ActionUpdate(BaseModel):
    """Schema for user-editing an action."""
    type: Optional[ActionType] = None
    description: Optional[str] = None
    owner: Optional[str] = None
    deadline_text: Optional[str] = None
    recipient_email: Optional[str] = None
    draft_subject: Optional[str] = None
    draft_body: Optional[str] = None
    needs_clarification: Optional[bool] = None
    approval_status: Optional[ApprovalStatus] = None


class ActionResponse(ActionBase):
    """Schema for action returned in responses."""
    id: str
    meeting_id: str
    execution_result: Optional[Dict[str, Any]] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
