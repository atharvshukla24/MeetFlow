"""Meeting API endpoints."""
import uuid
import logging
from pathlib import Path
from typing import Optional, List
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, UploadFile, File, Form, status, HTTPException
from sqlalchemy import update
from sqlalchemy.orm import Session

from app.core.config import settings
from app.database.session import get_db
from app.models.meeting import Meeting
from app.models.action import Action
from app.schemas.meeting import MeetingResponse, MeetingDetailResponse
from app.schemas.action import ActionResponse
from app.schemas.transcript import TranscriptResponse, TranscriptUpdate
from app.schemas.workflow import DecisionItem, OpenQuestionItem, WorkflowResponse
from app.services.storage import save_uploaded_audio, delete_stored_file
from app.services.transcription import get_transcription_service
from app.services.extraction import get_extraction_service, validate_evidence_in_transcript

logger = logging.getLogger("meetflow.meetings")

router = APIRouter(prefix="/meetings", tags=["meetings"])

ALLOWED_TRANSCRIBE_START_STATUSES = ["uploaded", "transcribed", "transcription_failed", "analyzed", "analysis_failed"]
ALLOWED_ANALYZE_START_STATUSES = ["transcribed", "analyzed", "analysis_failed"]
SYNTHETIC_BANNER = "[SYNTHETIC SAMPLE TRANSCRIPT — DEMO ONLY]"


@router.post(
    "/upload",
    response_model=MeetingResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload Meeting Audio",
    description="Upload a recorded meeting audio file for processing. Validates audio format and stores securely.",
)
async def upload_meeting_audio(
    file: UploadFile = File(..., description="Audio recording file (.wav, .mp3, .m4a, .aac, .ogg, .flac)"),
    title: Optional[str] = Form(default="Untitled Meeting", description="Meeting title"),
    db: Session = Depends(get_db),
):
    """
    Accepts multipart audio upload, performs extension and magic-byte validation,
    enforces 50 MB read-time limit, and creates a meeting record in SQLite.
    Rolls back database transaction and cleans up stored files if any failure occurs.
    """
    meeting_id = str(uuid.uuid4())

    # 1. Save and validate audio stream safely
    saved_file_path, display_filename, _ = await save_uploaded_audio(
        upload_file=file,
        meeting_id=meeting_id,
    )

    # 2. Persist meeting record with safe rollback and file cleanup
    try:
        meeting = Meeting(
            id=meeting_id,
            title=title.strip() if title and title.strip() else "Untitled Meeting",
            status="uploaded",
            audio_file_path=saved_file_path,
            audio_filename=display_filename,
            transcript=None,
            summary=None,
            decisions=[],
            open_questions=[],
            transcription_provider=None,
            extraction_provider=None,
            is_mock=False,
        )
        db.add(meeting)
        db.commit()
        db.refresh(meeting)
        logger.info(f"Meeting {meeting_id} created with audio '{display_filename}'.")
        return meeting
    except Exception as exc:
        db.rollback()
        logger.error(f"Database error creating meeting {meeting_id}: {exc}")
        # Clean up stored audio file on database failure
        delete_stored_file(saved_file_path)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database transaction failed during meeting creation.",
        )


@router.get(
    "",
    response_model=List[MeetingResponse],
    status_code=status.HTTP_200_OK,
    summary="List Meetings",
    description="Retrieve all meetings ordered by creation date descending.",
)
def list_meetings(
    db: Session = Depends(get_db),
):
    """Retrieve list of all meetings ordered by creation date descending."""
    return db.query(Meeting).order_by(Meeting.created_at.desc()).all()


@router.get(
    "/{meeting_id}",
    response_model=MeetingDetailResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Meeting Details",
    description="Retrieve complete meeting details by ID including transcript, summary, and actions.",
)
def get_meeting(
    meeting_id: str,
    db: Session = Depends(get_db),
):
    """Retrieve individual meeting details by ID. Returns 404 if not found."""
    meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
    if not meeting:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Meeting '{meeting_id}' not found.",
        )
    return meeting


