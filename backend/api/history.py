"""Job history API with search and filtering."""

from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession

from services.database import get_session
from models.database import Job, Transcript
from schemas.job import JobResponse, JobStatus, OutputFormat

router = APIRouter()


@router.get("")
async def get_history(
    q: Optional[str] = Query(default=None, description="Search query"),
    status: Optional[JobStatus] = Query(default=None),
    start_date: Optional[datetime] = Query(default=None),
    end_date: Optional[datetime] = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_session),
):
    """
    Get job history with search and filters.
    
    - **q**: Full-text search in filename and transcript text
    - **status**: Filter by job status
    - **start_date**: Filter jobs created after this date
    - **end_date**: Filter jobs created before this date
    """
    # Base query - only completed/failed jobs (not pending/processing)
    query = select(Job).where(
        Job.status.in_([
            JobStatus.COMPLETED,
            JobStatus.FAILED,
            JobStatus.CANCELLED,
        ])
    )
    
    # Apply status filter
    if status:
        query = query.where(Job.status == status)
    
    # Apply date filters
    if start_date:
        query = query.where(Job.created_at >= start_date)
    if end_date:
        query = query.where(Job.created_at <= end_date)
    
    # Apply search query
    if q:
        search_pattern = f"%{q}%"
        # Search in filename
        query = query.where(
            or_(
                Job.filename.ilike(search_pattern),
                Job.detected_language.ilike(search_pattern) if Job.detected_language else False,
            )
        )
    
    # Order by completion date, then created date
    query = query.order_by(
        Job.completed_at.desc().nullsfirst(),
        Job.created_at.desc()
    )
    
    # Get total count for pagination
    count_query = select(func.count(Job.id)).where(
        Job.status.in_([JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED])
    )
    if status:
        count_query = count_query.where(Job.status == status)
    if start_date:
        count_query = count_query.where(Job.created_at >= start_date)
    if end_date:
        count_query = count_query.where(Job.created_at <= end_date)
    
    result = await session.execute(count_query)
    total = result.scalar()
    
    # Apply pagination
    query = query.limit(limit).offset(offset)
    
    result = await session.execute(query)
    jobs = result.scalars().all()
    
    return {
        "total": total,
        "offset": offset,
        "limit": limit,
        "jobs": [
            {
                "id": job.id,
                "filename": job.filename,
                "status": job.status.value,
                "language": job.language,
                "detected_language": job.detected_language,
                "duration": job.duration,
                "created_at": job.created_at.isoformat() if job.created_at else None,
                "completed_at": job.completed_at.isoformat() if job.completed_at else None,
                "has_transcript": bool(job.transcript_path),
                "has_tts": bool(job.tts_audio_path),
                "error_message": job.error_message,
            }
            for job in jobs
        ],
    }


@router.get("/search")
async def search_transcripts(
    q: str = Query(..., min_length=2, description="Search query"),
    limit: int = Query(default=20, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
):
    """
    Search within transcript text.
    
    Returns jobs with matching transcript segments.
    """
    search_pattern = f"%{q}%"
    
    # Search in transcripts
    result = await session.execute(
        select(Transcript)
        .where(Transcript.full_text.ilike(search_pattern))
        .limit(limit)
    )
    transcripts = result.scalars().all()
    
    # Get associated jobs
    job_ids = [t.job_id for t in transcripts]
    
    if not job_ids:
        return {"results": [], "query": q}
    
    result = await session.execute(
        select(Job).where(Job.id.in_(job_ids))
    )
    jobs = result.scalars().all()
    jobs_map = {j.id: j for j in jobs}
    
    results = []
    for transcript in transcripts:
        job = jobs_map.get(transcript.job_id)
        if job:
            # Find matching snippet
            text = transcript.full_text or ""
            q_lower = q.lower()
            text_lower = text.lower()
            pos = text_lower.find(q_lower)
            
            if pos >= 0:
                start = max(0, pos - 50)
                end = min(len(text), pos + len(q) + 50)
                snippet = "..." + text[start:end] + "..." if start > 0 else text[start:end] + "..."
            else:
                snippet = text[:100] + "..." if len(text) > 100 else text
            
            results.append({
                "job_id": job.id,
                "filename": job.filename,
                "language": job.detected_language or job.language,
                "snippet": snippet,
                "created_at": job.created_at.isoformat() if job.created_at else None,
            })
    
    return {"results": results, "query": q}


@router.get("/stats")
async def get_stats(
    session: AsyncSession = Depends(get_session),
):
    """Get overall job statistics."""
    # Total jobs by status
    result = await session.execute(
        select(Job.status, func.count(Job.id))
        .group_by(Job.status)
    )
    status_counts = {status.value: count for status, count in result.all()}
    
    # Total duration processed
    result = await session.execute(
        select(func.sum(Job.duration))
        .where(Job.status == JobStatus.COMPLETED)
    )
    total_duration = result.scalar() or 0
    
    # Average processing time
    result = await session.execute(
        select(func.avg(
            func.extract('epoch', Job.completed_at) - func.extract('epoch', Job.started_at)
        ))
        .where(
            Job.status == JobStatus.COMPLETED,
            Job.completed_at.isnot(None),
            Job.started_at.isnot(None),
        )
    )
    avg_processing_time = result.scalar() or 0
    
    # Jobs by language
    result = await session.execute(
        select(Job.detected_language, func.count(Job.id))
        .where(Job.detected_language.isnot(None))
        .group_by(Job.detected_language)
        .order_by(func.count(Job.id).desc())
        .limit(10)
    )
    language_counts = [
        {"language": lang, "count": count} 
        for lang, count in result.all()
    ]
    
    return {
        "status_counts": status_counts,
        "total_completed": status_counts.get("completed", 0),
        "total_failed": status_counts.get("failed", 0),
        "total_duration_hours": round(total_duration / 3600, 2),
        "avg_processing_seconds": round(avg_processing_time, 2),
        "top_languages": language_counts,
    }
