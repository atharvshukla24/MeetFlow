"""Health check route."""
import logging
from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.orm import Session
from app.database.session import get_db
from app.core.config import settings
from app.schemas.health import HealthResponse

logger = logging.getLogger(__name__)

router = APIRouter(tags=["health"])


@router.get(
    "/health",
    response_model=HealthResponse,
    status_code=status.HTTP_200_OK,
    summary="Health Check",
    description="Check the operational status of the API and its database connection.",
)
def get_health(db: Session = Depends(get_db)):
    """Return system status including database connectivity check."""
    db_status = "connected"
    try:
        # Verify SQLite connection is responsive
        db.execute(text("SELECT 1"))
    except Exception as exc:
        logger.error(f"Database health check failed: {exc}")
        db_status = "disconnected"
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "status": "unhealthy",
                "app": settings.PROJECT_NAME,
                "version": settings.VERSION,
                "database": db_status,
                "environment": settings.ENVIRONMENT,
            },
        )

    return HealthResponse(
        status="healthy",
        app=settings.PROJECT_NAME,
        version=settings.VERSION,
        database=db_status,
        environment=settings.ENVIRONMENT,
    )