@router.post(
    "/{meeting_id}/transcribe",
    response_model=TranscriptResponse,
    status_code=status.HTTP_200_OK,
    summary="Transcribe Meeting",
    description="Transcribe meeting audio using configured provider. In Phase 2/3, uses Mock provider with atomic concurrency control.",
)
async def transcribe_meeting(
    meeting_id: str,
    db: Session = Depends(get_db),
):
    """
    Execute speech-to-text transcription on the meeting's stored audio recording.
    Uses atomic conditional SQL update to prevent concurrent duplicate processing.
    Recovers to 'transcription_failed' state on unexpected execution errors.
    """
    # 1. Verify meeting existence
    meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
    if not meeting:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Meeting '{meeting_id}' not found.",
        )

    # 2. Check audio recording presence
    if not meeting.audio_file_path:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No audio recording associated with this meeting.",
        )

    # 3. Verify physical audio file existence on disk
    if not Path(meeting.audio_file_path).exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Audio file missing from server storage.",
        )

    # Capture previous state in case of failure
    previous_transcript = meeting.transcript

    # 4. Atomic conditional status update to prevent race conditions
    stmt = (
        update(Meeting)
        .where(
            Meeting.id == meeting_id,
            Meeting.status.in_(ALLOWED_TRANSCRIBE_START_STATUSES),
        )
        .values(status="transcribing")
    )
    result = db.execute(stmt)
    db.commit()

    if result.rowcount == 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Transcription is already in progress for this meeting.",
        )

    db.refresh(meeting)

    # 5. Resolve transcription provider and execute
    try:
        service = get_transcription_service()
        transcript_text, is_mock = await service.transcribe(meeting.audio_file_path)
        meeting.transcript = transcript_text
        meeting.transcription_provider = service.provider_name
        meeting.is_mock = is_mock
        meeting.status = "transcribed"
        db.commit()
        db.refresh(meeting)

        logger.info(f"Meeting {meeting_id} transcribed successfully using {service.provider_name}.")
        return TranscriptResponse(
            meeting_id=meeting.id,
            status=meeting.status,
            transcription_provider=service.provider_name,
            is_mock=is_mock,
            transcript=meeting.transcript,
            audio_filename=meeting.audio_filename,
            updated_at=meeting.updated_at,
        )

    except HTTPException as exc:
        db.rollback()
        logger.error(f"HTTPException during transcription for meeting {meeting_id}: {exc.detail}")
        try:
            meeting.status = "transcription_failed"
            meeting.transcript = previous_transcript
            db.commit()
            db.refresh(meeting)
        except Exception as rollback_err:
            db.rollback()
            logger.error(f"Failed to record transcription_failed state: {rollback_err}")
        raise exc
    except Exception as exc:
        db.rollback()
        logger.error(f"Transcription failed for meeting {meeting_id}: {exc}")

        # Safely transition state to 'transcription_failed' so meeting is not stuck in 'transcribing'
        try:
            meeting.status = "transcription_failed"
            meeting.transcript = previous_transcript
            db.commit()
            db.refresh(meeting)
        except Exception as rollback_err:
            db.rollback()
            logger.error(f"Failed to record transcription_failed state: {rollback_err}")

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Transcription failed: {str(exc)}",
        )


@router.get(
    "/{meeting_id}/transcript",
    response_model=TranscriptResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Meeting Transcript",
    description="Retrieve the transcript and metadata for a transcribed meeting.",
)
def get_meeting_transcript(
    meeting_id: str,
    db: Session = Depends(get_db),
):
    """
    Retrieve transcript for a meeting.
    Requires that the meeting exists and is in 'transcribed' status.
    """
    meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
    if not meeting:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Meeting '{meeting_id}' not found.",
        )

    if meeting.status == "transcribing":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Transcription is currently in progress for this meeting.",
        )

    if not meeting.transcript:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Transcript is not ready for this meeting. Current status: '{meeting.status}'.",
        )

    # Server-controlled metadata
    is_mock = meeting.is_mock if meeting.is_mock is not None else (meeting.transcript.startswith(SYNTHETIC_BANNER))
    if meeting.transcript.startswith(SYNTHETIC_BANNER):
        is_mock = True

    provider = meeting.transcription_provider or ("mock" if is_mock else "gemini")

    return TranscriptResponse(
        meeting_id=meeting.id,
        status=meeting.status,
        transcription_provider=provider,
        is_mock=is_mock,
        transcript=meeting.transcript,
        audio_filename=meeting.audio_filename,
        updated_at=meeting.updated_at,
    )


