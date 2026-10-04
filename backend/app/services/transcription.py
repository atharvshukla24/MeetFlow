"""Transcription service interface and mock implementation."""
import os
import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Tuple
from fastapi import HTTPException, status
from app.core.config import settings

logger = logging.getLogger("meetflow.transcription")

DEFAULT_MOCK_TRANSCRIPT = """[SYNTHETIC SAMPLE TRANSCRIPT — DEMO ONLY]
[00:00:02] Sarah: Good morning everyone, let's begin our project sync. Atharv, could you give us an update on the backend API implementation?
[00:00:15] Atharv: Hi Sarah. The core database models and routing are in place. I will complete the backend API by Friday.
[00:00:30] Sarah: Thanks Atharv, that sounds great. Atharv, please also prepare an email summary for the engineering team once the tests pass.
[00:00:45] Atharv: Will do, I'll draft that email as soon as the test suite is green.
[00:00:58] Sarah: Next item: we explicitly decided to deploy the beta release to the staging environment next Monday at 10 AM.
[00:01:14] Bob: Quick question regarding the database—did we finalize whether to run the indexing migration during off-peak hours?
[00:01:28] Sarah: That remains an open question. Let's discuss and finalize that in Thursday's architecture review.
[00:01:40] Atharv: Sounds like a plan. Thanks everyone."""


class BaseTranscriptionService(ABC):
    """Abstract base class defining the speech-to-text service contract."""

    provider_name: str = "base"

    @abstractmethod
    async def transcribe(self, audio_file_path: str) -> Tuple[str, bool]:
        """
        Transcribe the audio recording at audio_file_path.

        Returns:
            Tuple of (transcript_text, is_mock)
        """
        pass


class MockTranscriptionService(BaseTranscriptionService):
    """
    Deterministic mock transcription provider for local development, testing, and demos.
    Generates structured synthetic dialogue with timestamps without external API calls.
    """

    provider_name: str = "mock"

    def __init__(self, sample_transcript_path: str = "sample_data/sample_meeting_transcript.txt"):
        self.sample_transcript_path = sample_transcript_path

    async def transcribe(self, audio_file_path: str) -> Tuple[str, bool]:
        """Load synthetic meeting dialogue and ensure it is visibly labelled as mock content."""
        transcript_text = DEFAULT_MOCK_TRANSCRIPT

        # Attempt to load from sample_data file if present
        try:
            path = Path(self.sample_transcript_path)
            if not path.is_absolute():
                # Resolve relative to project root (2 levels up from backend/app/services)
                project_root = Path(__file__).resolve().parent.parent.parent.parent
                path = project_root / self.sample_transcript_path

            if path.exists():
                with open(path, "r", encoding="utf-8") as f:
                    content = f.read().strip()
                if content:
                    transcript_text = content
        except Exception as exc:
            logger.warning(f"Could not load sample transcript file from {self.sample_transcript_path}: {exc}")

        # Ensure synthetic banner is present
        banner = "[SYNTHETIC SAMPLE TRANSCRIPT — DEMO ONLY]"
        if not transcript_text.startswith(banner):
            transcript_text = f"{banner}\n{transcript_text}"

        return transcript_text, True


AUDIO_MIME_TYPES = {
    ".wav": "audio/wav",
    ".mp3": "audio/mp3",
    ".m4a": "audio/m4a",
    ".aac": "audio/aac",
    ".ogg": "audio/ogg",
    ".flac": "audio/flac",
}


