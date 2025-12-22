"""Prometheus metrics endpoint for monitoring."""

from datetime import datetime
from fastapi import APIRouter
from fastapi.responses import PlainTextResponse
from sqlalchemy import select, func

from services.database import async_session_maker
from models.database import Job, Model
from schemas.job import JobStatus

router = APIRouter()


async def get_metrics_data():
    """Gather metrics from database."""
    async with async_session_maker() as session:
        # Job counts by status
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
        
        # Jobs in last hour
        one_hour_ago = datetime.utcnow().replace(minute=0, second=0, microsecond=0)
        result = await session.execute(
            select(func.count(Job.id))
            .where(Job.created_at >= one_hour_ago)
        )
        jobs_last_hour = result.scalar() or 0
        
        # Model counts
        result = await session.execute(
            select(func.count(Model.id))
            .where(Model.is_downloaded == True)
        )
        downloaded_models = result.scalar() or 0
        
        return {
            "status_counts": status_counts,
            "total_duration": total_duration,
            "avg_processing_time": avg_processing_time,
            "jobs_last_hour": jobs_last_hour,
            "downloaded_models": downloaded_models,
        }


@router.get("", response_class=PlainTextResponse)
async def get_metrics():
    """
    Prometheus metrics endpoint.
    
    Returns metrics in Prometheus text format.
    """
    data = await get_metrics_data()
    
    lines = [
        "# HELP stt_jobs_total Total number of jobs by status",
        "# TYPE stt_jobs_total gauge",
    ]
    
    for status, count in data["status_counts"].items():
        lines.append(f'stt_jobs_total{{status="{status}"}} {count}')
    
    lines.extend([
        "",
        "# HELP stt_audio_processed_seconds Total seconds of audio processed",
        "# TYPE stt_audio_processed_seconds counter",
        f"stt_audio_processed_seconds {data['total_duration']:.2f}",
        "",
        "# HELP stt_processing_time_seconds Average job processing time",
        "# TYPE stt_processing_time_seconds gauge",
        f"stt_processing_time_seconds {data['avg_processing_time']:.2f}",
        "",
        "# HELP stt_jobs_last_hour Jobs created in the last hour",
        "# TYPE stt_jobs_last_hour gauge",
        f"stt_jobs_last_hour {data['jobs_last_hour']}",
        "",
        "# HELP stt_models_downloaded Number of downloaded models",
        "# TYPE stt_models_downloaded gauge",
        f"stt_models_downloaded {data['downloaded_models']}",
    ])
    
    return "\n".join(lines)


@router.get("/json")
async def get_metrics_json():
    """Get metrics in JSON format."""
    return await get_metrics_data()