@router.patch(
    "/{meeting_id}/transcript",
    response_model=TranscriptResponse,
    status_code=status.HTTP_200_OK,
    summary="Edit Meeting Transcript",
    description="Update the transcript text of a transcribed meeting. Preserves synthetic labelling and protects against concurrent updates.",
)
def update_meeting_transcript(
    meeting_id: str,
    payload: TranscriptUpdate,
    db: Session = Depends(get_db),
):
    """
    Update transcript text for a meeting.
    Requires that the meeting exists and is currently in 'transcribed' status.
    Uses atomic conditional update to prevent race conditions.
    """
    meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
    if not meeting:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Meeting '{meeting_id}' not found.",
        )

    if meeting.status == "transcribing":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot edit transcript while transcription is in progress.",
        )

    if meeting.status != "transcribed":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot edit transcript: meeting is not in 'transcribed' status (current status: '{meeting.status}').",
        )

    # Determine if this was a mock transcript
    is_mock = meeting.is_mock if meeting.is_mock is not None else (meeting.transcript.startswith(SYNTHETIC_BANNER))
    if meeting.transcript.startswith(SYNTHETIC_BANNER):
        is_mock = True

    provider = meeting.transcription_provider or ("mock" if is_mock else "gemini")

    submitted_text = payload.transcript.strip()
    # Preserve/re-attach synthetic banner if omitted by user on mock transcript
    if is_mock and not submitted_text.startswith(SYNTHETIC_BANNER):
        final_transcript = f"{SYNTHETIC_BANNER}\n{submitted_text}"
    else:
        final_transcript = submitted_text

    # Atomic conditional update requiring status == 'transcribed'
    stmt = (
        update(Meeting)
        .where(
            Meeting.id == meeting_id,
            Meeting.status == "transcribed",
        )
        .values(
            transcript=final_transcript,
            updated_at=datetime.now(timezone.utc),
        )
    )
    result = db.execute(stmt)
    db.commit()

    if result.rowcount == 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot edit transcript: meeting is no longer in 'transcribed' status.",
        )

    db.refresh(meeting)
    logger.info(f"Transcript updated for meeting {meeting_id}.")

    return TranscriptResponse(
        meeting_id=meeting.id,
        status=meeting.status,
        transcription_provider=provider,
        is_mock=is_mock,
        transcript=meeting.transcript,
        audio_filename=meeting.audio_filename,
        updated_at=meeting.updated_at,
    )


