"""Pydantic schemas for workflow extraction, decisions, and action items."""
from typing import Optional, List, Literal
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field
from app.schemas.action import ActionResponse


class DecisionItem(BaseModel):
    """Schema for a decision agreed in the meeting."""
    description: str = Field(..., description="Decision agreed in meeting")
    evidence: str = Field(..., description="Exact transcript excerpt")


class OpenQuestionItem(BaseModel):
    """Schema for an unresolved topic or open question."""
    question: str = Field(..., description="Unresolved topic or question")
    evidence: str = Field(..., description="Transcript excerpt identifying the open topic")


class ExtractedActionItem(BaseModel):
    """Schema for an action item extracted from meeting dialogue."""
    type: Literal["task", "email", "message", "reminder", "calendar_event"] = Field(
        default="task",
        description="Action type",
    )
    description: str = Field(..., description="Actionable task description")
    owner: Optional[str] = Field(default=None, description="Explicitly assigned owner or None")
    deadline_text: Optional[str] = Field(default=None, description="Relative or spoken deadline or None")
    recipient_email: Optional[str] = Field(default=None, description="Explicitly stated recipient email or None")
    draft_subject: Optional[str] = Field(default=None, description="Email/message draft subject if applicable")
    draft_body: Optional[str] = Field(default=None, description="Email/message draft body if applicable")
    evidence: str = Field(..., description="Direct transcript excerpt justifying this action")
    confidence: Literal["high", "medium", "low"] = Field(default="high", description="Extraction confidence")
    needs_clarification: bool = Field(default=False, description="Flag indicating missing critical details")
    approval_status: str = Field(default="pending", description="Initial workflow approval status")


class WorkflowExtractionContract(BaseModel):
    """Contract schema for raw extraction output from an extraction provider."""
    summary: str = Field(..., description="Concise meeting summary")
    decisions: List[DecisionItem] = Field(default_factory=list)
    actions: List[ExtractedActionItem] = Field(default_factory=list)
    open_questions: List[OpenQuestionItem] = Field(default_factory=list)


class WorkflowResponse(BaseModel):
    """Client response schema for meeting workflow details."""
    meeting_id: str = Field(..., description="Meeting ID")
    status: str = Field(..., description="Current meeting status")
    extraction_provider: str = Field(default="mock", description="Provider used for extraction")
    is_mock: bool = Field(default=True, description="Indicates if workflow is mock/synthetic")
    summary: Optional[str] = Field(default=None, description="Meeting summary")
    decisions: List[DecisionItem] = Field(default_factory=list, description="List of decisions")
    open_questions: List[OpenQuestionItem] = Field(default_factory=list, description="List of open questions")
    actions: List[ActionResponse] = Field(default_factory=list, description="List of extracted action items")
    created_at: datetime = Field(..., description="Meeting creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")

    model_config = ConfigDict(from_attributes=True)
