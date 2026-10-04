"""Application configuration settings using pydantic-settings."""
from typing import List, Union
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
import json


from pathlib import Path

# Resolve project root directory reliably regardless of uvicorn launch directory
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
ROOT_ENV_FILE = PROJECT_ROOT / ".env"
DEFAULT_DB_FILE = (PROJECT_ROOT / "meetflow.db").as_posix()
DEFAULT_UPLOAD_DIR = str(PROJECT_ROOT / "uploads")


class Settings(BaseSettings):
    PROJECT_NAME: str = "MeetFlow API"
    VERSION: str = "0.1.0"
    API_V1_STR: str = "/api/v1"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True

    # SQLite database URL (defaults to absolute project root path)
    DATABASE_URL: str = f"sqlite:///{DEFAULT_DB_FILE}"

    # CORS origins
    CORS_ORIGINS: Union[List[str], str] = [
        "http://localhost:3000",
        "http://localhost:5173",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
    ]

    # File storage configuration (defaults to absolute project root path)
    UPLOAD_DIR: str = DEFAULT_UPLOAD_DIR
    MAX_UPLOAD_SIZE_BYTES: int = 50 * 1024 * 1024  # 50 MB
    ALLOWED_AUDIO_EXTENSIONS: List[str] = [".wav", ".mp3", ".m4a", ".aac", ".ogg", ".flac"]

    # Transcription provider configuration
    TRANSCRIPTION_PROVIDER: str = "gemini"
    GEMINI_TRANSCRIPTION_MODEL: str = "gemini-3.5-transcribe"

    # Workflow extraction provider configuration
    EXTRACTION_PROVIDER: str = "gemma"

    # Action execution provider configuration
    EXECUTION_PROVIDER: str = "mock"

    # AI Configuration (Gemini API for transcription and Gemma analysis)
    GEMINI_API_KEY: str = ""
    GEMMA_MODEL: str = "gemma-4-26b-a4b-it"
    GEMINI_MODEL_ID: str = "gemma-4-26b-a4b-it"

    @field_validator("DATABASE_URL", mode="before")
    @classmethod
    def resolve_db_url(cls, v: str) -> str:
        if isinstance(v, str) and v.startswith("sqlite:///./"):
            rel_part = v.replace("sqlite:///./", "")
            return f"sqlite:///{(PROJECT_ROOT / rel_part).as_posix()}"
        return v

    @field_validator("UPLOAD_DIR", mode="before")
    @classmethod
    def resolve_upload_dir(cls, v: str) -> str:
        if isinstance(v, str) and (v.startswith("./") or v == "uploads"):
            rel_part = v.lstrip("./")
            return str(PROJECT_ROOT / rel_part)
        return v

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, str):
            if v.startswith("[") and v.endswith("]"):
                try:
                    return json.loads(v)
                except Exception:
                    pass
            return [i.strip() for i in v.split(",") if i.strip()]
        return v

    model_config = SettingsConfigDict(
        env_file=[str(ROOT_ENV_FILE), ".env"],
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )


settings = Settings()
