"""MeetFlow FastAPI application entrypoint."""
import logging
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from typing import Optional
from datetime import datetime, timezone
from sqlalchemy import update
from app.core.config import settings
from app.database.session import engine, get_db, init_db, SessionLocal
from app.models.base import Base
from app.models.action import Action
from app.api.router import api_router
from app.api.v1.health import get_health
from app.schemas.health import HealthResponse

# Configure structured logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("meetflow")


def recover_stuck_actions(target_session: Optional[Session] = None) -> int:
    """
    Single-worker recovery sweep: safely mark any actions abandoned in 'executing' state
    from a previous crashed process as 'failed'.
    Idempotent and safe to run on every startup before incoming requests are accepted.
    Note: MeetFlow MVP supports a single server worker only. Multi-worker deployment is out of scope.
    """
    close_session = False
    session = target_session
    if session is None:
        session = SessionLocal()
        close_session = True

    try:
        stmt = (
            update(Action)
            .where(Action.approval_status == "executing")
            .values(
                approval_status="failed",
                execution_result={
                    "status": "failed",
                    "provider": "mock",
                    "is_mock": True,
                    "error": "Server was interrupted while action was executing. Outcome is uncertain.",
                    "interrupted_at": datetime.now(timezone.utc).isoformat(),
                },
                updated_at=datetime.now(timezone.utc),
            )
        )
        result = session.execute(stmt)
        session.commit()
        return result.rowcount
    finally:
        if close_session:
            session.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager: handle startup and shutdown events."""
    logger.info("Initializing MeetFlow database tables and schema...")
    init_db()

    # Recovery sweep for stuck executing actions (Single-worker local MVP only)
    recovered_count = recover_stuck_actions()
    if recovered_count > 0:
        logger.warning(f"Startup recovery sweep: marked {recovered_count} interrupted executing action(s) as failed.")

    # Ensure uploads directory exists
    if not os.path.exists(settings.UPLOAD_DIR):
        os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
        logger.info(f"Created uploads directory at {settings.UPLOAD_DIR}")

    logger.info(f"{settings.PROJECT_NAME} v{settings.VERSION} ready.")
    yield
    logger.info("Shutting down MeetFlow application...")


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="MeetFlow: Turn meeting recordings into approved, executable workflows.",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# Configure Cross-Origin Resource Sharing (CORS)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get(
    "/",
    tags=["root"],
    summary="Root Welcome Endpoint",
    description="Provides basic API status and links to documentation.",
)
def root():
    return {
        "app": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "docs_url": "/docs",
        "health_url": "/health",
        "api_v1_prefix": settings.API_V1_STR,
    }


# Mount central API router at root (for runtime backward compatibility)
# and under versioned prefix /api/v1 for API versioning support.
# Hide unversioned mount from OpenAPI to avoid duplicate entries in Swagger docs.
app.include_router(api_router, include_in_schema=False)
app.include_router(api_router, prefix=settings.API_V1_STR)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)
