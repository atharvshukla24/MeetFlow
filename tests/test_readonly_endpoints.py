"""Tests for newly added read-only endpoints (meetings list/detail and actions list)."""
import uuid
import time
from datetime import datetime, timezone
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.meeting import Meeting
from app.models.action import Action


def test_list_meetings_empty(client: TestClient, db_session: Session):
    """When no meetings exist, returns an empty list."""
    # Ensure database is empty of meetings for this check
    db_session.query(Action).delete()
    db_session.query(Meeting).delete()
    db_session.commit()

    response = client.get("/api/v1/meetings")
    assert response.status_code == 200
    assert response.json() == []


def test_list_meetings_ordered_by_created_at_desc(client: TestClient, db_session: Session):
    """Meetings must be returned in descending order of created_at."""
    m1 = Meeting(
        id=str(uuid.uuid4()),
        title="First Meeting",
        status="uploaded",
        created_at=datetime(2026, 10, 1, 10, 0, 0, tzinfo=timezone.utc),
    )
    m2 = Meeting(
        id=str(uuid.uuid4()),
        title="Second Meeting",
        status="transcribed",
        created_at=datetime(2026, 10, 2, 10, 0, 0, tzinfo=timezone.utc),
    )
    m3 = Meeting(
        id=str(uuid.uuid4()),
        title="Third Meeting",
        status="analyzed",
        created_at=datetime(2026, 10, 3, 10, 0, 0, tzinfo=timezone.utc),
    )
    db_session.add_all([m1, m2, m3])
    db_session.commit()

    response = client.get("/api/v1/meetings")
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 3

    # Find indices of our test meetings
    ids = [item["id"] for item in data]
    assert ids.index(m3.id) < ids.index(m2.id) < ids.index(m1.id)


def test_get_meeting_details_success(client: TestClient, db_session: Session):
    """GET /meetings/{id} returns full meeting details."""
    meeting_id = str(uuid.uuid4())
    meeting = Meeting(
        id=meeting_id,
        title="Sprint Planning Meeting",
        status="analyzed",
        audio_filename="sprint_sync.wav",
        transcript="[00:00:02] Alice: Let's begin the planning.",
        summary="Sprint planning meeting covering release goals.",
        decisions=[{"description": "Release on Tuesday", "evidence": "Let's release on Tuesday"}],
        open_questions=[{"question": "Who owns QA?", "evidence": "Who owns QA?"}],
    )
    db_session.add(meeting)

    action = Action(
        id=str(uuid.uuid4()),
        meeting_id=meeting_id,
        type="task",
        description="Verify staging deployment",
        owner="Bob",
        approval_status="pending",
    )
    db_session.add(action)
    db_session.commit()

    response = client.get(f"/api/v1/meetings/{meeting_id}")
    assert response.status_code == 200
    data = response.json()

    assert data["id"] == meeting_id
    assert data["title"] == "Sprint Planning Meeting"
    assert data["status"] == "analyzed"
    assert data["audio_filename"] == "sprint_sync.wav"
    assert data["transcript"] == "[00:00:02] Alice: Let's begin the planning."
    assert data["summary"] == "Sprint planning meeting covering release goals."
    assert len(data["decisions"]) == 1
    assert len(data["open_questions"]) == 1
    assert len(data["actions"]) == 1
    assert data["actions"][0]["id"] == action.id


def test_get_meeting_details_not_found(client: TestClient):
    """GET /meetings/{nonexistent_id} returns 404."""
    response = client.get(f"/api/v1/meetings/{uuid.uuid4()}")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_list_actions_ordered_by_created_at_desc(client: TestClient, db_session: Session):
    """Actions must be returned ordered by created_at descending."""
    meeting = Meeting(id=str(uuid.uuid4()), title="Sync", status="analyzed")
    db_session.add(meeting)

    a1 = Action(
        id=str(uuid.uuid4()),
        meeting_id=meeting.id,
        type="task",
        description="Old action",
        approval_status="pending",
        created_at=datetime(2026, 10, 1, 9, 0, 0, tzinfo=timezone.utc),
    )
    a2 = Action(
        id=str(uuid.uuid4()),
        meeting_id=meeting.id,
        type="email",
        description="New action",
        approval_status="approved",
        created_at=datetime(2026, 10, 2, 9, 0, 0, tzinfo=timezone.utc),
    )
    db_session.add_all([a1, a2])
    db_session.commit()

    response = client.get("/api/v1/actions")
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 2

    ids = [item["id"] for item in data]
    assert ids.index(a2.id) < ids.index(a1.id)


def test_readonly_endpoints_work_with_both_prefixes(client: TestClient, db_session: Session):
    """Both /meetings and /api/v1/meetings work identically at runtime."""
    meeting = Meeting(id=str(uuid.uuid4()), title="Prefix Test", status="uploaded")
    db_session.add(meeting)
    db_session.commit()

    res_root = client.get(f"/meetings/{meeting.id}")
    assert res_root.status_code == 200

    res_v1 = client.get(f"/api/v1/meetings/{meeting.id}")
    assert res_v1.status_code == 200
    assert res_root.json()["id"] == res_v1.json()["id"]
