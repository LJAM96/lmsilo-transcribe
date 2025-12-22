"""File management API routes."""

from pathlib import Path
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import aiofiles

from services.database import get_session
from models.database import Job
from config import settings

router = APIRouter()


@router.get("/{job_id}/original")
async def get_original_file(
    job_id: str,
    session: AsyncSession = Depends(get_session),
):
    """
    Stream the original uploaded file.
    """
    result = await session.execute(select(Job).where(Job.id == job_id))
    job = result.scalar_one_or_none()
    
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    if not job.original_path:
        raise HTTPException(status_code=404, detail="Original file not found")
    
    file_path = Path(job.original_path)
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File no longer exists")
    
    # Determine content type
    suffix = file_path.suffix.lower()
    content_types = {
        ".mp3": "audio/mpeg",
        ".wav": "audio/wav",
        ".ogg": "audio/ogg",
        ".flac": "audio/flac",
        ".m4a": "audio/m4a",
        ".mp4": "video/mp4",
        ".webm": "video/webm",
        ".mkv": "video/x-matroska",
        ".mov": "video/quicktime",
        ".avi": "video/x-msvideo",
    }
    content_type = content_types.get(suffix, "application/octet-stream")
    
    return FileResponse(
        path=str(file_path),
        media_type=content_type,
        filename=job.filename,
    )


@router.get("/{job_id}/audio")
async def get_tts_audio(
    job_id: str,
    session: AsyncSession = Depends(get_session),
):
    """
    Stream the TTS synthesized audio.
    """
    result = await session.execute(select(Job).where(Job.id == job_id))
    job = result.scalar_one_or_none()
    
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    if not job.tts_audio_path:
        raise HTTPException(status_code=404, detail="TTS audio not available")
    
    file_path = Path(job.tts_audio_path)
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Audio file no longer exists")
    
    return FileResponse(
        path=str(file_path),
        media_type="audio/wav",
        filename=f"{job_id}_tts.wav",
    )


@router.get("/{job_id}/video-with-tts")
async def get_video_with_tts(
    job_id: str,
    session: AsyncSession = Depends(get_session),
):
    """
    Stream video with TTS audio track replacing original.
    
    This endpoint returns the remuxed video with synthesized audio.
    """
    result = await session.execute(select(Job).where(Job.id == job_id))
    job = result.scalar_one_or_none()
    
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    # Check if this was a video job with TTS enabled
    if not job.enable_tts:
        raise HTTPException(status_code=400, detail="TTS was not enabled for this job")
    
    # Look for remuxed video file
    tts_video_path = settings.output_dir / job_id / "video_with_tts.mp4"
    if not tts_video_path.exists():
        raise HTTPException(status_code=404, detail="Remuxed video not available yet")
    
    return FileResponse(
        path=str(tts_video_path),
        media_type="video/mp4",
        filename=f"{job_id}_with_tts.mp4",
    )


@router.get("/{job_id}/subtitles")
async def get_subtitles(
    job_id: str,
    format: str = Query(default="vtt", regex="^(srt|vtt)$"),
    session: AsyncSession = Depends(get_session),
):
    """
    Get subtitle file for a completed job.
    """
    result = await session.execute(select(Job).where(Job.id == job_id))
    job = result.scalar_one_or_none()
    
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    subtitle_path = settings.output_dir / job_id / f"subtitles.{format}"
    if not subtitle_path.exists():
        raise HTTPException(status_code=404, detail=f"Subtitle file not found")
    
    content_type = "text/vtt" if format == "vtt" else "text/plain"
    
    return FileResponse(
        path=str(subtitle_path),
        media_type=content_type,
        filename=f"{job_id}.{format}",
    )


async def stream_file(file_path: Path, chunk_size: int = 1024 * 64):
    """Generator for streaming file content."""
    async with aiofiles.open(file_path, "rb") as f:
        while chunk := await f.read(chunk_size):
            yield chunk
