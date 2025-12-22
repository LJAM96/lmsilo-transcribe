"""
System evaluation and performance estimation service.

Provides:
- Hardware capability assessment
- Model compatibility analysis
- ETA predictions based on benchmarks
- Optimization recommendations
"""

import time
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
from datetime import timedelta
import logging

from .hardware import get_hardware_config, HardwareConfig, GPUInfo
from schemas.model import ModelInfo, ModelEngine, BUILTIN_MODELS

logger = logging.getLogger(__name__)


@dataclass
class PerformanceEstimate:
    """Estimated performance for a specific configuration."""
    
    realtime_factor: float  # e.g., 0.5 means 2x slower than realtime
    estimated_duration_seconds: float
    confidence: str  # "high", "medium", "low"
    bottleneck: str  # "gpu_memory", "compute", "cpu", "disk"


@dataclass
class ModelRecommendation:
    """A recommendation for better model selection."""
    
    current_model: str
    recommended_model: str
    reason: str
    expected_speedup: float
    quality_tradeoff: str  # "none", "minor", "significant"


@dataclass
class SystemEvaluation:
    """Complete system evaluation results."""
    
    # Hardware summary
    hardware_summary: str
    hardware_score: int  # 1-100
    
    # Capability checks
    can_run_gpu: bool
    gpu_memory_gb: float
    recommended_compute_type: str
    max_concurrent_jobs: int
    
    # Model compatibility
    model_compatibility: Dict[str, Dict[str, bool]]  # engine -> model -> can_run
    
    # Current configuration analysis
    performance_estimate: Optional[PerformanceEstimate]
    recommendations: List[ModelRecommendation]
    warnings: List[str]
    
    # Benchmark data (if available)
    benchmark_results: Optional[Dict[str, float]]


# Benchmark data: (model_size, device_type) -> realtime_factor
# realtime_factor of 20 means it transcribes 1 minute of audio in 3 seconds
BENCHMARK_DATA: Dict[Tuple[str, str], float] = {
    # CUDA GPU benchmarks (RTX 3080 reference)
    ("tiny", "cuda"): 50.0,
    ("base", "cuda"): 40.0,
    ("small", "cuda"): 25.0,
    ("medium", "cuda"): 12.0,
    ("large-v2", "cuda"): 6.0,
    ("large-v3", "cuda"): 6.0,
    ("large-v3-turbo", "cuda"): 15.0,
    ("distil-large-v3", "cuda"): 18.0,
    
    # CPU benchmarks (8-core reference)
    ("tiny", "cpu"): 8.0,
    ("base", "cpu"): 4.0,
    ("small", "cpu"): 1.5,
    ("medium", "cpu"): 0.4,  # Slower than realtime
    ("large-v2", "cpu"): 0.1,  # Very slow
    ("large-v3", "cpu"): 0.1,
    ("large-v3-turbo", "cpu"): 0.3,
    ("distil-large-v3", "cpu"): 0.5,
    
    # Apple MPS benchmarks (M1 Pro reference)
    ("tiny", "mps"): 30.0,
    ("base", "mps"): 20.0,
    ("small", "mps"): 12.0,
    ("medium", "mps"): 5.0,
    ("large-v2", "mps"): 2.5,
    ("large-v3", "mps"): 2.5,
    ("large-v3-turbo", "mps"): 6.0,
    ("distil-large-v3", "mps"): 8.0,
}

# VRAM requirements in GB
MODEL_VRAM_REQUIREMENTS: Dict[str, float] = {
    "tiny": 1.0,
    "base": 1.5,
    "small": 2.5,
    "medium": 5.0,
    "large-v2": 10.0,
    "large-v3": 10.0,
    "large-v3-turbo": 6.0,
    "distil-large-v3": 4.0,
}

# Diarization VRAM requirements
DIARIZATION_VRAM: Dict[str, float] = {
    "pyannote/speaker-diarization-3.1": 4.0,
    "pyannote/speaker-diarization-3.0": 4.0,
}

# TTS VRAM requirements
TTS_VRAM: Dict[str, float] = {
    "coqui-xtts": 6.0,
    "coqui-vits": 2.0,
    "piper": 0.5,
    "bark": 8.0,
    "tortoise": 12.0,
    "mars5": 8.0,
}


