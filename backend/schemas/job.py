"""Job-related Pydantic schemas."""

from datetime import datetime
from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field


class JobStatus(str, Enum):
    """Job processing status."""

    PENDING = "pending"
    QUEUED = "queued"
    PROCESSING = "processing"
    TRANSCRIBING = "transcribing"
    DIARIZING = "diarizing"
    SYNTHESIZING = "synthesizing"
    SYNCING = "syncing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class OutputFormat(str, Enum):
    """Available output formats."""

    JSON = "json"
    SRT = "srt"
    VTT = "vtt"
    TXT = "txt"


class JobCreate(BaseModel):
    """Schema for creating a new transcription job."""

    filename: str = Field(..., description="Original filename")
    language: str = Field(default="auto", description="Source language or 'auto' for detection")
    translate_to: Optional[str] = Field(default=None, description="Target language for translation (None = no translation)")
    model_id: Optional[str] = Field(default=None, description="Whisper model ID to use")
    enable_diarization: bool = Field(default=False, description="Enable speaker diarization")
    enable_tts: bool = Field(default=False, description="Enable TTS synthesis")
    sync_tts_timing: bool = Field(
        default=True,
        description="Sync TTS output to original audio timing",
    )
    output_formats: List[OutputFormat] = Field(
        default=[OutputFormat.JSON, OutputFormat.SRT],
        description="Desired output formats",
    )
    priority: int = Field(default=5, ge=1, le=10, description="Job priority (1=highest, 10=lowest)")


class TranscriptSegment(BaseModel):
    """A single segment of transcribed text."""

    id: int = Field(..., description="Segment index")
    start: float = Field(..., description="Start time in seconds")
    end: float = Field(..., description="End time in seconds")
    text: str = Field(..., description="Transcribed text")
    speaker: Optional[str] = Field(default=None, description="Speaker label if diarization enabled")
    confidence: Optional[float] = Field(default=None, description="Confidence score")
    words: Optional[List[dict]] = Field(default=None, description="Word-level timestamps")


class TranscriptResponse(BaseModel):
    """Complete transcript response."""

    id: str
    job_id: str
    language: str
    duration: float
    segments: List[TranscriptSegment]
    speakers: Optional[List[str]] = None


class JobResponse(BaseModel):
    """Schema for job response."""

    id: str = Field(..., description="Unique job ID")
    filename: str
    status: JobStatus
    progress: float = Field(default=0.0, ge=0, le=100, description="Progress percentage")
    language: str
    detected_language: Optional[str] = None
    translate_to: Optional[str] = None
    model_id: str
    enable_diarization: bool
    enable_tts: bool
    sync_tts_timing: bool
    output_formats: List[OutputFormat]
    priority: int

    # Timestamps
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    # Results
    duration: Optional[float] = Field(default=None, description="Media duration in seconds")
    transcript_url: Optional[str] = None
    audio_url: Optional[str] = None
    error_message: Optional[str] = None

    # Queue info
    queue_position: Optional[int] = None

    class Config:
        from_attributes = True


class JobUpdate(BaseModel):
    """Schema for updating job status (internal use)."""

    status: Optional[JobStatus] = None
    progress: Optional[float] = None
    detected_language: Optional[str] = None
    duration: Optional[float] = None
    transcript_url: Optional[str] = None
    audio_url: Optional[str] = None
    error_message: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
