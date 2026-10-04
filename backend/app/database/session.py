"""Database engine and session management for SQLite."""
from typing import Generator
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from app.core.config import settings

# For SQLite, check_same_thread=False is required to allow multiple threads to access it in FastAPI
connect_args = {}
if settings.DATABASE_URL.startswith("sqlite"):
    connect_args["check_same_thread"] = False

engine = create_engine(
    settings.DATABASE_URL,
    connect_args=connect_args,
    echo=False,
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)


def get_db() -> Generator[Session, None, None]:
    """Dependency for obtaining database sessions in FastAPI route handlers."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db(target_engine=None) -> None:
    """
    Initialize database tables and safely add missing columns if upgrading an existing SQLite database.
    Does not rely solely on create_all() to alter existing tables.
    """
    from app.models.base import Base
    import app.models  # Ensure models are imported

    active_engine = target_engine or engine
    Base.metadata.create_all(bind=active_engine)

    if str(active_engine.url).startswith("sqlite"):
        with active_engine.connect() as conn:
            cursor = conn.execute(text("PRAGMA table_info(meetings)"))
            columns = {row[1] for row in cursor.fetchall()}
            if columns:
                if "transcription_provider" not in columns:
                    conn.execute(text("ALTER TABLE meetings ADD COLUMN transcription_provider VARCHAR(50)"))
                if "extraction_provider" not in columns:
                    conn.execute(text("ALTER TABLE meetings ADD COLUMN extraction_provider VARCHAR(50)"))
                if "is_mock" not in columns:
                    conn.execute(text("ALTER TABLE meetings ADD COLUMN is_mock BOOLEAN DEFAULT 1"))
            conn.commit()