@router.post(
    "/{meeting_id}/analyze",
    response_model=WorkflowResponse,
    status_code=status.HTTP_200_OK,
    summary="Analyze Meeting Transcript",
    description="Extract actionable workflow (tasks, decisions, open questions) from transcript. Safe transactional re-analysis.",
)
async def analyze_meeting(
    meeting_id: str,
    db: Session = Depends(get_db),
):
    """
    Execute workflow extraction on meeting transcript.
    Uses atomic conditional update to prevent race conditions.
    Safely preserves previous workflow if re-analysis fails.
    """
    meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
    if not meeting:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Meeting '{meeting_id}' not found.",
        )

    if meeting.status == "uploaded":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Meeting must be transcribed before workflow extraction. Current status: 'uploaded'.",
        )

    if not meeting.transcript or not meeting.transcript.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Meeting has no transcript content to analyze.",
        )

    # Capture exact previous status before transition to analyzing (Safeguard 2)
    previous_status = meeting.status

    # Atomic conditional update requiring status in ALLOWED_ANALYZE_START_STATUSES
    stmt = (
        update(Meeting)
        .where(
            Meeting.id == meeting_id,
            Meeting.status.in_(ALLOWED_ANALYZE_START_STATUSES),
        )
        .values(status="analyzing")
    )
    result = db.execute(stmt)
    db.commit()

    if result.rowcount == 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Workflow analysis is already in progress for this meeting.",
        )

    db.refresh(meeting)

    # Resolve extraction provider and extract workflow in-memory (Safeguard 3)
    try:
        service = get_extraction_service()
        contract, is_mock = await service.extract_workflow(meeting.transcript)
        # Validate that all extracted evidence excerpts are present in the transcript
        validate_evidence_in_transcript(contract, meeting.transcript)
    except HTTPException as exc:
        logger.error(f"Extraction error for meeting {meeting_id}: {exc.detail}")
        # Safe recovery: restore exact previous status without deleting existing actions
        try:
            meeting.status = previous_status
            db.commit()
            db.refresh(meeting)
        except Exception as rollback_err:
            db.rollback()
            logger.exception(f"Failed to restore previous status for {meeting_id}: {rollback_err}")
        raise exc
    except Exception as exc:
        logger.exception(f"Internal error during extraction/validation for meeting {meeting_id}: {exc}")
        # Safe recovery: restore exact previous status without deleting existing actions
        try:
            meeting.status = previous_status
            db.commit()
            db.refresh(meeting)
        except Exception as rollback_err:
            db.rollback()
            logger.exception(f"Failed to restore previous status for {meeting_id}: {rollback_err}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Workflow extraction failed due to an internal error: {str(exc)}",
        )

    # Perform atomic transactional replacement of actions and metadata
    try:
        # Clear old unapproved actions; do not overwrite approved or executed actions during reanalysis
        db.query(Action).filter(
            Action.meeting_id == meeting_id,
            Action.approval_status.notin_(["approved", "executing", "succeeded", "failed"]),
        ).delete(synchronize_session=False)

        for item in contract.actions:
            new_action = Action(
                id=str(uuid.uuid4()),
                meeting_id=meeting_id,
                type=item.type,
                description=item.description,
                owner=item.owner,
                deadline_text=item.deadline_text,
                recipient_email=item.recipient_email,
                draft_subject=item.draft_subject,
                draft_body=item.draft_body,
                evidence=item.evidence,
                confidence=item.confidence,
                needs_clarification=item.needs_clarification,
                approval_status="pending",
            )
            db.add(new_action)

        meeting.summary = contract.summary
        meeting.decisions = [d.model_dump() for d in contract.decisions]
        meeting.open_questions = [q.model_dump() for q in contract.open_questions]
        meeting.extraction_provider = service.provider_name
        meeting.is_mock = is_mock
        meeting.status = "analyzed"
        meeting.updated_at = datetime.now(timezone.utc)

        db.commit()
        db.refresh(meeting)
        logger.info(f"Workflow successfully extracted and committed for meeting {meeting_id}.")
    except Exception as exc:
        db.rollback()
        logger.exception(f"Database error committing workflow for meeting {meeting_id}: {exc}")
        try:
            meeting.status = previous_status
            db.commit()
            db.refresh(meeting)
        except Exception:
            db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to persist extracted workflow due to an internal database error.",
        )

    return WorkflowResponse(
        meeting_id=meeting.id,
        status=meeting.status,
        extraction_provider=meeting.extraction_provider or "mock",
        is_mock=meeting.is_mock if meeting.is_mock is not None else True,
        summary=meeting.summary,
        decisions=[DecisionItem(**d) for d in (meeting.decisions or [])],
        open_questions=[OpenQuestionItem(**q) for q in (meeting.open_questions or [])],
        actions=[ActionResponse.model_validate(a) for a in meeting.actions],
        created_at=meeting.created_at,
        updated_at=meeting.updated_at,
    )


@router.get(
    "/{meeting_id}/workflow",
    response_model=WorkflowResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Meeting Workflow",
    description="Retrieve extracted workflow (summary, decisions, open questions, actions) for an analyzed meeting.",
)
def get_meeting_workflow(
    meeting_id: str,
    db: Session = Depends(get_db),
):
    """
    Retrieve extracted workflow items for a meeting.
    Requires meeting to be in 'analyzed' status.
    """
    meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
    if not meeting:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Meeting '{meeting_id}' not found.",
        )

    if meeting.status == "analyzing":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Workflow analysis is currently in progress for this meeting.",
        )

    if meeting.status != "analyzed":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Workflow has not been extracted yet. Current status: '{meeting.status}'.",
        )

    return WorkflowResponse(
        meeting_id=meeting.id,
        status=meeting.status,
        extraction_provider=meeting.extraction_provider or "mock",
        is_mock=meeting.is_mock if meeting.is_mock is not None else True,
        summary=meeting.summary,
        decisions=[DecisionItem(**d) for d in (meeting.decisions or [])],
        open_questions=[OpenQuestionItem(**q) for q in (meeting.open_questions or [])],
        actions=[ActionResponse.model_validate(a) for a in meeting.actions],
        created_at=meeting.created_at,
        updated_at=meeting.updated_at,
    )
