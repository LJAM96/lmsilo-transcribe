"""Audio synchronization worker for timing-matched TTS output."""

import asyncio
from pathlib import Path
from typing import Dict, Any, List
from sqlalchemy import select

from .celery_app import celery_app
from config import settings


@celery_app.task(bind=True, name="workers.sync_worker.sync_audio_timing")
def sync_audio_timing(self, job_id: str, prev_result: Any = None):
    """
    Synchronize TTS audio to match original audio timing.
    
    This uses rubberband for time-stretching and FFmpeg for video remuxing.
    Each segment is stretched/compressed to match its original duration.
    """
    from services.database import async_session_maker
    from models.database import Job, Transcript, TranscriptSegment, TTSOutput
    from schemas.job import JobStatus
    
    async def run():
        async with async_session_maker() as session:
            result = await session.execute(select(Job).where(Job.id == job_id))
            job = result.scalar_one_or_none()
            
            if not job:
                raise ValueError(f"Job {job_id} not found")
            
            if not job.enable_tts or not job.sync_tts_timing:
                return {"status": "skipped", "job_id": job_id}
            
            # Update status
            job.status = JobStatus.SYNCING
            job.current_stage = "syncing audio timing"
            await session.commit()
            
            await update_progress(session, job, 92, "Synchronizing audio timing...")
            
            # Get output directory
            output_dir = settings.output_dir / job_id
            
            # Get transcript segments with timing info
            result = await session.execute(
                select(Transcript).where(Transcript.job_id == job_id)
            )
            transcript = result.scalar_one_or_none()
            
            if not transcript:
                raise ValueError("No transcript found")
            
            result = await session.execute(
                select(TranscriptSegment)
                .where(TranscriptSegment.transcript_id == transcript.id)
                .order_by(TranscriptSegment.segment_index)
            )
            segments = result.scalars().all()
            
            # Time-stretch each segment to match original duration
            synced_segments = []
            
            for i, seg in enumerate(segments):
                original_duration = seg.end_time - seg.start_time
                segment_path = output_dir / f"segment_{i:04d}.wav"
                synced_path = output_dir / f"segment_{i:04d}_synced.wav"
                
                if segment_path.exists():
                    # Get TTS segment duration
                    tts_duration = await get_audio_duration(segment_path)
                    
                    if tts_duration > 0:
                        # Calculate stretch ratio
                        ratio = original_duration / tts_duration
                        
                        # Apply time-stretch using rubberband
                        await time_stretch_audio(
                            input_path=segment_path,
                            output_path=synced_path,
                            ratio=ratio,
                        )
                        
                        synced_segments.append({
                            "path": str(synced_path),
                            "start": seg.start_time,
                            "end": seg.end_time,
                            "original_duration": original_duration,
                            "tts_duration": tts_duration,
                            "ratio": ratio,
                        })
            
            await update_progress(session, job, 95, "Combining synced audio...")
            
            # Combine synced segments with proper timing (including silence gaps)
            synced_audio_path = output_dir / "tts_synced.wav"
            await combine_with_timing(
                segments=synced_segments,
                total_duration=job.duration or transcript.duration,
                output_path=synced_audio_path,
            )
            
            # Update TTS output record
            result = await session.execute(
                select(TTSOutput).where(TTSOutput.job_id == job_id)
            )
            tts_output = result.scalar_one_or_none()
            
            if tts_output:
                tts_output.audio_path = str(synced_audio_path)
                tts_output.is_timing_synced = True
            
            job.tts_audio_path = str(synced_audio_path)
            
            # If source was video, remux with new audio
            source_path = Path(job.original_path)
            video_extensions = {".mp4", ".webm", ".mkv", ".mov", ".avi"}
            
            if source_path.suffix.lower() in video_extensions:
                await update_progress(session, job, 97, "Creating video with new audio...")
                
                video_with_tts = output_dir / "video_with_tts.mp4"
                await remux_video_with_audio(
                    video_path=source_path,
                    audio_path=synced_audio_path,
                    output_path=video_with_tts,
                )
            
            await session.commit()
            await update_progress(session, job, 99, "Audio sync complete")
            
            return {
                "status": "synced",
                "job_id": job_id,
                "synced_audio": str(synced_audio_path),
            }
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(run())
    finally:
        loop.close()


