"""Speaker diarization worker with pluggable engine support."""

import asyncio
from typing import Dict, Any, List, Optional
from sqlalchemy import select

from .celery_app import celery_app
from config import settings
from schemas.model import ModelEngine


@celery_app.task(bind=True, name="workers.diarization_worker.diarize_audio")
def diarize_audio(self, job_id: str, prev_result: Any = None):
    """
    Perform speaker diarization on transcribed audio.
    
    Supports multiple engines:
    - pyannote (default, best quality)
    - nemo (NVIDIA NeMo)
    - speechbrain
    """
    from services.database import async_session_maker
    from models.database import Job, Model, Transcript, TranscriptSegment
    from schemas.job import JobStatus
    
    async def run():
        async with async_session_maker() as session:
            result = await session.execute(select(Job).where(Job.id == job_id))
            job = result.scalar_one_or_none()
            
            if not job:
                raise ValueError(f"Job {job_id} not found")
            
            if not job.enable_diarization:
                return {"status": "skipped", "job_id": job_id}
            
            # Get diarization model
            model = None
            if job.diarization_model_id:
                result = await session.execute(
                    select(Model).where(Model.id == job.diarization_model_id)
                )
                model = result.scalar_one_or_none()
            
            # Use default if none specified
            if not model:
                result = await session.execute(
                    select(Model).where(
                        Model.model_type == "diarization",
                        Model.is_default == True,
                    )
                )
                model = result.scalar_one_or_none()
            
            if not model:
                raise ValueError("No diarization model available. Please register a model first.")
            
            # Update status
            job.status = JobStatus.DIARIZING
            job.current_stage = "diarizing"
            await session.commit()
            
            await update_progress(session, job, 50, "Starting speaker diarization...")
            
            # Get audio path
            audio_path = await get_audio_path(job.original_path)
            
            # Run diarization based on engine
            engine = model.engine
            
            if engine == ModelEngine.PYANNOTE:
                diarization = await diarize_pyannote(
                    audio_path=audio_path,
                    model_id=model.model_id,
                    device=model.device or settings.device,
                    hf_token=settings.hf_token,
                )
            elif engine == ModelEngine.NEMO:
                diarization = await diarize_nemo(
                    audio_path=audio_path,
                    model_id=model.model_id,
                )
            elif engine == ModelEngine.SPEECHBRAIN:
                diarization = await diarize_speechbrain(
                    audio_path=audio_path,
                    model_id=model.model_id,
                )
            else:
                raise ValueError(f"Unsupported diarization engine: {engine}")
            
            await update_progress(session, job, 70, "Assigning speakers to segments...")
            
            # Get transcript segments
            result = await session.execute(
                select(Transcript).where(Transcript.job_id == job_id)
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
            
            await update_progress(session, job, 80, "Diarization complete")
            
            return {"status": "diarized", "job_id": job_id, "speakers": len(speakers)}
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(run())
    finally:
        loop.close()


async def diarize_pyannote(
    audio_path: str,
    model_id: str,
    device: str,
    hf_token: str,
) -> List[Dict]:
    """Perform diarization using pyannote-audio."""
    from pyannote.audio import Pipeline
    import torch
    
    pipeline = Pipeline.from_pretrained(
        model_id,
        use_auth_token=hf_token,
    )
    
    if device == "cuda" and torch.cuda.is_available():
        pipeline = pipeline.to(torch.device("cuda"))
    
    diarization = pipeline(audio_path)
    
    # Convert to list of segments
    segments = []
    for turn, _, speaker in diarization.itertracks(yield_label=True):
        segments.append({
            "start": turn.start,
            "end": turn.end,
            "speaker": speaker,
        })
    
    return segments


async def diarize_nemo(
    audio_path: str,
    model_id: str,
) -> List[Dict]:
    """Perform diarization using NVIDIA NeMo."""
    from nemo.collections.asr.models import ClusteringDiarizer
    
    # NeMo requires a manifest file
    import json
    import tempfile
    from pathlib import Path
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump({
            "audio_filepath": audio_path,
            "offset": 0,
            "duration": None,
            "label": "infer",
            "text": "-",
        }, f)
        manifest_path = f.name
    
    config = {
        "manifest_filepath": manifest_path,
        "out_dir": str(Path(audio_path).parent / "diarization"),
    }
    
    diarizer = ClusteringDiarizer(cfg=config)
    diarizer.diarize()
    
    # Parse RTTM output
    rttm_path = Path(config["out_dir"]) / "pred_rttms" / f"{Path(audio_path).stem}.rttm"
    segments = parse_rttm(str(rttm_path))
    
    return segments


async def diarize_speechbrain(
    audio_path: str,
    model_id: str,
) -> List[Dict]:
    """Perform diarization using SpeechBrain."""
    from speechbrain.inference.speaker import SpeakerRecognition
    from speechbrain.inference.VAD import VAD
    
    # This is a simplified implementation
    # Full SpeechBrain diarization requires more setup
    vad = VAD.from_hparams(source="speechbrain/vad-crdnn-libriparty")
    
    boundaries = vad.get_speech_segments(audio_path)
    
    # For now, treat all speech as single speaker
    # Full implementation would cluster embeddings
    segments = []
    for start, end in boundaries:
        segments.append({
            "start": float(start),
            "end": float(end),
            "speaker": "SPEAKER_00",
        })
    
    return segments


def parse_rttm(rttm_path: str) -> List[Dict]:
    """Parse RTTM diarization output file."""
    segments = []
    with open(rttm_path, 'r') as f:
        for line in f:
            parts = line.strip().split()
            if parts[0] == "SPEAKER":
                start = float(parts[3])
                duration = float(parts[4])
                speaker = parts[7]
                segments.append({
                    "start": start,
                    "end": start + duration,
                    "speaker": speaker,
                })
    return segments


def find_speaker_for_segment(
    diarization: List[Dict],
    start: float,
    end: float,
) -> Optional[str]:
    """Find the dominant speaker for a transcript segment."""
    if not diarization:
        return None
    
    # Calculate overlap with each diarization segment
    speaker_times = {}
    
    for d_seg in diarization:
        overlap_start = max(start, d_seg["start"])
        overlap_end = min(end, d_seg["end"])
        overlap = max(0, overlap_end - overlap_start)
        
        if overlap > 0:
            speaker = d_seg["speaker"]
            speaker_times[speaker] = speaker_times.get(speaker, 0) + overlap
    
    if not speaker_times:
        return None
    
    # Return speaker with most overlap
    return max(speaker_times, key=speaker_times.get)


async def get_audio_path(file_path: str) -> str:
    """Get audio path, extracting from video if needed."""
    from pathlib import Path
    import subprocess
    
    path = Path(file_path)
    video_extensions = {".mp4", ".webm", ".mkv", ".mov", ".avi"}
    
    if path.suffix.lower() in video_extensions:
        audio_path = path.with_suffix(".wav")
        if not audio_path.exists():
            subprocess.run([
                "ffmpeg", "-i", str(path),
                "-vn", "-acodec", "pcm_s16le",
                "-ar", "16000", "-ac", "1",
                str(audio_path), "-y",
            ], check=True, capture_output=True)
        return str(audio_path)
    
    return file_path


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
