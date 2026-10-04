"""Meeting SQLAlchemy ORM model."""
from typing import Optional, List, TYPE_CHECKING
import uuid
from sqlalchemy import String, Text, JSON, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.action import Action


class Meeting(Base, TimestampMixin):
    """Database model representing a recorded meeting and its processing pipeline."""
    __tablename__ = "meetings"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        index=True,
    )
    title: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        default="Untitled Meeting",
    )
    status: Mapped[str] = mapped_column(
        String(50),
        default="created",
        nullable=False,
        index=True,
    )
    audio_file_path: Mapped[Optional[str]] = mapped_column(
        String(512),
        nullable=True,
    )
    audio_filename: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )
    transcript: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    summary: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    decisions: Mapped[Optional[list]] = mapped_column(
        JSON,
        nullable=True,
        default=list,
    )
    open_questions: Mapped[Optional[list]] = mapped_column(
        JSON,
        nullable=True,
        default=list,
    )
    transcription_provider: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        default=None,
    )
    extraction_provider: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        default=None,
    )
    is_mock: Mapped[Optional[bool]] = mapped_column(
        Boolean,
        nullable=True,
        default=False,
    )

    # Relationship to extracted actions
    actions: Mapped[List["Action"]] = relationship(
        "Action",
        back_populates="meeting",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
