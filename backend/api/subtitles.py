"""Subtitle burn-in API for video files."""

import asyncio
import subprocess
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from services.database import get_session
from models.database import Job, Transcript
from schemas.job import JobStatus
from config import settings

router = APIRouter()


class BurnSubtitlesRequest(BaseModel):
    """Options for subtitle burn-in."""
    font_size: int = 24
    font_color: str = "white"
    outline_color: str = "black"
    outline_width: int = 2
    position: str = "bottom"  # bottom, top, middle


async def burn_subtitles_task(job_id: str, options: BurnSubtitlesRequest):
    """Background task to burn subtitles into video."""
    from services.database import async_session_maker
    
    async with async_session_maker() as session:
        # Get job
        result = await session.execute(
            select(Job).where(Job.id == job_id)
        )
        job = result.scalar_one_or_none()
        
        if not job:
            return
        
        # Get transcript
        result = await session.execute(
            select(Transcript).where(Transcript.job_id == job_id)
        )
        transcript = result.scalar_one_or_none()
        
        if not transcript:
            return
        
        # Generate SRT file
        from services.export import generate_srt
        srt_content = await generate_srt(transcript)
        srt_path = Path(settings.output_dir) / f"{job_id}_burn.srt"
        srt_path.write_text(srt_content)
        
        # Determine output path
        input_path = Path(job.original_path)
        output_path = Path(settings.output_dir) / f"{job_id}_subtitled{input_path.suffix}"
        
        # Build ffmpeg command
        # Subtitle style
        style = f"FontSize={options.font_size},PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,Outline={options.outline_width}"
        
        position_map = {
            "bottom": "Alignment=2,MarginV=30",
            "top": "Alignment=6,MarginV=30",
            "middle": "Alignment=5",
        }
        style += f",{position_map.get(options.position, position_map['bottom'])}"
        
        cmd = [
            "ffmpeg", "-y",
            "-i", str(input_path),
            "-vf", f"subtitles={str(srt_path)}:force_style='{style}'",
            "-c:a", "copy",
            str(output_path),
        ]
        
        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await process.communicate()
            
            if process.returncode == 0:
                # Update job with subtitled video path
                job.tts_audio_path = str(output_path)  # Reusing field for subtitled video
                await session.commit()
        except Exception as e:
            print(f"Subtitle burn-in failed: {e}")
        finally:
            # Clean up temp SRT
            if srt_path.exists():
                srt_path.unlink()


@router.post("/{job_id}/burn-subtitles")
async def burn_subtitles(
    job_id: str,
    options: BurnSubtitlesRequest,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
):
    """
    Burn subtitles into a video file.
    
    Creates a new video file with embedded subtitles.
    """
    # Verify job exists and is a video
    result = await session.execute(
        select(Job).where(Job.id == job_id)
    )
    job = result.scalar_one_or_none()
    
    if not job:
        raise HTTPException(404, "Job not found")
    
    if job.status != JobStatus.COMPLETED:
        raise HTTPException(400, "Job must be completed first")
    
    # Check if it's a video file
    video_extensions = {'.mp4', '.webm', '.mkv', '.mov', '.avi'}
    if not any(job.original_path.lower().endswith(ext) for ext in video_extensions):
        raise HTTPException(400, "Only video files support subtitle burn-in")
    
    # Check for transcript
    result = await session.execute(
        select(Transcript).where(Transcript.job_id == job_id)
    )
    transcript = result.scalar_one_or_none()
    
    if not transcript:
        raise HTTPException(400, "No transcript found for this job")
    
    # Start background task
    background_tasks.add_task(burn_subtitles_task, job_id, options)
    
    return {
        "status": "processing",
        "message": "Subtitle burn-in started",
        "job_id": job_id,
    }
