"""Speech-to-Text worker with pluggable engine support - OPTIMIZED VERSION."""

import asyncio
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional

from sqlalchemy import select

from .celery_app import celery_app
from config import settings
from schemas.model import ModelEngine

logger = logging.getLogger(__name__)

# Use model manager with idle timeout
from services.model_manager import get_whisper_model as get_cached_faster_whisper


def get_cached_whisperx(model_id: str, device: str):
    """Get or create cached whisperx model."""
    cache_key = f"whisperx:{model_id}:{device}"
    
    if cache_key not in _model_cache:
        import whisperx
        
        logger.info(f"Loading WhisperX model: {model_id} (device={device})")
        _model_cache[cache_key] = whisperx.load_model(model_id, device=device)
        logger.info(f"WhisperX model {model_id} loaded and cached")
    
    return _model_cache[cache_key]


def get_cached_openai_whisper(model_id: str):
    """Get or create cached OpenAI whisper model."""
    cache_key = f"openai_whisper:{model_id}"
    
    if cache_key not in _model_cache:
        import whisper
        
        logger.info(f"Loading OpenAI Whisper model: {model_id}")
        _model_cache[cache_key] = whisper.load_model(model_id)
        logger.info(f"OpenAI Whisper model {model_id} loaded and cached")
    
    return _model_cache[cache_key]


def get_cached_hf_pipeline(model_id: str):
    """Get or create cached HuggingFace pipeline."""
    cache_key = f"hf_whisper:{model_id}"
    
    if cache_key not in _model_cache:
        from transformers import pipeline
        
        logger.info(f"Loading HuggingFace pipeline: {model_id}")
        _model_cache[cache_key] = pipeline(
            "automatic-speech-recognition",
            model=model_id,
            return_timestamps="word",
        )
        logger.info(f"HuggingFace pipeline {model_id} loaded and cached")
    
    return _model_cache[cache_key]


@celery_app.task(bind=True, name="workers.stt_worker.transcribe_audio")
def transcribe_audio(self, job_id: str, prev_result: Any = None):
    """
    Transcribe audio using the configured STT engine.
    
    OPTIMIZED: Models are cached per worker process for faster subsequent jobs.
    
    Supports multiple engines:
    - faster-whisper (default, fastest)
    - whisperx (with alignment)
    - openai-whisper (original)
    - huggingface-whisper (transformers)
    """
    from services.database import async_session_maker
    from models.database import Job, Model, Transcript, TranscriptSegment
    from schemas.job import JobStatus
    
    async def run():
        async with async_session_maker() as session:
            # Get job and model
            result = await session.execute(select(Job).where(Job.id == job_id))
            job = result.scalar_one_or_none()
            
            if not job:
                raise ValueError(f"Job {job_id} not found")
            
            # Get STT model
            model = None
            if job.model_id:
                result = await session.execute(
                    select(Model).where(Model.id == job.model_id)
                )
                model = result.scalar_one_or_none()
            
            # Use default model if none specified
            if not model:
                result = await session.execute(
                    select(Model).where(
                        Model.model_type == "whisper",
                        Model.is_default == True,
                    )
                )
                model = result.scalar_one_or_none()
            
            if not model:
                raise ValueError("No STT model available. Please register a model first.")
            
            # Update status
            job.status = JobStatus.TRANSCRIBING
            job.current_stage = "transcribing"
            await session.commit()
            
            # Notify progress
            await update_progress(session, job, 10, "Starting transcription...")
            
            # Extract audio if video
            audio_path = await extract_audio_if_needed(job.original_path)
            
            # Run transcription based on engine (with cached models)
            engine = model.engine
            
            if engine == ModelEngine.FASTER_WHISPER:
                segments, info = await transcribe_faster_whisper(
                    audio_path=audio_path,
                    model_id=model.model_id,
                    language=job.language if job.language != "auto" else None,
                    compute_type=model.compute_type or settings.compute_type,
                    device=model.device or settings.device,
                    progress_callback=lambda p: update_progress_sync(session, job, 10 + p * 0.7),
                )
            elif engine == ModelEngine.WHISPERX:
                segments, info = await transcribe_whisperx(
                    audio_path=audio_path,
                    model_id=model.model_id,
                    language=job.language if job.language != "auto" else None,
                    device=model.device or settings.device,
                    progress_callback=lambda p: update_progress_sync(session, job, 10 + p * 0.7),
                )
            elif engine == ModelEngine.OPENAI_WHISPER:
                segments, info = await transcribe_openai_whisper(
                    audio_path=audio_path,
                    model_id=model.model_id,
                    language=job.language if job.language != "auto" else None,
                )
            elif engine == ModelEngine.HUGGINGFACE_WHISPER:
                segments, info = await transcribe_hf_whisper(
                    audio_path=audio_path,
                    model_id=model.model_id,
                    language=job.language if job.language != "auto" else None,
                )
            else:
                raise ValueError(f"Unsupported STT engine: {engine}")
            
            # Save transcript to database
            await update_progress(session, job, 85, "Saving transcript...")
            
            transcript = Transcript(
                job_id=job_id,
                language=info.get("language", job.language),
                duration=info.get("duration", 0),
                word_count=sum(len(seg["text"].split()) for seg in segments),
                full_text=" ".join(seg["text"] for seg in segments),
            )
            session.add(transcript)
            await session.commit()
            await session.refresh(transcript)
            
            # Save segments in batch (reduced commits)
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
            
            # Single commit for all segments
            await session.commit()
            
            # Update job
            job.detected_language = info.get("language")
            job.duration = info.get("duration")
            job.progress = 90
            
            # Generate output files
            output_dir = settings.output_dir / job_id
            output_dir.mkdir(parents=True, exist_ok=True)
            
            await generate_output_files(segments, output_dir, job.output_formats)
            
            job.transcript_path = str(output_dir / "transcript.json")
            await session.commit()
            
            await update_progress(session, job, 95, "Transcription complete")
            
            return {"status": "transcribed", "job_id": job_id}
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(run())
    finally:
        loop.close()