def evaluate_system(
    stt_model: Optional[str] = None,
    diarization_model: Optional[str] = None,
    tts_model: Optional[str] = None,
    audio_duration_seconds: Optional[float] = None,
) -> SystemEvaluation:
    """
    Evaluate system capabilities and provide recommendations.
    
    Args:
        stt_model: Selected STT model (e.g., "large-v3")
        diarization_model: Selected diarization model
        tts_model: Selected TTS engine (e.g., "coqui-xtts")
        audio_duration_seconds: Duration of audio to process (for ETA)
    
    Returns:
        Complete system evaluation with recommendations
    """
    config = get_hardware_config()
    
    # Calculate hardware score
    hardware_score = calculate_hardware_score(config)
    
    # Build hardware summary
    hardware_summary = build_hardware_summary(config)
    
    # Check GPU availability
    can_run_gpu = len(config.gpus) > 0
    gpu_memory_gb = max((gpu.memory_gb for gpu in config.gpus), default=0)
    
    # Calculate max concurrent jobs
    max_concurrent = calculate_max_concurrent(config)
    
    # Check model compatibility
    model_compatibility = check_model_compatibility(config)
    
    # Analyze current selection
    warnings = []
    recommendations = []
    performance_estimate = None
    
    if stt_model:
        # Check if model can run
        vram_needed = get_total_vram_needed(stt_model, diarization_model, tts_model)
        
        if not can_run_gpu:
            if stt_model in ["large-v2", "large-v3", "medium"]:
                warnings.append(
                    f"⚠️ Running {stt_model} on CPU will be very slow. "
                    f"Estimated speed: {BENCHMARK_DATA.get((stt_model, 'cpu'), 0.1):.1f}x realtime."
                )
                recommendations.append(ModelRecommendation(
                    current_model=stt_model,
                    recommended_model="distil-large-v3" if stt_model.startswith("large") else "small",
                    reason="Much faster on CPU with minimal quality loss",
                    expected_speedup=5.0,
                    quality_tradeoff="minor",
                ))
        elif vram_needed > gpu_memory_gb:
            warnings.append(
                f"⚠️ Total VRAM needed ({vram_needed:.1f}GB) exceeds available ({gpu_memory_gb:.1f}GB). "
                f"Some models may be swapped to RAM, causing slowdowns."
            )
            recommendations.append(ModelRecommendation(
                current_model=stt_model,
                recommended_model="large-v3-turbo" if stt_model == "large-v3" else "small",
                reason=f"Fits within your {gpu_memory_gb:.0f}GB VRAM",
                expected_speedup=2.0,
                quality_tradeoff="minor" if "turbo" in stt_model else "minor",
            ))
        
        # Calculate performance estimate
        if audio_duration_seconds:
            performance_estimate = estimate_performance(
                config=config,
                stt_model=stt_model,
                diarization_model=diarization_model,
                tts_model=tts_model,
                audio_duration=audio_duration_seconds,
            )
    
    # Additional recommendations based on hardware
    if can_run_gpu and config.recommended_compute_type == "float16":
        if not any(r.current_model for r in recommendations):
            pass  # Already optimal
    elif not can_run_gpu and config.cpu_threads < 8:
        warnings.append(
            f"💡 Your CPU has {config.cpu_threads} threads. Consider using smaller models "
            f"(tiny, base, small) for acceptable performance."
        )
    
    return SystemEvaluation(
        hardware_summary=hardware_summary,
        hardware_score=hardware_score,
        can_run_gpu=can_run_gpu,
        gpu_memory_gb=gpu_memory_gb,
        recommended_compute_type=config.recommended_compute_type,
        max_concurrent_jobs=max_concurrent,
        model_compatibility=model_compatibility,
        performance_estimate=performance_estimate,
        recommendations=recommendations,
        warnings=warnings,
        benchmark_results=None,
    )


def calculate_hardware_score(config: HardwareConfig) -> int:
    """Calculate a 1-100 hardware score."""
    score = 0
    
    # GPU contribution (up to 60 points)
    if config.gpus:
        best_gpu = max(config.gpus, key=lambda g: g.memory_gb)
        if best_gpu.memory_gb >= 24:
            score += 60
        elif best_gpu.memory_gb >= 16:
            score += 50
        elif best_gpu.memory_gb >= 12:
            score += 40
        elif best_gpu.memory_gb >= 8:
            score += 30
        elif best_gpu.memory_gb >= 6:
            score += 20
        else:
            score += 10
    
    # CPU contribution (up to 25 points)
    if config.cpu_threads >= 32:
        score += 25
    elif config.cpu_threads >= 16:
        score += 20
    elif config.cpu_threads >= 8:
        score += 15
    elif config.cpu_threads >= 4:
        score += 10
    else:
        score += 5
    
    # RAM contribution (up to 15 points)
    if config.ram_gb >= 64:
        score += 15
    elif config.ram_gb >= 32:
        score += 12
    elif config.ram_gb >= 16:
        score += 8
    else:
        score += 4
    
    return min(100, score)


def build_hardware_summary(config: HardwareConfig) -> str:
    """Build a human-readable hardware summary."""
    parts = []
    
    if config.gpus:
        gpu_names = [g.name for g in config.gpus]
        parts.append(f"GPU: {', '.join(gpu_names)}")
        parts.append(f"VRAM: {max(g.memory_gb for g in config.gpus):.0f}GB")
    else:
        parts.append("GPU: None detected")
    
    parts.append(f"CPU: {config.cpu_cores} cores ({config.cpu_threads} threads)")
    parts.append(f"RAM: {config.ram_gb:.0f}GB")
    parts.append(f"Device: {config.preferred_device}")
    
    return " • ".join(parts)


