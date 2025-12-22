"""Batch job management API for bulk uploads."""

import io
import zipfile
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, Depends, File, Form, UploadFile, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from services.database import get_session
from models.database import Job, JobBatch, Transcript
from schemas.job import JobStatus
from config import settings

router = APIRouter()


@router.post("")
async def create_batch(
    files: List[UploadFile] = File(...),
    batch_name: Optional[str] = Form(default=None),
    language: str = Form(default="auto"),
    enable_diarization: bool = Form(default=False),
    enable_tts: bool = Form(default=False),
    session: AsyncSession = Depends(get_session),
):
    """
    Create a batch job from multiple files.
    
    All files will be processed with the same settings.
    """
    if len(files) < 2:
        raise HTTPException(400, "Batch requires at least 2 files")
    
    # Generate batch name if not provided
    if not batch_name:
        batch_name = f"Batch {datetime.now().strftime('%Y-%m-%d %H:%M')}"
    
    # Create batch
    batch = JobBatch(
        name=batch_name,
        total_files=len(files),
        status=JobStatus.PENDING,
    )
    session.add(batch)
    await session.flush()  # Get batch ID
    
    # Create jobs for each file
    jobs = []
    for file in files:
        # Save file
        file_path = settings.upload_dir / f"{batch.id}_{file.filename}"
        content = await file.read()
        file_path.write_bytes(content)
        
        job = Job(
            batch_id=batch.id,
            filename=file.filename,
            original_path=str(file_path),
            file_size=len(content),
            language=language,
            enable_diarization=enable_diarization,
            enable_tts=enable_tts,
            status=JobStatus.QUEUED,
        )
        session.add(job)
        jobs.append(job)
    
    await session.commit()
    
    # Start processing jobs
    from services.background_tasks import start_job_background
    for job in jobs:
        start_job_background(job.id)
    
    return {
        "id": batch.id,
        "name": batch.name,
        "total_files": batch.total_files,
        "status": batch.status.value,
        "jobs": [{"id": j.id, "filename": j.filename} for j in jobs],
    }


@router.get("")
async def list_batches(
    limit: int = 20,
    offset: int = 0,
    session: AsyncSession = Depends(get_session),
):
    """List all batches."""
    result = await session.execute(
        select(JobBatch)
        .order_by(JobBatch.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    batches = result.scalars().all()
    
    return {
        "batches": [
            {
                "id": b.id,
                "name": b.name,
                "total_files": b.total_files,
                "completed_files": b.completed_files,
                "failed_files": b.failed_files,
                "status": b.status.value,
                "progress": b.progress,
                "created_at": b.created_at.isoformat() if b.created_at else None,
            }
            for b in batches
        ]
    }


@router.get("/{batch_id}")
async def get_batch(
    batch_id: str,
    session: AsyncSession = Depends(get_session),
):
    """Get batch details with all jobs."""
    result = await session.execute(
        select(JobBatch)
        .where(JobBatch.id == batch_id)
        .options(selectinload(JobBatch.jobs))
    )
    batch = result.scalar_one_or_none()
    
    if not batch:
        raise HTTPException(404, "Batch not found")
    
    return {
        "id": batch.id,
        "name": batch.name,
        "total_files": batch.total_files,
        "completed_files": batch.completed_files,
        "failed_files": batch.failed_files,
        "status": batch.status.value,
        "progress": batch.progress,
        "created_at": batch.created_at.isoformat() if batch.created_at else None,
        "completed_at": batch.completed_at.isoformat() if batch.completed_at else None,
        "jobs": [
            {
                "id": j.id,
                "filename": j.filename,
                "status": j.status.value,
                "progress": j.progress,
                "current_stage": j.current_stage,
                "duration": j.duration,
                "error_message": j.error_message,
            }
            for j in batch.jobs
        ],
    }


@router.delete("/{batch_id}")
async def delete_batch(
    batch_id: str,
    session: AsyncSession = Depends(get_session),
):
    """Delete a batch and all its jobs."""
    result = await session.execute(
        select(JobBatch)
        .where(JobBatch.id == batch_id)
        .options(selectinload(JobBatch.jobs))
    )
    batch = result.scalar_one_or_none()
    
    if not batch:
        raise HTTPException(404, "Batch not found")
    
    # Delete all jobs
    for job in batch.jobs:
        await session.delete(job)
    
    await session.delete(batch)
    await session.commit()
    
    return {"deleted": batch_id}


@router.get("/{batch_id}/export")
async def export_batch(
    batch_id: str,
    format: str = "txt",
    session: AsyncSession = Depends(get_session),
):
    """
    Export all transcripts from a batch as a ZIP file.
    
    Format options: txt, srt, json
    """
    result = await session.execute(
        select(JobBatch)
        .where(JobBatch.id == batch_id)
        .options(selectinload(JobBatch.jobs))
    )
    batch = result.scalar_one_or_none()
    
    if not batch:
        raise HTTPException(404, "Batch not found")
    
    # Create ZIP in memory
    zip_buffer = io.BytesIO()
    
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        for job in batch.jobs:
            if job.status != JobStatus.COMPLETED:
                continue
            
            # Get transcript
            result = await session.execute(
                select(Transcript).where(Transcript.job_id == job.id)
            )
            transcript = result.scalar_one_or_none()
            
            if not transcript:
                continue
            
            # Generate content based on format
            base_name = Path(job.filename).stem
            
            if format == "txt":
                content = transcript.full_text or ""
                filename = f"{base_name}.txt"
            elif format == "srt":
                # Generate SRT from segments
                from services.export import generate_srt
                content = await generate_srt(transcript)
                filename = f"{base_name}.srt"
            else:  # json
                import json
                content = json.dumps({
                    "job_id": job.id,
                    "filename": job.filename,
                    "language": transcript.language,
                    "text": transcript.full_text,
                }, indent=2)
                filename = f"{base_name}.json"
            
            zip_file.writestr(filename, content)
    
    zip_buffer.seek(0)
    
    return StreamingResponse(
        zip_buffer,
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="{batch.name}.zip"'
        }
    )


async def update_batch_progress(session: AsyncSession, batch_id: str):
    """Update batch progress after a job completes."""
    result = await session.execute(
        select(JobBatch)
        .where(JobBatch.id == batch_id)
        .options(selectinload(JobBatch.jobs))
    )
    batch = result.scalar_one_or_none()
    
    if not batch:
        return
    
    completed = sum(1 for j in batch.jobs if j.status == JobStatus.COMPLETED)
    failed = sum(1 for j in batch.jobs if j.status == JobStatus.FAILED)
    
    batch.completed_files = completed
    batch.failed_files = failed
    batch.progress = (completed + failed) / batch.total_files * 100
    
    if completed + failed >= batch.total_files:
        batch.status = JobStatus.COMPLETED if failed == 0 else JobStatus.FAILED
        batch.completed_at = datetime.utcnow()
    elif completed + failed > 0:
        batch.status = JobStatus.PROCESSING
    
    await session.commit()
