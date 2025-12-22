"""Database models using SQLAlchemy ORM."""

from datetime import datetime
from typing import Optional, List
import uuid
from sqlalchemy import (
    Column,
    String,
    Text,
    Float,
    Integer,
    Boolean,
    DateTime,
    Enum as SQLEnum,
    JSON,
    ForeignKey,
)
from sqlalchemy.orm import relationship, DeclarativeBase
from sqlalchemy.dialects.postgresql import UUID

from schemas.job import JobStatus, OutputFormat
from schemas.model import ModelType, ModelEngine, ModelSource


class Base(DeclarativeBase):
    """Base class for all models."""

    pass


def generate_uuid():
    return str(uuid.uuid4())


class JobBatch(Base):
    """Batch of multiple jobs for bulk upload."""

    __tablename__ = "job_batches"

    id = Column(String, primary_key=True, default=generate_uuid)
    
    # Batch info
    name = Column(String, nullable=False)
    total_files = Column(Integer, default=0)
    completed_files = Column(Integer, default=0)
    failed_files = Column(Integer, default=0)
    
    # Status
    status = Column(SQLEnum(JobStatus), default=JobStatus.PENDING)
    progress = Column(Float, default=0.0)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime)
    
    # Relationships
    jobs = relationship("Job", back_populates="batch")


class Job(Base):
    """Transcription job model."""

    __tablename__ = "jobs"

    id = Column(String, primary_key=True, default=generate_uuid)
    
    # Batch reference (optional)
    batch_id = Column(String, ForeignKey("job_batches.id"), nullable=True)
    
    # File info
    filename = Column(String, nullable=False)
    original_path = Column(String, nullable=False)
    file_size = Column(Integer)
    duration = Column(Float)  # Media duration in seconds
    
    # Processing options
    language = Column(String, default="auto")
    detected_language = Column(String)
    translate_to = Column(String)  # Target language for translation (None = no translation)
    model_id = Column(String, ForeignKey("models.id"))
    diarization_model_id = Column(String, ForeignKey("models.id"), nullable=True)
    tts_model_id = Column(String, ForeignKey("models.id"), nullable=True)
    
    enable_diarization = Column(Boolean, default=False)
    enable_tts = Column(Boolean, default=False)
    sync_tts_timing = Column(Boolean, default=True)
    output_formats = Column(JSON, default=["json", "srt"])
    
    # Queue management
    priority = Column(Integer, default=5)
    queue_position = Column(Integer)
    
    # Status tracking
    status = Column(SQLEnum(JobStatus), default=JobStatus.PENDING)
    progress = Column(Float, default=0.0)
    current_stage = Column(String)  # e.g., "transcribing", "diarizing"
    error_message = Column(Text)
    
    # Output paths
    transcript_path = Column(String)
    tts_audio_path = Column(String)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    started_at = Column(DateTime)
    completed_at = Column(DateTime)
    
    # Relationships
    batch = relationship("JobBatch", back_populates="jobs")
    stt_model = relationship("Model", foreign_keys=[model_id])
    diarization_model = relationship("Model", foreign_keys=[diarization_model_id])
    tts_model = relationship("Model", foreign_keys=[tts_model_id])
    transcript = relationship("Transcript", back_populates="job", uselist=False)


class Model(Base):
    """ML model configuration."""

    __tablename__ = "models"

    id = Column(String, primary_key=True, default=generate_uuid)
    
    # Identity
    name = Column(String, nullable=False)
    model_type = Column(SQLEnum(ModelType), nullable=False)
    engine = Column(SQLEnum(ModelEngine), nullable=False)
    
    # Source
    source = Column(SQLEnum(ModelSource), default=ModelSource.HUGGINGFACE)
    model_id = Column(String, nullable=False)  # HF repo, path, or URL
    revision = Column(String)
    
    # Configuration
    info = Column(JSON, default={})
    compute_type = Column(String)
    device = Column(String)
    is_default = Column(Boolean, default=False)
    
    # Status
    is_downloaded = Column(Boolean, default=False)
    local_path = Column(String)
    download_progress = Column(Float)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    last_used_at = Column(DateTime)


class Transcript(Base):
    """Stored transcript with segments."""

    __tablename__ = "transcripts"

    id = Column(String, primary_key=True, default=generate_uuid)
    job_id = Column(String, ForeignKey("jobs.id"), nullable=False)
    
    # Metadata
    language = Column(String)
    duration = Column(Float)
    word_count = Column(Integer)
    speaker_count = Column(Integer)
    
    # Full text
    full_text = Column(Text)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    job = relationship("Job", back_populates="transcript")
    segments = relationship("TranscriptSegment", back_populates="transcript", order_by="TranscriptSegment.start_time")


class TranscriptSegment(Base):
    """Individual transcript segment with timing."""

    __tablename__ = "transcript_segments"

    id = Column(String, primary_key=True, default=generate_uuid)
    transcript_id = Column(String, ForeignKey("transcripts.id"), nullable=False)
    
    # Segment data
    segment_index = Column(Integer, nullable=False)
    start_time = Column(Float, nullable=False)
    end_time = Column(Float, nullable=False)
    text = Column(Text, nullable=False)
    
    # Speaker info (if diarization enabled)
    speaker = Column(String)
    speaker_confidence = Column(Float)
    
    # Word-level data (JSON array)
    words = Column(JSON)  # [{word, start, end, confidence}, ...]
    
    # Confidence
    confidence = Column(Float)
    
    # Relationship
    transcript = relationship("Transcript", back_populates="segments")


class TTSOutput(Base):
    """TTS synthesized audio output."""

    __tablename__ = "tts_outputs"

    id = Column(String, primary_key=True, default=generate_uuid)
    job_id = Column(String, ForeignKey("jobs.id"), nullable=False)
    
    # Audio info
    audio_path = Column(String, nullable=False)
    duration = Column(Float)
    sample_rate = Column(Integer)
    format = Column(String, default="wav")
    
    # Sync info
    is_timing_synced = Column(Boolean, default=False)
    original_duration = Column(Float)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
