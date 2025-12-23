"""Job management API routes."""

from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, Form, Request
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from services.database import get_session
from models.database import Job, Model, Transcript, TranscriptSegment
from schemas.job import (
    JobCreate,
    JobResponse,
    JobStatus,
    JobUpdate,
    TranscriptResponse,
    TranscriptSegment as TranscriptSegmentSchema,
    OutputFormat,
)

# Celery import is optional - jobs can be created without workers
try:
    from workers.tasks import process_job
    CELERY_AVAILABLE = True
except ImportError:
    CELERY_AVAILABLE = False
    process_job = None

router = APIRouter()

# Initialize audit logger
try:
    import sys
    sys.path.insert(0, "/app")
    from shared.services.audit import AuditLogger
    audit_logger = AuditLogger("transcribe")
except ImportError:
    audit_logger = None


@router.post("", response_model=JobResponse, status_code=201)
async def create_job(
    request: Request,
    file: UploadFile = File(...),
    language: str = Form(default="auto"),
    translate_to: Optional[str] = Form(default=None),
    model_id: Optional[str] = Form(default=None),
    diarization_model_id: Optional[str] = Form(default=None),
    tts_model_id: Optional[str] = Form(default=None),
    enable_diarization: bool = Form(default=False),
    enable_tts: bool = Form(default=False),
    sync_tts_timing: bool = Form(default=True),
    output_formats: str = Form(default="json,srt"),
    priority: int = Form(default=5, ge=1, le=10),
    session: AsyncSession = Depends(get_session),
):
    """
    Create a new transcription job.
    
    Upload an audio or video file and configure processing options.
    """
    from config import settings
    import aiofiles
    import os
    import uuid
    import hashlib
    
    # Validate file type
    allowed_types = {
        "audio/mpeg", "audio/wav", "audio/x-wav", "audio/mp3",
        "audio/ogg", "audio/flac", "audio/m4a", "audio/aac",
        "video/mp4", "video/webm", "video/mpeg", "video/quicktime",
        "video/x-msvideo", "video/x-matroska",
    }
    
    content_type = file.content_type or ""
    if content_type not in allowed_types:
        # Try to infer from extension
        ext = os.path.splitext(file.filename or "")[1].lower()
        valid_extensions = {".mp3", ".wav", ".ogg", ".oga", ".flac", ".m4a", ".aac",
                           ".mp4", ".webm", ".mpeg", ".mov", ".avi", ".mkv"}
        if ext not in valid_extensions:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported file type. Allowed: audio (mp3, wav, ogg, flac, m4a) and video (mp4, webm, mkv, mov)",
            )
    
    # Get default model if not specified
    if not model_id:
        result = await session.execute(
            select(Model).where(
                Model.is_default == True,
                Model.model_type == "whisper",
            )
        )
        default_model = result.scalar_one_or_none()
        model_id = default_model.id if default_model else None
    
    # Generate unique file path
    file_id = str(uuid.uuid4())
    ext = os.path.splitext(file.filename or "file")[1] or ".mp3"
    upload_path = settings.upload_dir / f"{file_id}{ext}"
    
    # Save uploaded file and compute hash
    content = await file.read()
    file_hash = hashlib.sha256(content).hexdigest()
    async with aiofiles.open(upload_path, "wb") as f:
        await f.write(content)
    
    # Parse output formats
    formats = [OutputFormat(f.strip()) for f in output_formats.split(",") if f.strip()]
    
    # Calculate queue position
    result = await session.execute(
        select(func.count(Job.id)).where(
            Job.status.in_([JobStatus.PENDING, JobStatus.QUEUED, JobStatus.PROCESSING])
        )
    )
    queue_position = result.scalar() + 1
    
    # Create job record
    job = Job(
        filename=file.filename or "unknown",
        original_path=str(upload_path),
        file_size=len(content),
        language=language,
        translate_to=translate_to,
        model_id=model_id,
        diarization_model_id=diarization_model_id if enable_diarization else None,
        tts_model_id=tts_model_id if enable_tts else None,
        enable_diarization=enable_diarization,
        enable_tts=enable_tts,
        sync_tts_timing=sync_tts_timing,
        output_formats=[f.value for f in formats],
        priority=priority,
        queue_position=queue_position,
        status=JobStatus.QUEUED,
    )
    
    session.add(job)
    await session.commit()
    await session.refresh(job)
    
    # Log audit event
    if audit_logger:
        try:
            await audit_logger.log(
                session=session,
                action="job_created",
                request=request,
                job_id=job.id,
                file_hash=file_hash,
                file_name=file.filename,
                file_size_bytes=len(content),
                status="queued",
                metadata={
                    "language": language,
                    "enable_diarization": enable_diarization,
                    "enable_tts": enable_tts,
                },
            )
        except Exception:
            pass  # Don't fail job creation if audit fails
    
    # Queue the job for processing
    if CELERY_AVAILABLE and process_job:
        # Production: Use Celery
        process_job.delay(job.id)
    else:
        # Development: Use simple background tasks
        from services.background_tasks import start_job_background
        start_job_background(job.id)
    
    return JobResponse(
        id=job.id,
        filename=job.filename,
        status=job.status,
        progress=job.progress,
        language=job.language,
        model_id=job.model_id or "",
        enable_diarization=job.enable_diarization,
        enable_tts=job.enable_tts,
        sync_tts_timing=job.sync_tts_timing,
        output_formats=formats,
        priority=job.priority,
        queue_position=queue_position,
        created_at=job.created_at,
    )


