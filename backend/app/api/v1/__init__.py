"""API v1 endpoints."""
from app.api.v1.health import router as health_router
from app.api.v1.meetings import router as meetings_router

__all__ = ["health_router", "meetings_router"]
