"""Simple background task runner without Celery for development/simple deployments."""

import asyncio
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import Optional
from sqlalchemy import select

from config import settings
from services.database import async_session_maker
from models.database import Job, Model, Transcript, TranscriptSegment
from schemas.job import JobStatus


# Thread pool for running CPU-bound tasks
executor = ThreadPoolExecutor(max_workers=settings.max_concurrent_jobs or 2)


async def process_job_async(job_id: str):
    """
    Process a job asynchronously without Celery.
    
    This is a simplified version for development/local use.
    For production with multiple workers, use Celery.
    """
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
            
            # Broadcast start
            await broadcast_progress(job_id, 0, "processing", "Starting job...")
            
            # Step 1: Transcription
            job.status = JobStatus.TRANSCRIBING
            await session.commit()
            await broadcast_progress(job_id, 5, "transcribing", "Transcribing audio...")
            
            transcript_result = await run_transcription(session, job)
            
            if not transcript_result:
                raise ValueError("Transcription failed")
            
            # Step 2: Diarization (if enabled)
            if job.enable_diarization:
                job.status = JobStatus.DIARIZING
                await session.commit()
                await broadcast_progress(job_id, 60, "diarizing", "Identifying speakers...")
                
                await run_diarization(session, job)
            
            # Step 3: TTS (if enabled)
            if job.enable_tts:
                job.status = JobStatus.SYNTHESIZING
                await session.commit()
                await broadcast_progress(job_id, 80, "generating_tts", "Synthesizing speech...")
                
                await run_tts(session, job)
            
            # Complete
            await session.refresh(job)
            job.status = JobStatus.COMPLETED
            job.completed_at = datetime.utcnow()
            job.progress = 100.0
            await session.commit()
            
            # Update batch progress if part of a batch
            if job.batch_id:
                from api.batches import update_batch_progress
                await update_batch_progress(session, job.batch_id)
            
            await broadcast_progress(job_id, 100, "completed", "Job completed!")
            
            return {"status": "completed", "job_id": job_id}
            
        except Exception as e:
            await session.refresh(job)
            job.status = JobStatus.FAILED
            job.error_message = str(e)
            job.completed_at = datetime.utcnow()
            await session.commit()
            
            # Update batch progress if part of a batch
            if job.batch_id:
                from api.batches import update_batch_progress
                await update_batch_progress(session, job.batch_id)
            
            await broadcast_progress(job_id, 0, "failed", str(e))
            
            raise


async def broadcast_progress(job_id: str, progress: float, stage: str, message: str):
    """Broadcast job progress to WebSocket clients."""
    try:
        from api.queue import manager
        # Format matches frontend useWebSocket.ts expectations
        await manager.broadcast({
            "type": "job_progress",
            "data": {
                "jobId": job_id,
                "stage": stage,
                "progress": progress,
                "message": message,
            }
        })
    except Exception:
        pass  # WebSocket might not be initialized


async def run_transcription(session, job):
    """Run transcription using faster-whisper."""
    from workers.stt_worker import (
        transcribe_faster_whisper,
        extract_audio_if_needed,
        generate_output_files,
    )
    from pathlib import Path
    
    # Get model
    model = None
    if job.model_id:
        result = await session.execute(
            select(Model).where(Model.id == job.model_id)
        )
        model = result.scalar_one_or_none()
    
    if not model:
        result = await session.execute(
            select(Model).where(
                Model.model_type == "whisper",
                Model.is_default == True,
            )
        )
        model = result.scalar_one_or_none()
    
    if not model:
        raise ValueError("No STT model available. Please register and download a model first.")
    
    if not model.is_downloaded:
        raise ValueError(f"Model '{model.name}' is not downloaded. Please download it first.")
    
    # Extract audio if needed
    audio_path = await extract_audio_if_needed(job.original_path)
    
    # Progress callback
    async def progress_cb(p):
        await broadcast_progress(job.id, 10 + p * 0.5, "transcribing", f"Transcribing: {int(p)}%")
    
    # Determine task: "translate" if translating to English, otherwise "transcribe"
    task = "translate" if job.translate_to == "en" else "transcribe"
    
    # Run transcription
    segments, info = await transcribe_faster_whisper(
        audio_path=audio_path,
        model_id=model.model_id,
        language=job.language if job.language != "auto" else None,
        compute_type=model.compute_type or settings.compute_type,
        device=model.device or settings.device,
        task=task,
        progress_callback=lambda p: asyncio.create_task(progress_cb(p)),
    )
    
    # Save transcript
    transcript = Transcript(
        job_id=job.id,
        language=info.get("language", job.language),
        duration=info.get("duration", 0),
        word_count=sum(len(seg["text"].split()) for seg in segments),
        full_text=" ".join(seg["text"] for seg in segments),
    )
    session.add(transcript)
    await session.commit()
    await session.refresh(transcript)
    
    # Save segments
    for i, seg in enumerate(segments):
        segment = TranscriptSegment(
            transcript_id=transcript.id,
            segment_index=i,
            start_time=seg["start"],
            end_time=seg["end"],
            text=seg["text"],
            confidence=seg.get("confidence"),
            words=seg.get("words"),
        )
        session.add(segment)
    
    # Update job
    job.detected_language = info.get("language")
    job.duration = info.get("duration")
    job.progress = 55
    
    # Generate output files
    output_dir = settings.output_dir / job.id
    output_dir.mkdir(parents=True, exist_ok=True)
    
    await generate_output_files(segments, output_dir, job.output_formats)
    
    job.transcript_path = str(output_dir / "transcript.json")
    await session.commit()
    
    return {"segments": segments, "info": info}


