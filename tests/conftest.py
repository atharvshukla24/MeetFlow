"""Pytest configuration and fixtures for testing MeetFlow."""
import os
import sys
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# Ensure backend directory is in Python path for test discovery
BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.main import app
from app.models.base import Base
from app.database.session import get_db, init_db

# Use an in-memory SQLite database for isolated tests
TEST_DATABASE_URL = "sqlite:///:memory:"

test_engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


@pytest.fixture(scope="session", autouse=True)
def setup_test_db():
    """Create tables and ensure schema columns in the in-memory test database."""
    init_db(target_engine=test_engine)
    yield
    Base.metadata.drop_all(bind=test_engine)


@pytest.fixture(autouse=True)
def default_mock_providers():
    """
    Ensure automated tests run with offline mock providers by default
    so that unit tests never make external network calls or require live API keys.
    Dedicated tests (e.g. test_gemini_transcription.py and test_gemma_extraction.py)
    explicitly patch settings to test real providers using mocks.
    """
    from app.core.config import settings
    orig_transcription = settings.TRANSCRIPTION_PROVIDER
    orig_extraction = settings.EXTRACTION_PROVIDER
    settings.TRANSCRIPTION_PROVIDER = "mock"
    settings.EXTRACTION_PROVIDER = "mock"
    yield
    settings.TRANSCRIPTION_PROVIDER = orig_transcription
    settings.EXTRACTION_PROVIDER = orig_extraction


@pytest.fixture
def db_session():
    """Yield a transactional database session for a test."""
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client(db_session):
    """Provide a FastAPI TestClient with the database dependency overridden."""
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
