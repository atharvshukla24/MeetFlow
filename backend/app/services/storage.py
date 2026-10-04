"""Audio file storage, validation, and security service."""
import os
import re
import logging
from pathlib import Path
from typing import Tuple
from fastapi import UploadFile, HTTPException, status
from app.core.config import settings

logger = logging.getLogger("meetflow.storage")

# Magic byte signatures for audio formats
AUDIO_MAGIC_SIGNATURES = {
    ".wav": lambda b: b.startswith(b"RIFF") and len(b) >= 12 and b[8:12] == b"WAVE",
    ".mp3": lambda b: b.startswith(b"ID3") or (
        len(b) >= 2 and b[0] == 0xFF and (b[1] & 0xE0) == 0xE0
    ),
    ".ogg": lambda b: b.startswith(b"OggS"),
    ".flac": lambda b: b.startswith(b"fLaC"),
    ".m4a": lambda b: len(b) >= 12 and b[4:8] == b"ftyp",
    ".aac": lambda b: (
        b.startswith(b"ID3") or (len(b) >= 2 and b[0] == 0xFF and (b[1] & 0xF0) == 0xF0)
    ),
}


def is_safe_subpath(parent: Path, child: Path) -> bool:
    """Check if child path is safely contained within parent directory without escaping."""
    try:
        resolved_parent = parent.resolve()
        resolved_child = child.resolve()
        if hasattr(resolved_child, "is_relative_to"):
            return resolved_child.is_relative_to(resolved_parent)
        resolved_child.relative_to(resolved_parent)
        return True
    except (ValueError, RuntimeError):
        return False


def sanitize_filename(filename: str) -> str:
    """Sanitize client-provided filename to prevent path traversal or special characters."""
    base_name = os.path.basename(filename)
    stem, ext = os.path.splitext(base_name)
    sanitized_stem = re.sub(r"[^a-zA-Z0-9_\-]", "_", stem)[:32]
    sanitized_stem = sanitized_stem.strip("_") or "audio"
    return f"{sanitized_stem}{ext.lower()}"


def validate_audio_headers(header_bytes: bytes, extension: str) -> bool:
    """Validate that initial file bytes match the audio signature for the given extension."""
    validator = AUDIO_MAGIC_SIGNATURES.get(extension.lower())
    if not validator:
        return False
    return validator(header_bytes)


async def save_uploaded_audio(
    upload_file: UploadFile,
    meeting_id: str,
) -> Tuple[str, str, int]:
    """
    Validate and save uploaded audio file using read-time chunk streaming.
    Enforces extension check, audio header magic-byte verification, and 50 MB limit.
    Deletes any partial file on error.

    Returns:
        Tuple of (saved_file_path_str, sanitized_display_filename, total_bytes)
    """
    original_filename = upload_file.filename or "uploaded_audio.wav"
    _, ext = os.path.splitext(original_filename)
    ext_lower = ext.lower()

    # 1. Primary check: Extension validation
    if ext_lower not in settings.ALLOWED_AUDIO_EXTENSIONS:
        allowed = ", ".join(settings.ALLOWED_AUDIO_EXTENSIONS)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file extension '{ext}'. Allowed extensions: {allowed}",
        )

    # 2. Prepare upload directory
    upload_dir = Path(settings.UPLOAD_DIR).resolve()
    upload_dir.mkdir(parents=True, exist_ok=True)

    sanitized_original = sanitize_filename(original_filename)
    server_filename = f"{meeting_id}_{sanitized_original}"
    target_path = upload_dir / server_filename

    # Verify path containment
    if not is_safe_subpath(upload_dir, target_path):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid filename path traversal attempt detected.",
        )

    total_bytes = 0
    header_verified = False
    chunk_size = 64 * 1024  # 64 KB chunks

    try:
        with open(target_path, "wb") as out_file:
            while True:
                chunk = await upload_file.read(chunk_size)
                if not chunk:
                    break

                # 3. Magic-byte verification on the very first chunk
                if not header_verified:
                    if not validate_audio_headers(chunk[:64], ext_lower):
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Invalid audio file format. File content does not match audio signature.",
                        )
                    header_verified = True

                total_bytes += len(chunk)

                # 4. Read-time size enforcement (50 MB)
                if total_bytes > settings.MAX_UPLOAD_SIZE_BYTES:
                    raise HTTPException(
                        status_code=getattr(status, "HTTP_413_CONTENT_TOO_LARGE", 413),
                        detail="File exceeds maximum allowed upload size of 50 MB.",
                    )

                out_file.write(chunk)

        # 5. Check empty file
        if total_bytes == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Uploaded file is empty.",
            )

    except Exception:
        # Clean up any partial or invalid file from disk on failure
        if target_path.exists():
            try:
                target_path.unlink()
            except OSError as cleanup_err:
                logger.error(f"Failed to delete partial file {target_path}: {cleanup_err}")
        raise

    return str(target_path), sanitized_original, total_bytes


def delete_stored_file(file_path_str: str) -> bool:
    """Safely delete a stored file from disk if it exists."""
    try:
        path = Path(file_path_str).resolve()
        upload_dir = Path(settings.UPLOAD_DIR).resolve()
        if is_safe_subpath(upload_dir, path) and path.exists():
            path.unlink()
            return True
    except Exception as exc:
        logger.error(f"Error deleting file {file_path_str}: {exc}")
    return False
