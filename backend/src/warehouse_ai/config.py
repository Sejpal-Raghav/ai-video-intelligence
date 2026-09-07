"""Runtime configuration using pydantic-settings matching Blueprint Section 7."""

from __future__ import annotations

import os
import shutil
from enum import Enum
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppEnv(str, Enum):
    DEVELOPMENT = "development"
    TEST = "test"
    DEMO = "demo"


class ModelBackend(str, Enum):
    ULTRALYTICS = "ultralytics"
    REPLAY = "replay"


class ModelDevice(str, Enum):
    AUTO = "auto"
    CPU = "cpu"
    CUDA_0 = "cuda:0"


# Determine repository root (3 levels up from this file: backend/src/warehouse_ai/config.py -> root)
REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    APP_ENV: AppEnv = AppEnv.DEVELOPMENT
    API_HOST: str = "127.0.0.1"
    API_PORT: int = Field(default=8000, ge=1, le=65535)
    WEB_ORIGIN: str = "http://127.0.0.1:3000"
    DATABASE_URL: str = "sqlite:///./storage/app.db"
    STORAGE_ROOT: str = "./storage"

    FFMPEG_PATH: str = "ffmpeg"
    FFPROBE_PATH: str = "ffprobe"

    MODEL_BACKEND: ModelBackend = ModelBackend.ULTRALYTICS
    MODEL_PATH: str = "./models/warehouse-v1.pt"
    MODEL_DEVICE: ModelDevice = ModelDevice.AUTO

    INFERENCE_FPS: int = Field(default=10, ge=1, le=60)
    VERIFY_ENABLED: bool = True
    VERIFY_FPS: int = Field(default=25, ge=1, le=60)
    VERIFY_PADDING_MS: int = Field(default=2000, ge=0)

    MAX_UPLOAD_BYTES: int = Field(default=524288000, ge=1)
    MAX_VIDEO_SECONDS: int = Field(default=600, ge=1)
    MAX_VIDEO_WIDTH: int = Field(default=3840, ge=1)
    MAX_VIDEO_HEIGHT: int = Field(default=2160, ge=1)

    MEDIA_RETENTION_HOURS: int = Field(default=72, ge=1)
    RETENTION_SCAN_SECONDS: int = Field(default=600, ge=10)

    JOB_LEASE_SECONDS: int = Field(default=60, ge=10)
    JOB_HEARTBEAT_SECONDS: int = Field(default=10, ge=1)
    JOB_MAX_ATTEMPTS: int = Field(default=2, ge=1, le=5)

    LOG_LEVEL: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"

    ALLOW_REMOTE_BIND: bool = False
    ALLOW_DIRTY_RUN: bool = False

    ASSISTANT_ENABLED: bool = False
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = ""
    OPENAI_STORE: bool = False

    # Resolved absolute paths computed at validation time
    storage_root_path: Path = Field(default_factory=lambda: REPO_ROOT / "storage")
    ffmpeg_bin: Path | str = Field(default="ffmpeg")
    ffprobe_bin: Path | str = Field(default="ffprobe")
    model_file_path: Path = Field(default_factory=lambda: REPO_ROOT / "models" / "warehouse-v1.pt")

    @model_validator(mode="after")
    def validate_and_resolve_paths(self) -> Settings:
        # Check API_HOST constraint for non-development environments
        if self.APP_ENV != AppEnv.DEVELOPMENT and self.API_HOST == "0.0.0.0" and not self.ALLOW_REMOTE_BIND:
            raise ValueError(
                "Production/demo startup refuses API_HOST=0.0.0.0 unless ALLOW_REMOTE_BIND=true"
            )

        # Storage root path resolution
        raw_storage = Path(self.STORAGE_ROOT)
        if not raw_storage.is_absolute():
            resolved_storage = (REPO_ROOT / raw_storage).resolve()
        else:
            resolved_storage = raw_storage.resolve()

        # Storage root must remain a descendant of REPO_ROOT or be specifically configured
        self.storage_root_path = resolved_storage

        # Resolve FFMPEG / FFPROBE executables
        ffmpeg_which = shutil.which(self.FFMPEG_PATH)
        self.ffmpeg_bin = Path(ffmpeg_which).resolve() if ffmpeg_which else self.FFMPEG_PATH

        ffprobe_which = shutil.which(self.FFPROBE_PATH)
        self.ffprobe_bin = Path(ffprobe_which).resolve() if ffprobe_which else self.FFPROBE_PATH

        # Model path resolution
        raw_model = Path(self.MODEL_PATH)
        if not raw_model.is_absolute():
            self.model_file_path = (REPO_ROOT / raw_model).resolve()
        else:
            self.model_file_path = raw_model.resolve()

        # Assistant validation
        if self.ASSISTANT_ENABLED and not self.OPENAI_API_KEY:
            raise ValueError("OPENAI_API_KEY is required when ASSISTANT_ENABLED=true")

        return self


# Global cached settings instance
_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