@router.get("", response_model=List[JobResponse])
async def list_jobs(
    status: Optional[JobStatus] = Query(default=None),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_session),
):
    """List all jobs with optional status filter."""
    query = select(Job).order_by(Job.created_at.desc()).limit(limit).offset(offset)
    
    if status:
        query = query.where(Job.status == status)
    
    result = await session.execute(query)
    jobs = result.scalars().all()
    
    return [
        JobResponse(
            id=job.id,
            filename=job.filename,
            status=job.status,
            progress=job.progress,
            language=job.language,
            detected_language=job.detected_language,
            model_id=job.model_id or "",
            enable_diarization=job.enable_diarization,
            enable_tts=job.enable_tts,
            sync_tts_timing=job.sync_tts_timing,
            output_formats=[OutputFormat(f) for f in job.output_formats],
            priority=job.priority,
            queue_position=job.queue_position,
            created_at=job.created_at,
            started_at=job.started_at,
            completed_at=job.completed_at,
            duration=job.duration,
            error_message=job.error_message,
        )
        for job in jobs
    ]


@router.get("/{job_id}", response_model=JobResponse)
async def get_job(
    job_id: str,
    session: AsyncSession = Depends(get_session),
):
    """Get a specific job by ID."""
    result = await session.execute(select(Job).where(Job.id == job_id))
    job = result.scalar_one_or_none()
    
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    return JobResponse(
        id=job.id,
        filename=job.filename,
        status=job.status,
        progress=job.progress,
        language=job.language,
        detected_language=job.detected_language,
        model_id=job.model_id or "",
        enable_diarization=job.enable_diarization,
        enable_tts=job.enable_tts,
        sync_tts_timing=job.sync_tts_timing,
        output_formats=[OutputFormat(f) for f in job.output_formats],
        priority=job.priority,
        queue_position=job.queue_position,
        created_at=job.created_at,
        started_at=job.started_at,
        completed_at=job.completed_at,
        duration=job.duration,
        transcript_url=f"/api/jobs/{job.id}/transcript" if job.transcript_path else None,
        audio_url=f"/outputs/{job.id}/tts.wav" if job.tts_audio_path else None,
        error_message=job.error_message,
    )


@router.delete("/{job_id}", status_code=204)
async def delete_job(
    job_id: str,
    session: AsyncSession = Depends(get_session),
):
    """Delete or cancel a job."""
    import os
    
    result = await session.execute(select(Job).where(Job.id == job_id))
    job = result.scalar_one_or_none()
    
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    # Cancel if still processing
    if job.status in [JobStatus.QUEUED, JobStatus.PROCESSING, JobStatus.TRANSCRIBING]:
        try:
            from workers.tasks import celery_app
            celery_app.control.revoke(job_id, terminate=True)
        except ImportError:
            pass
        job.status = JobStatus.CANCELLED
    
    # Clean up files
    if job.original_path and os.path.exists(job.original_path):
        os.remove(job.original_path)
    if job.transcript_path and os.path.exists(job.transcript_path):
        os.remove(job.transcript_path)
    if job.tts_audio_path and os.path.exists(job.tts_audio_path):
        os.remove(job.tts_audio_path)
    
    await session.delete(job)
    await session.commit()


