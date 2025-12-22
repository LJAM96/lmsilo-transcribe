"""Main task orchestration for job processing."""

import asyncio
from datetime import datetime
from celery import chain
from sqlalchemy import select

from .celery_app import celery_app
from .stt_worker import transcribe_audio
from .diarization_worker import diarize_audio
from .tts_worker import synthesize_speech
from .sync_worker import sync_audio_timing


@celery_app.task(bind=True, name="workers.tasks.process_job")
def process_job(self, job_id: str):
    """
    Main job processing orchestrator.
    
    Runs the appropriate pipeline based on job configuration:
    1. Transcription (always)
    2. Diarization (if enabled)
    3. TTS synthesis (if enabled)
    4. Audio sync (if TTS + timing sync enabled)
    """
    from services.database import async_session_maker
    from models.database import Job
    from schemas.job import JobStatus
    
    async def run():
        async with async_session_maker() as session:
            result = await session.execute(select(Job).where(Job.id == job_id))
            job = result.scalar_one_or_none()
            
            if not job:
                return {"error": "Job not found"}
            
            try:
                # Update status to processing
                job.status = JobStatus.PROCESSING
                job.started_at = datetime.utcnow()
                await session.commit()
                
                # Build processing chain based on options
                tasks = []
                
                # Step 1: Transcription (always required)
                tasks.append(transcribe_audio.s(job_id))
                
                # Step 2: Diarization (optional)
                if job.enable_diarization:
                    tasks.append(diarize_audio.s(job_id))
                
                # Step 3: TTS synthesis (optional)
                if job.enable_tts:
                    tasks.append(synthesize_speech.s(job_id))
                    
                    # Step 4: Audio timing sync (if TTS enabled and sync requested)
                    if job.sync_tts_timing:
                        tasks.append(sync_audio_timing.s(job_id))
                
                # Execute chain
                if len(tasks) == 1:
                    # Single task, run directly
                    result = tasks[0].apply_async()
                    result.get()  # Wait for completion
                else:
                    # Chain multiple tasks
                    workflow = chain(*tasks)
                    result = workflow.apply_async()
                    result.get()  # Wait for completion
                
                # Mark as completed
                await session.refresh(job)
                job.status = JobStatus.COMPLETED
                job.completed_at = datetime.utcnow()
                job.progress = 100.0
                await session.commit()
                
                # Notify via WebSocket
                await notify_completion(job)
                
                return {"status": "completed", "job_id": job_id}
                
            except Exception as e:
                await session.refresh(job)
                job.status = JobStatus.FAILED
                job.error_message = str(e)
                job.completed_at = datetime.utcnow()
                await session.commit()
                
                await notify_failure(job, str(e))
                
                raise
    
    # Run async function in sync context
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(run())
    finally:
        loop.close()


async def notify_completion(job):
    """Notify WebSocket clients of job completion."""
    from api.queue import manager
    
    await manager.broadcast({
        "type": "job_completed",
        "job": {
            "id": job.id,
            "filename": job.filename,
            "status": job.status.value,
            "duration": job.duration,
        },
    })


async def notify_failure(job, error: str):
    """Notify WebSocket clients of job failure."""
    from api.queue import manager
    
    await manager.broadcast({
        "type": "job_failed",
        "job": {
            "id": job.id,
            "filename": job.filename,
            "status": job.status.value,
            "error": error,
        },
    })
