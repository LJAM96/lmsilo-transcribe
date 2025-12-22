"""
Application configuration using Pydantic Settings.

Environment variables are loaded from .env file or system environment.
"""

from pathlib import Path
from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, computed_field


class Settings(BaseSettings):
    """Application settings with environment variable support."""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Application
    app_name: str = "STT Server"
    debug: bool = False

    # Database
    database_url: str = Field(
        default="postgresql+asyncpg://stt:stt@localhost:5432/stt",
        description="PostgreSQL connection URL",
    )

    # Redis
    redis_url: str = Field(
        default="redis://localhost:6379/0",
        description="Redis connection URL for Celery broker",
    )

    # File Storage
    upload_dir: Path = Field(
        default=Path("./uploads"),
        description="Directory for uploaded files",
    )
    output_dir: Path = Field(
        default=Path("./outputs"),
        description="Directory for processed outputs",
    )
    model_dir: Path = Field(
        default=Path("./models"),
        description="Directory for ML models",
    )
    max_upload_size_mb: int = Field(
        default=500,
        description="Maximum upload file size in MB",
    )

    # CORS - stored as comma-separated string
    cors_origins_str: str = Field(
        default="http://localhost:3000,http://localhost:5173",
        alias="CORS_ORIGINS",
        description="Allowed CORS origins (comma-separated)",
    )
    
    @computed_field
    @property
    def cors_origins(self) -> List[str]:
        """Parse comma-separated CORS origins into a list."""
        return [origin.strip() for origin in self.cors_origins_str.split(",") if origin.strip()]

    # ML Models
    default_whisper_model: str = Field(
        default="large-v3",
        description="Default Whisper model size",
    )
    default_language: str = Field(
        default="auto",
        description="Default transcription language (auto for detection)",
    )

    # HuggingFace (required for pyannote)
    hf_token: str = Field(
        default="",
        description="HuggingFace access token for pyannote models",
    )

    # Processing
    device: str = Field(
        default="cpu",
        description="Compute device: cuda, cpu, or auto",
    )
    compute_type: str = Field(
        default="int8",
        description="Compute type: float16, int8, or float32",
    )
    max_concurrent_jobs: int = Field(
        default=2,
        description="Maximum concurrent transcription jobs",
    )


settings = Settings()

# Ensure directories exist
settings.upload_dir.mkdir(parents=True, exist_ok=True)
settings.output_dir.mkdir(parents=True, exist_ok=True)
settings.model_dir.mkdir(parents=True, exist_ok=True)