def format_seconds(secs_val) -> str:
    """Format seconds (float or string like '12.4s') into [HH:MM:SS]."""
    try:
        s = float(str(secs_val).rstrip("s"))
        h = int(s // 3600)
        m = int((s % 3600) // 60)
        sec = int(s % 60)
        return f"[{h:02d}:{m:02d}:{sec:02d}]"
    except Exception:
        return ""


def format_gemini_transcript(response) -> str:
    """
    Format Gemini transcription response preserving speaker labels and timestamps if present.
    If speaker annotations and timestamps exist, groups into turns:
    [HH:MM:SS] Speaker: text...
    Otherwise falls back to response.text.
    Never invents timestamps, speakers, or dialogue.
    """
    turns = []
    current_speaker = None
    current_start = None
    current_words = []
    prev_end = None

    for candidate in getattr(response, "candidates", []) or []:
        content = getattr(candidate, "content", None)
        if not content:
            continue
        for part in getattr(content, "parts", []) or []:
            transcription = getattr(part, "audio_transcription", None)
            if not transcription:
                continue
            speaker = getattr(transcription, "speaker_label", None) or ""
            words_info = getattr(transcription, "words", None) or []
            for w in words_info:
                word_text = getattr(w, "word", None) or ""
                start_offset = getattr(w, "start_offset", None)
                end_offset = getattr(w, "end_offset", None)
                if not word_text:
                    continue

                start_s = None
                if start_offset is not None:
                    try:
                        start_s = float(str(start_offset).rstrip("s"))
                    except Exception:
                        pass

                should_break = False
                if current_speaker is not None and speaker != current_speaker:
                    should_break = True
                elif (
                    current_words
                    and prev_end is not None
                    and start_s is not None
                    and (start_s - prev_end) >= 1.5
                    and current_words[-1].endswith((".", "!", "?"))
                ):
                    should_break = True

                if should_break:
                    time_str = format_seconds(current_start) if current_start is not None else ""
                    speaker_str = f"{current_speaker}: " if current_speaker else ""
                    body_str = " ".join(current_words)
                    prefix = f"{time_str} " if time_str else ""
                    turns.append(f"{prefix}{speaker_str}{body_str}".strip())
                    current_words = []
                    current_start = start_offset
                    current_speaker = speaker
                elif current_speaker is None:
                    current_speaker = speaker
                    current_start = start_offset

                current_words.append(word_text)
                if end_offset is not None:
                    try:
                        prev_end = float(str(end_offset).rstrip("s"))
                    except Exception:
                        pass

    if current_words:
        time_str = format_seconds(current_start) if current_start is not None else ""
        speaker_str = f"{current_speaker}: " if current_speaker else ""
        body_str = " ".join(current_words)
        prefix = f"{time_str} " if time_str else ""
        turns.append(f"{prefix}{speaker_str}{body_str}".strip())

    if turns:
        return "\n".join(turns)

    if hasattr(response, "text") and response.text and response.text.strip():
        return response.text.strip()

    return ""


class GeminiTranscriptionService(BaseTranscriptionService):
    """
    Real audio speech-to-text provider using Google's dedicated Gemini transcription model.
    Sends uploaded audio file from backend storage to Google's Gemini API (default: gemini-3.5-transcribe).
    Supports automatic language detection and speaker diarization with word timestamps.
    """

    provider_name: str = "gemini"

    def __init__(self, api_key: str = None, model_name: str = None):
        self.api_key = (api_key if api_key is not None else getattr(settings, "GEMINI_API_KEY", "")).strip()
        configured_model = (model_name if model_name is not None else getattr(settings, "GEMINI_TRANSCRIPTION_MODEL", "gemini-3.5-transcribe")).strip()
        self.model_name = configured_model if configured_model else "gemini-3.5-transcribe"

    async def transcribe(self, audio_file_path: str) -> Tuple[str, bool]:
        """
        Transcribe the stored audio file using Gemini API.
        Fails fast if unconfigured or on API error; never silently falls back to mock.

        Returns:
            Tuple of (transcript_text, is_mock=False)
        """
        if not self.api_key:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Gemini API key is not configured. Set GEMINI_API_KEY in the backend environment.",
            )

        if not os.path.exists(audio_file_path):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Audio file '{audio_file_path}' not found on server storage.",
            )

        ext = Path(audio_file_path).suffix.lower()
        mime_type = AUDIO_MIME_TYPES.get(ext, "audio/wav")

        try:
            from google import genai
            from google.genai import types

            client = genai.Client(api_key=self.api_key)
            config = types.GenerateContentConfig(
                audio_transcription_config=types.AudioTranscriptionConfig(
                    diarization=True,
                    word_timestamp=True,
                )
            )

            uploaded_file = None
            try:
                # Upload audio file to Google GenAI Files API or pass inline Part
                if hasattr(client, "aio") and hasattr(client.aio, "files") and hasattr(client.aio.files, "upload"):
                    try:
                        uploaded_file = await client.aio.files.upload(
                            file=audio_file_path,
                            config=types.UploadFileConfig(mime_type=mime_type),
                        )
                        audio_input = uploaded_file
                    except Exception as upload_err:
                        logger.debug(f"Direct Files API upload failed or bypassed: {upload_err}")
                        with open(audio_file_path, "rb") as af:
                            audio_bytes = af.read()
                        audio_input = types.Part.from_bytes(data=audio_bytes, mime_type=mime_type)

                    response = await client.aio.models.generate_content(
                        model=self.model_name,
                        contents=[audio_input],
                        config=config,
                    )
                else:
                    try:
                        uploaded_file = client.files.upload(
                            file=audio_file_path,
                            config=types.UploadFileConfig(mime_type=mime_type),
                        )
                        audio_input = uploaded_file
                    except Exception as upload_err:
                        logger.debug(f"Direct Files API upload failed or bypassed: {upload_err}")
                        with open(audio_file_path, "rb") as af:
                            audio_bytes = af.read()
                        audio_input = types.Part.from_bytes(data=audio_bytes, mime_type=mime_type)

                    response = client.models.generate_content(
                        model=self.model_name,
                        contents=[audio_input],
                        config=config,
                    )
            finally:
                if uploaded_file and hasattr(uploaded_file, "name"):
                    try:
                        if hasattr(client, "aio") and hasattr(client.aio, "files"):
                            await client.aio.files.delete(name=uploaded_file.name)
                        else:
                            client.files.delete(name=uploaded_file.name)
                    except Exception as del_err:
                        logger.debug(f"Failed to delete temporary audio file {uploaded_file.name}: {del_err}")

        except HTTPException:
            raise
        except Exception as exc:
            logger.exception(f"Gemini transcription API request failed: {exc}")
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Gemini transcription API request failed: {str(exc)}",
            )

        transcript_text = format_gemini_transcript(response)
        if not transcript_text or not transcript_text.strip():
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Gemini transcription API returned an empty or unparseable transcript.",
            )

        return transcript_text.strip(), False


def get_transcription_service() -> BaseTranscriptionService:
    """
    Service factory resolving the configured transcription provider.
    Strictly checks TRANSCRIPTION_PROVIDER and never silently falls back to mock.
    """
    provider = getattr(settings, "TRANSCRIPTION_PROVIDER", "mock").lower()

    if provider == "mock":
        return MockTranscriptionService()
    elif provider in ("gemini", "google"):
        return GeminiTranscriptionService()

    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail=f"Transcription provider '{provider}' is not supported.",
    )