async def get_audio_duration(audio_path: Path) -> float:
    """Get duration of audio file in seconds."""
    import subprocess
    import json
    
    result = subprocess.run([
        "ffprobe",
        "-v", "quiet",
        "-print_format", "json",
        "-show_format",
        str(audio_path),
    ], capture_output=True, text=True)
    
    if result.returncode != 0:
        return 0
    
    data = json.loads(result.stdout)
    return float(data.get("format", {}).get("duration", 0))


async def time_stretch_audio(
    input_path: Path,
    output_path: Path,
    ratio: float,
) -> None:
    """
    Time-stretch audio using rubberband.
    
    Ratio < 1 = speed up (compress)
    Ratio > 1 = slow down (stretch)
    """
    import subprocess
    
    # Clamp ratio to reasonable bounds
    ratio = max(0.25, min(4.0, ratio))
    
    # rubberband uses time ratio (inverse of speed)
    subprocess.run([
        "rubberband",
        "-t", str(ratio),  # Time ratio
        "-p", "0",  # No pitch shift
        "-c", "6",  # Crisp mode for speech
        str(input_path),
        str(output_path),
    ], check=True, capture_output=True)


async def combine_with_timing(
    segments: List[Dict],
    total_duration: float,
    output_path: Path,
) -> None:
    """
    Combine audio segments with proper timing, inserting silence for gaps.
    """
    import subprocess
    import wave
    import struct
    
    # Create output wav file
    sample_rate = 22050  # Standard rate
    
    # Calculate total samples
    total_samples = int(total_duration * sample_rate)
    
    # Create empty audio buffer
    audio_buffer = [0.0] * total_samples
    
    # Insert each segment at correct position
    for seg in segments:
        start_sample = int(seg["start"] * sample_rate)
        
        # Read segment audio
        if Path(seg["path"]).exists():
            with wave.open(seg["path"], 'r') as wav:
                # Resample if needed
                seg_rate = wav.getframerate()
                n_frames = wav.getnframes()
                raw_data = wav.readframes(n_frames)
                
                if wav.getsampwidth() == 2:
                    samples = struct.unpack(f"{n_frames}h", raw_data)
                    samples = [s / 32768.0 for s in samples]  # Normalize
                    
                    # Simple resampling if rates differ
                    if seg_rate != sample_rate:
                        ratio = sample_rate / seg_rate
                        new_len = int(len(samples) * ratio)
                        samples = [samples[int(i / ratio)] for i in range(new_len)]
                    
                    # Insert into buffer
                    for i, s in enumerate(samples):
                        idx = start_sample + i
                        if idx < len(audio_buffer):
                            audio_buffer[idx] = s
    
    # Write output
    with wave.open(str(output_path), 'w') as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        
        # Convert back to int16
        int_samples = [int(max(-1, min(1, s)) * 32767) for s in audio_buffer]
        wav.writeframes(struct.pack(f"{len(int_samples)}h", *int_samples))


async def remux_video_with_audio(
    video_path: Path,
    audio_path: Path,
    output_path: Path,
) -> None:
    """
    Replace video's audio track with new audio.
    """
    import subprocess
    
    subprocess.run([
        "ffmpeg",
        "-i", str(video_path),
        "-i", str(audio_path),
        "-c:v", "copy",  # Keep video codec
        "-map", "0:v:0",  # Use video from first input
        "-map", "1:a:0",  # Use audio from second input
        "-shortest",  # Match shortest stream
        str(output_path),
        "-y",
    ], check=True, capture_output=True)


async def update_progress(session, job, progress: float, message: str = ""):
    """Update job progress."""
    job.progress = progress
    if message:
        job.current_stage = message
    await session.commit()
    
    from api.queue import manager
    await manager.broadcast({
        "type": "progress",
        "job_id": job.id,
        "progress": progress,
        "message": message,
    })