def calculate_max_concurrent(config: HardwareConfig) -> int:
    """Calculate maximum concurrent jobs based on hardware."""
    if not config.gpus:
        # CPU: limited by cores
        return max(1, config.cpu_threads // 8)
    
    # GPU: limited by VRAM (assume medium model ~5GB each)
    total_vram = sum(g.memory_gb for g in config.gpus)
    return max(1, int(total_vram // 5))


def check_model_compatibility(config: HardwareConfig) -> Dict[str, Dict[str, bool]]:
    """Check which models can run on this hardware."""
    compatibility = {}
    
    gpu_memory = max((g.memory_gb for g in config.gpus), default=0)
    
    # Whisper models
    compatibility["whisper"] = {}
    for model_name, vram in MODEL_VRAM_REQUIREMENTS.items():
        if config.gpus:
            can_run = vram <= gpu_memory
        else:
            # CPU can run anything, just slowly
            can_run = True
        compatibility["whisper"][model_name] = can_run
    
    # Diarization
    compatibility["diarization"] = {}
    for model_name, vram in DIARIZATION_VRAM.items():
        compatibility["diarization"][model_name] = config.gpus and vram <= gpu_memory
    
    # TTS
    compatibility["tts"] = {}
    for engine, vram in TTS_VRAM.items():
        if config.gpus:
            can_run = vram <= gpu_memory
        else:
            can_run = engine in ["piper", "coqui-vits"]  # CPU-friendly
        compatibility["tts"][engine] = can_run
    
    return compatibility


def get_total_vram_needed(
    stt_model: Optional[str],
    diarization_model: Optional[str],
    tts_model: Optional[str],
) -> float:
    """Calculate total VRAM needed for all models."""
    total = 0
    
    if stt_model:
        # Extract base model name
        base_name = stt_model.split("/")[-1].replace("faster-whisper-", "")
        total += MODEL_VRAM_REQUIREMENTS.get(base_name, 5.0)
    
    if diarization_model:
        total += DIARIZATION_VRAM.get(diarization_model, 4.0)
    
    if tts_model:
        total += TTS_VRAM.get(tts_model, 4.0)
    
    return total


def estimate_performance(
    config: HardwareConfig,
    stt_model: str,
    diarization_model: Optional[str],
    tts_model: Optional[str],
    audio_duration: float,
) -> PerformanceEstimate:
    """
    Estimate processing time for a job.
    """
    device = config.preferred_device
    if device == "rocm":
        device = "cuda"  # Similar performance
    
    # Get base model name
    base_model = stt_model.split("/")[-1].replace("faster-whisper-", "")
    
    # Get STT benchmark
    stt_rtf = BENCHMARK_DATA.get((base_model, device), BENCHMARK_DATA.get((base_model, "cpu"), 0.5))
    
    # Adjust for hardware differences
    if device == "cuda" and config.gpus:
        best_gpu = max(config.gpus, key=lambda g: g.memory_gb)
        # Adjust based on GPU memory (reference is 10GB)
        memory_factor = min(2.0, best_gpu.memory_gb / 10)
        stt_rtf *= memory_factor
    
    if device == "cpu":
        # Adjust for CPU cores (reference is 8)
        core_factor = config.cpu_threads / 8
        stt_rtf *= min(2.0, core_factor)
    
    # Calculate STT time
    stt_time = audio_duration / stt_rtf
    
    # Add diarization time (roughly 0.3x realtime on GPU)
    diarization_time = 0
    if diarization_model:
        if config.gpus:
            diarization_time = audio_duration * 0.3
        else:
            diarization_time = audio_duration * 2.0  # Much slower on CPU
    
    # Add TTS time (roughly 0.5-2x of output duration)
    tts_time = 0
    if tts_model:
        if tts_model == "piper":
            tts_time = audio_duration * 0.1  # Very fast
        elif tts_model == "coqui-xtts":
            tts_time = audio_duration * 0.5 if config.gpus else audio_duration * 3
        elif tts_model == "tortoise":
            tts_time = audio_duration * 5  # Slow but high quality
        else:
            tts_time = audio_duration * 1.0
    
    total_time = stt_time + diarization_time + tts_time
    
    # Determine bottleneck
    if not config.gpus:
        bottleneck = "cpu"
    elif stt_time > diarization_time and stt_time > tts_time:
        bottleneck = "compute"
    else:
        bottleneck = "gpu_memory" if tts_model else "compute"
    
    # Confidence based on benchmark availability
    if (base_model, device) in BENCHMARK_DATA:
        confidence = "high"
    elif device == "cpu":
        confidence = "medium"
    else:
        confidence = "low"
    
    return PerformanceEstimate(
        realtime_factor=audio_duration / total_time if total_time > 0 else 1.0,
        estimated_duration_seconds=total_time,
        confidence=confidence,
        bottleneck=bottleneck,
    )


def format_eta(seconds: float) -> str:
    """Format seconds into human-readable ETA."""
    if seconds < 60:
        return f"{int(seconds)}s"
    elif seconds < 3600:
        return f"{int(seconds // 60)}m {int(seconds % 60)}s"
    else:
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        return f"{hours}h {minutes}m"