async def transcribe_faster_whisper(
    audio_path: str,
    model_id: str,
    language: Optional[str],
    compute_type: str,
    device: str,
    task: str = "transcribe",
    progress_callback=None,
) -> tuple[List[Dict], Dict]:
    """Transcribe using faster-whisper with cached model."""
    # Use cached model
    model = get_cached_faster_whisper(model_id, device, compute_type)
    
    segments_iter, info = model.transcribe(
        audio_path,
        language=language,
        task=task,
        word_timestamps=True,
        vad_filter=True,  # Voice activity detection for efficiency
        vad_parameters=dict(
            min_silence_duration_ms=500,  # Skip long silences
        ),
        beam_size=5,
        best_of=5,
    )
    
    segments = []
    for seg in segments_iter:
        segments.append({
            "start": seg.start,
            "end": seg.end,
            "text": seg.text.strip(),
            "confidence": seg.avg_logprob,
            "words": [
                {"word": w.word, "start": w.start, "end": w.end, "probability": w.probability}
                for w in (seg.words or [])
            ],
        })
        if progress_callback:
            progress = min(seg.end / (info.duration or 1) * 100, 100)
            progress_callback(progress)
    
    return segments, {
        "language": info.language,
        "duration": info.duration,
        "language_probability": info.language_probability,
    }


async def transcribe_whisperx(
    audio_path: str,
    model_id: str,
    language: Optional[str],
    device: str,
    progress_callback=None,
) -> tuple[List[Dict], Dict]:
    """Transcribe using WhisperX with word alignment and cached model."""
    import whisperx
    
    # Use cached model
    model = get_cached_whisperx(model_id, device)
    
    # Load audio
    audio = whisperx.load_audio(audio_path)
    
    # Transcribe
    result = model.transcribe(audio, language=language)
    
    if progress_callback:
        progress_callback(50)
    
    # Align (alignment model not cached as it varies by language)
    model_a, metadata = whisperx.load_align_model(
        language_code=result["language"],
        device=device,
    )
    result = whisperx.align(
        result["segments"],
        model_a,
        metadata,
        audio,
        device,
    )
    
    if progress_callback:
        progress_callback(100)
    
    segments = []
    for seg in result["segments"]:
        segments.append({
            "start": seg["start"],
            "end": seg["end"],
            "text": seg["text"].strip(),
            "words": seg.get("words", []),
        })
    
    duration = len(audio) / 16000
    
    return segments, {
        "language": result.get("language", language),
        "duration": duration,
    }


