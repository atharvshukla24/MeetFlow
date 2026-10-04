"""Central API routing configuration."""
from fastapi import APIRouter
from app.api.v1.health import router as health_router
from app.api.v1.meetings import router as meetings_router
from app.api.v1.actions import router as actions_router

api_router = APIRouter()

# Mount API v1 health routes
api_router.include_router(health_router, prefix="", tags=["health"])

# Mount API v1 meetings routes
api_router.include_router(meetings_router)

# Mount API v1 actions routes
api_router.include_router(actions_router)