async def run_diarization(session, job):
    """Run speaker diarization using pyannote or configured engine."""
    from workers.diarization_worker import (
        diarize_pyannote,
        find_speaker_for_segment,
        get_audio_path,
    )
    from models.database import Model, Transcript, TranscriptSegment
    
    # Get diarization model
    model = None
    if job.diarization_model_id:
        result = await session.execute(
            select(Model).where(Model.id == job.diarization_model_id)
        )
        model = result.scalar_one_or_none()
    
    if not model:
        result = await session.execute(
            select(Model).where(
                Model.model_type == "diarization",
                Model.is_default == True,
            )
        )
        model = result.scalar_one_or_none()
    
    if not model:
        await broadcast_progress(job.id, 75, "diarizing", "No diarization model - skipping")
        return
    
    if not model.is_downloaded:
        await broadcast_progress(job.id, 75, "diarizing", "Diarization model not downloaded - skipping")
        return
    
    await broadcast_progress(job.id, 62, "diarizing", "Running pyannote diarization...")
    
    # Get audio path
    audio_path = await get_audio_path(job.original_path)
    
    # Run diarization (pyannote is default)
    try:
        diarization = await diarize_pyannote(
            audio_path=audio_path,
            model_id=model.model_id,
            device=model.device or settings.device,
            hf_token=settings.hf_token,
        )
    except Exception as e:
        await broadcast_progress(job.id, 75, "diarizing", f"Diarization failed: {str(e)[:50]}")
        return
    
    await broadcast_progress(job.id, 70, "diarizing", "Assigning speakers to segments...")
    
    # Get transcript segments
    result = await session.execute(
        select(Transcript).where(Transcript.job_id == job.id)
    )
    transcript = result.scalar_one_or_none()
    
    if transcript:
        result = await session.execute(
            select(TranscriptSegment)
            .where(TranscriptSegment.transcript_id == transcript.id)
            .order_by(TranscriptSegment.segment_index)
        )
        segments = result.scalars().all()
        
        # Assign speakers to segments
        speakers = set()
        for segment in segments:
            speaker = find_speaker_for_segment(
                diarization,
                segment.start_time,
                segment.end_time,
            )
            segment.speaker = speaker
            if speaker:
                speakers.add(speaker)
        
        transcript.speaker_count = len(speakers)
        await session.commit()
    
    await broadcast_progress(job.id, 75, "diarizing", f"Identified {len(speakers)} speakers")


async def run_tts(session, job):
    """Run TTS synthesis using Coqui or configured engine."""
    from workers.tts_worker import (
        synthesize_coqui_xtts,
        synthesize_piper,
        combine_audio_segments,
    )
    from models.database import Model, Transcript, TranscriptSegment, TTSOutput
    from pathlib import Path
    
    # Get TTS model
    model = None
    if job.tts_model_id:
        result = await session.execute(
            select(Model).where(Model.id == job.tts_model_id)
        )
        model = result.scalar_one_or_none()
    
    if not model:
        result = await session.execute(
            select(Model).where(
                Model.model_type == "tts",
                Model.is_default == True,
            )
        )
        model = result.scalar_one_or_none()
    
    if not model:
        await broadcast_progress(job.id, 95, "generating_tts", "No TTS model - skipping")
        return
    
    if not model.is_downloaded:
        await broadcast_progress(job.id, 95, "generating_tts", "TTS model not downloaded - skipping")
        return
    
    await broadcast_progress(job.id, 82, "generating_tts", "Loading TTS model...")
    
    # Get transcript segments
    result = await session.execute(
        select(Transcript).where(Transcript.job_id == job.id)
    )
    transcript = result.scalar_one_or_none()
    
    if not transcript:
        await broadcast_progress(job.id, 95, "generating_tts", "No transcript for TTS - skipping")
        return
    
    result = await session.execute(
        select(TranscriptSegment)
        .where(TranscriptSegment.transcript_id == transcript.id)
        .order_by(TranscriptSegment.segment_index)
    )
    segments = result.scalars().all()
    
    # Prepare output directory
    output_dir = settings.output_dir / job.id
    output_dir.mkdir(parents=True, exist_ok=True)
    
    await broadcast_progress(job.id, 85, "generating_tts", f"Synthesizing {len(segments)} segments...")
    
    # Run TTS (default to Coqui XTTS)
    try:
        audio_segments = await synthesize_coqui_xtts(
            segments=segments,
            model_id=model.model_id,
            language=job.detected_language or job.language or "en",
            output_dir=output_dir,
            device=model.device or settings.device,
        )
    except Exception as e:
        await broadcast_progress(job.id, 95, "generating_tts", f"TTS failed: {str(e)[:50]}")
        return
    
    await broadcast_progress(job.id, 92, "generating_tts", "Combining audio segments...")
    
    # Combine all audio segments
    combined_path = output_dir / "tts_output.wav"
    await combine_audio_segments(audio_segments, combined_path)
    
    # Save TTS output record
    import wave
    try:
        with wave.open(str(combined_path), 'r') as wav:
            duration = wav.getnframes() / wav.getframerate()
            sample_rate = wav.getframerate()
        
        tts_output = TTSOutput(
            job_id=job.id,
            audio_path=str(combined_path),
            duration=duration,
            sample_rate=sample_rate,
            format="wav",
            is_timing_synced=False,
            original_duration=job.duration,
        )
        session.add(tts_output)
        
        job.tts_audio_path = str(combined_path)
        await session.commit()
    except Exception:
        pass  # Audio file may not be valid wav
    
    await broadcast_progress(job.id, 95, "generating_tts", "TTS complete")


def start_job_background(job_id: str):
    """Start job processing in a background thread."""
    def run():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(process_job_async(job_id))
        finally:
            loop.close()
    
    executor.submit(run)
