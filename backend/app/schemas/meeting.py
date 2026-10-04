"""Pydantic schemas for meetings."""
from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field
from app.schemas.action import ActionResponse


class DecisionItem(BaseModel):
    """Schema for a decision reached during a meeting."""
    description: str = Field(..., description="Decision stated in the meeting")
    evidence: str = Field(..., description="Relevant transcript excerpt")


class OpenQuestionItem(BaseModel):
    """Schema for an unresolved topic or open question."""
    question: str = Field(..., description="Open question identified")
    evidence: str = Field(..., description="Relevant transcript excerpt")


class MeetingBase(BaseModel):
    """Base schema for meeting details."""
    title: Optional[str] = Field(default="Untitled Meeting", description="Meeting title")


class MeetingCreate(MeetingBase):
    """Schema for initializing a new meeting record."""
    pass


class MeetingUpdate(BaseModel):
    """Schema for updating meeting transcript or metadata."""
    title: Optional[str] = None
    transcript: Optional[str] = None


class MeetingResponse(MeetingBase):
    """Schema for basic meeting representation."""
    id: str
    status: str
    audio_filename: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class MeetingDetailResponse(MeetingResponse):
    """Detailed schema for meeting with transcript, summary, decisions, and actions."""
    transcript: Optional[str] = None
    summary: Optional[str] = None
    decisions: Optional[List[Dict[str, Any]]] = None
    open_questions: Optional[List[Dict[str, Any]]] = None
    transcription_provider: Optional[str] = None
    extraction_provider: Optional[str] = None
    is_mock: Optional[bool] = False
    actions: List[ActionResponse] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)
