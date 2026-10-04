"""Pydantic schemas for transcription requests and responses."""
from typing import Optional
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field, field_validator


class TranscriptResponse(BaseModel):
    """Response schema for meeting transcription."""
    meeting_id: str = Field(..., description="ID of the transcribed meeting")
    status: str = Field(..., description="Current meeting status, e.g. 'transcribed'")
    transcription_provider: Optional[str] = Field(
        default=None,
        description="Name of the transcription provider used (e.g. 'gemini' or 'mock')",
    )
    is_mock: bool = Field(
        default=False,
        description="Flag indicating whether transcript content is synthetic/mock data",
    )
    transcript: str = Field(..., description="Full formatted transcript text with speaker labels and timestamps")
    audio_filename: Optional[str] = Field(
        default=None,
        description="Original uploaded audio filename",
    )
    updated_at: datetime = Field(..., description="Timestamp of the update")

    model_config = ConfigDict(from_attributes=True)


class TranscriptUpdate(BaseModel):
    """
    Schema for updating meeting transcript text.
    Client cannot supply is_mock or transcription_provider; extra fields are strictly forbidden.
    """
    transcript: str = Field(
        ...,
        min_length=1,
        description="Updated transcript text with speaker turns and timestamps",
        examples=["[00:00:02] Sarah: Good morning team..."],
    )

    @field_validator("transcript")
    @classmethod
    def validate_non_empty(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("Transcript cannot be empty or whitespace only.")
        return stripped

    model_config = ConfigDict(extra="forbid")

