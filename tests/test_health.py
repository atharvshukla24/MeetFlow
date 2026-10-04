"""Unit and integration tests for health endpoints and database models."""
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from app.models.meeting import Meeting
from app.models.action import Action


def test_root_endpoint(client: TestClient):
    """Test that the root endpoint returns API information."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["app"] == "MeetFlow API"
    assert "version" in data
    assert data["health_url"] == "/health"
    assert data["api_v1_prefix"] == "/api/v1"


def test_root_health_endpoint(client: TestClient):
    """Test the GET /health endpoint."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["app"] == "MeetFlow API"
    assert data["database"] == "connected"
    assert data["environment"] == "development"
    assert "version" in data


def test_v1_health_endpoint(client: TestClient):
    """Test the GET /api/v1/health endpoint."""
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["app"] == "MeetFlow API"
    assert data["database"] == "connected"


def test_database_models_can_persist(db_session: Session):
    """Verify that Meeting and Action models can be persisted and queried in SQLite."""
    # 1. Create a meeting
    meeting = Meeting(
        title="Weekly Sync Test",
        status="created",
        audio_filename="test_meeting.wav",
    )
    db_session.add(meeting)
    db_session.commit()
    db_session.refresh(meeting)

    assert meeting.id is not None
    assert meeting.created_at is not None
    assert meeting.updated_at is not None
    assert meeting.title == "Weekly Sync Test"
    assert meeting.status == "created"

    # 2. Create an action linked to this meeting
    action = Action(
        meeting_id=meeting.id,
        type="task",
        description="Verify backend foundation",
        owner="Atharv",
        deadline_text="Friday",
        evidence="Atharv to verify backend foundation by Friday",
        confidence="high",
        needs_clarification=False,
        approval_status="pending",
    )
    db_session.add(action)
    db_session.commit()
    db_session.refresh(action)

    assert action.id is not None
    assert action.meeting_id == meeting.id
    assert action.type == "task"
    assert action.approval_status == "pending"

    # 3. Test relationship access
    db_session.refresh(meeting)
    assert len(meeting.actions) == 1
    assert meeting.actions[0].description == "Verify backend foundation"
