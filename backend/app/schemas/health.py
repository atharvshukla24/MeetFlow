"""Health check schemas."""
from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    """Schema for health check endpoint responses."""
    status: str = Field(..., description="Overall service status", examples=["healthy"])
    app: str = Field(..., description="Application name", examples=["MeetFlow API"])
    version: str = Field(..., description="API version", examples=["0.1.0"])
    database: str = Field(..., description="Database connection status", examples=["connected"])
    environment: str = Field(..., description="Current deployment environment", examples=["development"])