async def transcribe_openai_whisper(
    audio_path: str,
    model_id: str,
    language: Optional[str],
) -> tuple[List[Dict], Dict]:
    """Transcribe using original OpenAI Whisper with cached model."""
    # Use cached model
    model = get_cached_openai_whisper(model_id)
    result = model.transcribe(audio_path, language=language, word_timestamps=True)
    
    segments = []
    for seg in result["segments"]:
        segments.append({
            "start": seg["start"],
            "end": seg["end"],
            "text": seg["text"].strip(),
            "words": seg.get("words", []),
        })
    
    return segments, {
        "language": result.get("language"),
        "duration": result["segments"][-1]["end"] if result["segments"] else 0,
    }


async def transcribe_hf_whisper(
    audio_path: str,
    model_id: str,
    language: Optional[str],
) -> tuple[List[Dict], Dict]:
    """Transcribe using HuggingFace Transformers Whisper with cached pipeline."""
    import librosa
    
    # Use cached pipeline
    pipe = get_cached_hf_pipeline(model_id)
    
    audio, sr = librosa.load(audio_path, sr=16000)
    result = pipe(audio)
    
    segments = [{
        "start": 0,
        "end": len(audio) / sr,
        "text": result["text"],
        "words": result.get("chunks", []),
    }]
    
    return segments, {
        "language": language,
        "duration": len(audio) / sr,
    }


async def extract_audio_if_needed(file_path: str) -> str:
    """Extract audio from video if needed."""
    import subprocess
    from pathlib import Path
    
    path = Path(file_path)
    video_extensions = {".mp4", ".webm", ".mkv", ".mov", ".avi", ".mpeg"}
    
    if path.suffix.lower() not in video_extensions:
        return file_path
    
    audio_path = path.with_suffix(".wav")
    
    if not audio_path.exists():
        subprocess.run([
            "ffmpeg", "-i", str(path),
            "-vn", "-acodec", "pcm_s16le",
            "-ar", "16000", "-ac", "1",
            str(audio_path), "-y",
        ], check=True, capture_output=True)
    
    return str(audio_path)


async def update_progress(session, job, progress: float, message: str = ""):
    """Update job progress and notify clients."""
    job.progress = progress
    if message:
        job.current_stage = message
    await session.commit()
    
    try:
        from api.queue import manager
        await manager.broadcast({
            "type": "progress",
            "job_id": job.id,
            "progress": progress,
            "message": message,
        })
    except Exception:
        pass  # WebSocket notification is optional


def update_progress_sync(session, job, progress: float):
    """Sync version of progress update for callbacks."""
    import asyncio
    loop = asyncio.get_event_loop()
    loop.run_until_complete(update_progress(session, job, progress))


async def generate_output_files(segments: List[Dict], output_dir: Path, formats: List[str]):
    """Generate transcript in requested formats."""
    import json
    
    if "json" in formats:
        with open(output_dir / "transcript.json", "w") as f:
            json.dump({"segments": segments}, f, indent=2)
    
    if "srt" in formats:
        srt = generate_srt(segments)
        with open(output_dir / "subtitles.srt", "w") as f:
            f.write(srt)
    
    if "vtt" in formats:
        vtt = generate_vtt(segments)
        with open(output_dir / "subtitles.vtt", "w") as f:
            f.write(vtt)
    
    if "txt" in formats:
        txt = "\n".join(seg["text"] for seg in segments)
        with open(output_dir / "transcript.txt", "w") as f:
            f.write(txt)


def generate_srt(segments: List[Dict]) -> str:
    """Generate SRT format."""
    lines = []
    for i, seg in enumerate(segments, 1):
        start = format_srt_time(seg["start"])
        end = format_srt_time(seg["end"])
        lines.append(f"{i}\n{start} --> {end}\n{seg['text']}\n")
    return "\n".join(lines)


def generate_vtt(segments: List[Dict]) -> str:
    """Generate WebVTT format."""
    lines = ["WEBVTT\n"]
    for seg in segments:
        start = format_vtt_time(seg["start"])
        end = format_vtt_time(seg["end"])
        lines.append(f"\n{start} --> {end}\n{seg['text']}")
    return "\n".join(lines)


def format_srt_time(seconds: float) -> str:
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds % 1) * 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def format_vtt_time(seconds: float) -> str:
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds % 1) * 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}.{millis:03d}"
