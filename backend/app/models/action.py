"""Action SQLAlchemy ORM model representing proposed actions and execution state."""
from typing import Optional, TYPE_CHECKING
import uuid
from sqlalchemy import String, Text, Boolean, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.meeting import Meeting


class Action(Base, TimestampMixin):
    """Database model representing an action item, email draft, reminder, or task extracted from a meeting."""
    __tablename__ = "actions"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        index=True,
    )
    meeting_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("meetings.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # Action type: task, email, message, reminder, calendar_event
    type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="task",
    )
    description: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    owner: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )
    deadline_text: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )
    recipient_email: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )
    draft_subject: Mapped[Optional[str]] = mapped_column(
        String(512),
        nullable=True,
    )
    draft_body: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    evidence: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    confidence: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        default="medium",
    )
    needs_clarification: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    # Workflow approval state: pending, edited, approved, rejected, executing, succeeded, failed, needs_clarification
    approval_status: Mapped[str] = mapped_column(
        String(50),
        default="pending",
        nullable=False,
        index=True,
    )
    # Execution details / tool results
    execution_result: Mapped[Optional[dict]] = mapped_column(
        JSON,
        nullable=True,
    )

    # Relationship back to parent meeting
    meeting: Mapped["Meeting"] = relationship(
        "Meeting",
        back_populates="actions",
    )