@router.get("/{job_id}/transcript", response_model=TranscriptResponse)
async def get_transcript(
    job_id: str,
    format: OutputFormat = Query(default=OutputFormat.JSON),
    session: AsyncSession = Depends(get_session),
):
    """Get the transcript for a completed job."""
    from fastapi.responses import PlainTextResponse
    
    result = await session.execute(
        select(Job).where(Job.id == job_id)
    )
    job = result.scalar_one_or_none()
    
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    if job.status != JobStatus.COMPLETED:
        raise HTTPException(
            status_code=400,
            detail=f"Job is not completed. Current status: {job.status.value}",
        )
    
    # Get transcript with segments
    result = await session.execute(
        select(Transcript).where(Transcript.job_id == job_id)
    )
    transcript = result.scalar_one_or_none()
    
    if not transcript:
        raise HTTPException(status_code=404, detail="Transcript not found")
    
    result = await session.execute(
        select(TranscriptSegment)
        .where(TranscriptSegment.transcript_id == transcript.id)
        .order_by(TranscriptSegment.segment_index)
    )
    segments = result.scalars().all()
    
    # Return based on format
        if format == OutputFormat.JSON:
            return TranscriptResponse(
                id=transcript.id,
                job_id=job_id,
            language=transcript.language or job.detected_language or job.language,
            duration=transcript.duration or job.duration or 0,
            segments=[
                TranscriptSegmentSchema(
                    id=seg.segment_index,
                    start=seg.start_time,
                    end=seg.end_time,
                    text=seg.text,
                    speaker=seg.speaker,
                    confidence=seg.confidence,
                    words=seg.words,
                )
                for seg in segments
            ],
            speakers=list(set(seg.speaker for seg in segments if seg.speaker)),
        )
    
    elif format == OutputFormat.SRT:
        srt_content = generate_srt(segments)
        return PlainTextResponse(content=srt_content, media_type="text/plain")
    
    elif format == OutputFormat.VTT:
        vtt_content = generate_vtt(segments)
        return PlainTextResponse(content=vtt_content, media_type="text/vtt")
    
    elif format == OutputFormat.TXT:
        txt_content = "\n".join(seg.text for seg in segments)
        return PlainTextResponse(content=txt_content, media_type="text/plain")


from pydantic import BaseModel

class SpeakerUpdate(BaseModel):
    """Schema for updating speaker names."""
    speaker_map: dict


@router.patch("/{job_id}/speakers")
async def update_speakers(
    job_id: str,
    update: SpeakerUpdate,
    session: AsyncSession = Depends(get_session),
):
    """
    Update speaker names in a transcript.
    
    Accepts a mapping of old speaker names to new names.
    Example: {"SPEAKER_00": "Alice", "SPEAKER_01": "Bob"}
    """
    # Get the job
    result = await session.execute(select(Job).where(Job.id == job_id))
    job = result.scalar_one_or_none()
    
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    if job.status != JobStatus.COMPLETED:
        raise HTTPException(
            status_code=400,
            detail="Can only update speakers for completed jobs",
        )
    
    # Get transcript
    result = await session.execute(
        select(Transcript).where(Transcript.job_id == job_id)
    )
    transcript = result.scalar_one_or_none()
    
    if not transcript:
        raise HTTPException(status_code=404, detail="Transcript not found")
    
    # Get and update segments
    result = await session.execute(
        select(TranscriptSegment)
        .where(TranscriptSegment.transcript_id == transcript.id)
    )
    segments = result.scalars().all()
    
    updated_count = 0
    for segment in segments:
        if segment.speaker in update.speaker_map:
            segment.speaker = update.speaker_map[segment.speaker]
            updated_count += 1
    
    await session.commit()
    
    return {
        "message": "Speakers updated",
        "job_id": job_id,
        "segments_updated": updated_count,
        "speaker_map": update.speaker_map,
    }


def generate_srt(segments: List[TranscriptSegment]) -> str:
    """Generate SRT subtitle format."""
    lines = []
    for i, seg in enumerate(segments, 1):
        start = format_srt_time(seg.start_time)
        end = format_srt_time(seg.end_time)
        text = seg.text
        if seg.speaker:
            text = f"[{seg.speaker}] {text}"
        lines.append(f"{i}\n{start} --> {end}\n{text}\n")
    return "\n".join(lines)


def generate_vtt(segments: List[TranscriptSegment]) -> str:
    """Generate WebVTT subtitle format."""
    lines = ["WEBVTT\n"]
    for i, seg in enumerate(segments, 1):
        start = format_vtt_time(seg.start_time)
        end = format_vtt_time(seg.end_time)
        text = seg.text
        if seg.speaker:
            text = f"<v {seg.speaker}>{text}"
        lines.append(f"\n{i}\n{start} --> {end}\n{text}")
    return "\n".join(lines)


def format_srt_time(seconds: float) -> str:
    """Format time for SRT (HH:MM:SS,mmm)."""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds % 1) * 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def format_vtt_time(seconds: float) -> str:
    """Format time for VTT (HH:MM:SS.mmm)."""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds % 1) * 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}.{millis:03d}"
