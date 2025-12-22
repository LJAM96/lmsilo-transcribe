"""Text-to-Speech worker with pluggable engine support."""

import asyncio
from pathlib import Path
from typing import Dict, Any, List, Optional
from sqlalchemy import select

from .celery_app import celery_app
from config import settings
from schemas.model import ModelEngine


@celery_app.task(bind=True, name="workers.tts_worker.synthesize_speech")
def synthesize_speech(self, job_id: str, prev_result: Any = None):
    """
    Synthesize speech from transcript.
    
    Supports multiple engines:
    - coqui-xtts (multilingual, voice cloning)
    - coqui-vits (fast, good quality)
    - piper (very fast, lightweight)
    - mars5 (high quality, natural prosody)
    - bark (expressive, with sound effects)
    - tortoise (highest quality, slow)
    """
    from services.database import async_session_maker
    from models.database import Job, Model, Transcript, TranscriptSegment, TTSOutput
    from schemas.job import JobStatus
    
    async def run():
        async with async_session_maker() as session:
            result = await session.execute(select(Job).where(Job.id == job_id))
            job = result.scalar_one_or_none()
            
            if not job:
                raise ValueError(f"Job {job_id} not found")
            
            if not job.enable_tts:
                return {"status": "skipped", "job_id": job_id}
            
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
                raise ValueError("No TTS model available. Please register a model first.")
            
            # Update status
            job.status = JobStatus.SYNTHESIZING
            job.current_stage = "synthesizing"
            await session.commit()
            
            await update_progress(session, job, 60, "Starting speech synthesis...")
            
            # Get transcript segments
            result = await session.execute(
                select(Transcript).where(Transcript.job_id == job_id)
            )
            transcript = result.scalar_one_or_none()
            
            if not transcript:
                raise ValueError("No transcript found for TTS")
            
            result = await session.execute(
                select(TranscriptSegment)
                .where(TranscriptSegment.transcript_id == transcript.id)
                .order_by(TranscriptSegment.segment_index)
            )
            segments = result.scalars().all()
            
            # Prepare output directory
            output_dir = settings.output_dir / job_id
            output_dir.mkdir(parents=True, exist_ok=True)
            
            # Run TTS based on engine
            engine = model.engine
            
            if engine == ModelEngine.COQUI_XTTS:
                audio_segments = await synthesize_coqui_xtts(
                    segments=segments,
                    model_id=model.model_id,
                    language=job.detected_language or job.language,
                    output_dir=output_dir,
                    device=model.device or settings.device,
                )
            elif engine == ModelEngine.COQUI_VITS:
                audio_segments = await synthesize_coqui_vits(
                    segments=segments,
                    model_id=model.model_id,
                    output_dir=output_dir,
                )
            elif engine == ModelEngine.PIPER:
                audio_segments = await synthesize_piper(
                    segments=segments,
                    model_id=model.model_id,
                    output_dir=output_dir,
                )
            elif engine == ModelEngine.MARS5:
                audio_segments = await synthesize_mars5(
                    segments=segments,
                    model_id=model.model_id,
                    output_dir=output_dir,
                )
            elif engine == ModelEngine.BARK:
                audio_segments = await synthesize_bark(
                    segments=segments,
                    output_dir=output_dir,
                )
            elif engine == ModelEngine.TORTOISE:
                audio_segments = await synthesize_tortoise(
                    segments=segments,
                    output_dir=output_dir,
                )
            else:
                raise ValueError(f"Unsupported TTS engine: {engine}")
            
            await update_progress(session, job, 85, "Combining audio segments...")
            
            # Combine all audio segments
            combined_path = output_dir / "tts_output.wav"
            await combine_audio_segments(audio_segments, combined_path)
            
            # Save TTS output record
            import wave
            with wave.open(str(combined_path), 'r') as wav:
                duration = wav.getnframes() / wav.getframerate()
                sample_rate = wav.getframerate()
            
            tts_output = TTSOutput(
                job_id=job_id,
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
            
            await update_progress(session, job, 90, "TTS synthesis complete")
            
            return {
                "status": "synthesized",
                "job_id": job_id,
                "audio_path": str(combined_path),
                "duration": duration,
            }
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(run())
    finally:
        loop.close()


async def synthesize_coqui_xtts(
    segments: List,
    model_id: str,
    language: str,
    output_dir: Path,
    device: str,
) -> List[Dict]:
    """Synthesize using Coqui XTTS v2."""
    from TTS.api import TTS
    import torch
    
    tts = TTS(model_id)
    if device == "cuda" and torch.cuda.is_available():
        tts = tts.to("cuda")
    
    audio_segments = []
    
    for i, seg in enumerate(segments):
        output_path = output_dir / f"segment_{i:04d}.wav"
        
        # XTTS supports multiple languages
        lang = language[:2] if language else "en"
        
        tts.tts_to_file(
            text=seg.text,
            file_path=str(output_path),
            language=lang,
        )
        
        audio_segments.append({
            "path": str(output_path),
            "original_start": seg.start_time,
            "original_end": seg.end_time,
            "text": seg.text,
        })
    
    return audio_segments


async def synthesize_coqui_vits(
    segments: List,
    model_id: str,
    output_dir: Path,
) -> List[Dict]:
    """Synthesize using Coqui VITS."""
    from TTS.api import TTS
    
    tts = TTS(model_id)
    audio_segments = []
    
    for i, seg in enumerate(segments):
        output_path = output_dir / f"segment_{i:04d}.wav"
        tts.tts_to_file(text=seg.text, file_path=str(output_path))
        
        audio_segments.append({
            "path": str(output_path),
            "original_start": seg.start_time,
            "original_end": seg.end_time,
            "text": seg.text,
        })
    
    return audio_segments


async def synthesize_piper(
    segments: List,
    model_id: str,
    output_dir: Path,
) -> List[Dict]:
    """Synthesize using Piper TTS."""
    import subprocess
    
    audio_segments = []
    
    for i, seg in enumerate(segments):
        output_path = output_dir / f"segment_{i:04d}.wav"
        
        # Piper uses command line
        process = subprocess.run(
            ["piper", "--model", model_id, "--output_file", str(output_path)],
            input=seg.text,
            capture_output=True,
            text=True,
        )
        
        if process.returncode != 0:
            raise RuntimeError(f"Piper failed: {process.stderr}")
        
        audio_segments.append({
            "path": str(output_path),
            "original_start": seg.start_time,
            "original_end": seg.end_time,
            "text": seg.text,
        })
    
    return audio_segments


async def synthesize_mars5(
    segments: List,
    model_id: str,
    output_dir: Path,
) -> List[Dict]:
    """Synthesize using MARS5 TTS."""
    import torch
    from mars5.ar_generate import ar_generate
    from mars5.nar_generate import nar_generate
    
    # Load model
    device = "cuda" if torch.cuda.is_available() else "cpu"
    
    audio_segments = []
    
    for i, seg in enumerate(segments):
        output_path = output_dir / f"segment_{i:04d}.wav"
        
        # MARS5 generation
        # Note: Simplified - actual implementation needs proper model loading
        text = seg.text
        
        # Generate using AR model
        ar_output = ar_generate(text)
        # Refine with NAR model
        wav = nar_generate(ar_output)
        
        # Save
        import soundfile as sf
        sf.write(str(output_path), wav, 24000)
        
        audio_segments.append({
            "path": str(output_path),
            "original_start": seg.start_time,
            "original_end": seg.end_time,
            "text": seg.text,
        })
    
    return audio_segments


async def synthesize_bark(
    segments: List,
    output_dir: Path,
) -> List[Dict]:
    """Synthesize using Bark."""
    from bark import SAMPLE_RATE, generate_audio, preload_models
    from scipy.io.wavfile import write as write_wav
    
    preload_models()
    
    audio_segments = []
    
    for i, seg in enumerate(segments):
        output_path = output_dir / f"segment_{i:04d}.wav"
        
        audio_array = generate_audio(seg.text)
        write_wav(str(output_path), SAMPLE_RATE, audio_array)
        
        audio_segments.append({
            "path": str(output_path),
            "original_start": seg.start_time,
            "original_end": seg.end_time,
            "text": seg.text,
        })
    
    return audio_segments


async def synthesize_tortoise(
    segments: List,
    output_dir: Path,
) -> List[Dict]:
    """Synthesize using Tortoise TTS."""
    from tortoise.api import TextToSpeech
    from tortoise.utils.audio import load_audio
    import torchaudio
    
    tts = TextToSpeech()
    
    audio_segments = []
    
    for i, seg in enumerate(segments):
        output_path = output_dir / f"segment_{i:04d}.wav"
        
        # Tortoise is slow but high quality
        gen = tts.tts(seg.text, voice="random")
        torchaudio.save(str(output_path), gen.squeeze(0).cpu(), 24000)
        
        audio_segments.append({
            "path": str(output_path),
            "original_start": seg.start_time,
            "original_end": seg.end_time,
            "text": seg.text,
        })
    
    return audio_segments


async def combine_audio_segments(segments: List[Dict], output_path: Path):
    """Combine multiple audio segments into one file."""
    import subprocess
    
    # Create concat file for ffmpeg
    concat_path = output_path.parent / "concat.txt"
    with open(concat_path, "w") as f:
        for seg in segments:
            f.write(f"file '{seg['path']}'\n")
    
    # Concatenate using ffmpeg
    subprocess.run([
        "ffmpeg", "-f", "concat", "-safe", "0",
        "-i", str(concat_path),
        "-acodec", "pcm_s16le",
        str(output_path), "-y",
    ], check=True, capture_output=True)
    
    # Cleanup
    concat_path.unlink()


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
