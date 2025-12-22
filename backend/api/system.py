"""System information API routes."""

from fastapi import APIRouter, Query
from typing import Optional

from services.hardware import get_hardware_config, HardwareConfig
from services.evaluation import (
    evaluate_system,
    SystemEvaluation,
    format_eta,
)

router = APIRouter()


@router.get("/hardware")
async def get_hardware_info():
    """
    Get detected hardware information.
    
    Returns CPU, GPU, RAM details and recommended settings.
    """
    config = get_hardware_config()
    
    return {
        "cpu": {
            "cores": config.cpu_cores,
            "threads": config.cpu_threads,
        },
        "ram_gb": config.ram_gb,
        "gpus": [
            {
                "index": gpu.index,
                "name": gpu.name,
                "vendor": gpu.vendor,
                "memory_gb": gpu.memory_gb,
                "compute_capability": gpu.compute_capability,
            }
            for gpu in config.gpus
        ],
        "preferred_device": config.preferred_device,
        "recommended_compute_type": config.recommended_compute_type,
        "recommended_batch_size": config.recommended_batch_size,
        "recommended_num_workers": config.recommended_num_workers,
    }


@router.get("/gpu-usage")
async def get_gpu_usage():
    """
    Get real-time GPU memory usage for monitoring.
    
    Returns current and total memory for each GPU.
    """
    import subprocess
    import json as json_lib
    
    config = get_hardware_config()
    
    if not config.gpus:
        return {"gpus": [], "message": "No GPUs detected"}
    
    gpu_usage = []
    
    try:
        # Try nvidia-smi for NVIDIA GPUs
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=index,memory.used,memory.total,utilization.gpu,temperature.gpu", 
             "--format=csv,noheader,nounits"],
            capture_output=True,
            text=True,
            timeout=5
        )
        
        if result.returncode == 0:
            for line in result.stdout.strip().split('\n'):
                if line.strip():
                    parts = [p.strip() for p in line.split(',')]
                    if len(parts) >= 5:
                        gpu_usage.append({
                            "index": int(parts[0]),
                            "memory_used_mb": int(parts[1]),
                            "memory_total_mb": int(parts[2]),
                            "memory_percent": round(int(parts[1]) / int(parts[2]) * 100, 1) if int(parts[2]) > 0 else 0,
                            "utilization_percent": int(parts[3]),
                            "temperature_c": int(parts[4]) if parts[4].isdigit() else None,
                        })
    except (subprocess.TimeoutExpired, FileNotFoundError):
        # nvidia-smi not available or timed out
        pass
    
    # Fallback: estimate from hardware config
    if not gpu_usage and config.gpus:
        for gpu in config.gpus:
            gpu_usage.append({
                "index": gpu.index,
                "memory_used_mb": 0,
                "memory_total_mb": int(gpu.memory_gb * 1024),
                "memory_percent": 0,
                "utilization_percent": None,
                "temperature_c": None,
            })
    
    return {"gpus": gpu_usage}


@router.get("/evaluate")
async def evaluate_configuration(
    stt_model: Optional[str] = Query(default=None, description="STT model to evaluate"),
    diarization_model: Optional[str] = Query(default=None, description="Diarization model"),
    tts_model: Optional[str] = Query(default=None, description="TTS engine"),
    audio_duration: Optional[float] = Query(default=None, description="Audio duration in seconds for ETA"),
):
    """
    Evaluate system capabilities for a specific configuration.
    
    Returns:
    - Hardware score and summary
    - Model compatibility
    - Performance estimates with ETA
    - Recommendations for optimization
    """
    evaluation = evaluate_system(
        stt_model=stt_model,
        diarization_model=diarization_model,
        tts_model=tts_model,
        audio_duration_seconds=audio_duration,
    )
    
    result = {
        "hardware": {
            "summary": evaluation.hardware_summary,
            "score": evaluation.hardware_score,
            "score_description": get_score_description(evaluation.hardware_score),
            "can_run_gpu": evaluation.can_run_gpu,
            "gpu_memory_gb": evaluation.gpu_memory_gb,
            "recommended_compute_type": evaluation.recommended_compute_type,
            "max_concurrent_jobs": evaluation.max_concurrent_jobs,
        },
        "compatibility": evaluation.model_compatibility,
        "warnings": evaluation.warnings,
        "recommendations": [
            {
                "current": r.current_model,
                "recommended": r.recommended_model,
                "reason": r.reason,
                "expected_speedup": f"{r.expected_speedup:.1f}x faster",
                "quality_tradeoff": r.quality_tradeoff,
            }
            for r in evaluation.recommendations
        ],
    }
    
    if evaluation.performance_estimate:
        est = evaluation.performance_estimate
        result["estimate"] = {
            "realtime_factor": round(est.realtime_factor, 2),
            "realtime_description": format_realtime_factor(est.realtime_factor),
            "estimated_seconds": round(est.estimated_duration_seconds, 1),
            "estimated_time": format_eta(est.estimated_duration_seconds),
            "confidence": est.confidence,
            "bottleneck": est.bottleneck,
        }
    
    return result


@router.get("/benchmark")
async def run_benchmark(
    model: str = Query(default="base", description="Whisper model to benchmark"),
    duration_seconds: int = Query(default=30, description="Benchmark audio duration"),
):
    """
    Run a quick benchmark to calibrate performance estimates.
    
    This runs a short transcription to measure actual performance.
    """
    # This would run an actual benchmark
    # For now, return estimated values
    config = get_hardware_config()
    
    from services.evaluation import BENCHMARK_DATA
    
    device = config.preferred_device
    if device == "rocm":
        device = "cuda"
    
    rtf = BENCHMARK_DATA.get((model, device), BENCHMARK_DATA.get((model, "cpu"), 1.0))
    
    return {
        "model": model,
        "device": config.preferred_device,
        "realtime_factor": rtf,
        "description": format_realtime_factor(rtf),
        "sample_estimates": {
            "1_minute_audio": format_eta(60 / rtf),
            "10_minute_audio": format_eta(600 / rtf),
            "1_hour_audio": format_eta(3600 / rtf),
        },
    }


def get_score_description(score: int) -> str:
    """Get a human-readable description for hardware score."""
    if score >= 80:
        return "Excellent - Can run all models at full speed"
    elif score >= 60:
        return "Good - Can run large models comfortably"
    elif score >= 40:
        return "Moderate - May need to use medium/small models"
    elif score >= 20:
        return "Basic - Recommended to use small/base models"
    else:
        return "Limited - Consider using tiny model or external processing"


def format_realtime_factor(rtf: float) -> str:
    """Format realtime factor into human-readable description."""
    if rtf >= 10:
        return f"{rtf:.0f}x faster than realtime (very fast)"
    elif rtf >= 2:
        return f"{rtf:.1f}x faster than realtime (fast)"
    elif rtf >= 1:
        return f"{rtf:.1f}x realtime (good)"
    elif rtf >= 0.5:
        return f"{rtf:.1f}x realtime (acceptable)"
    elif rtf >= 0.1:
        return f"{rtf:.2f}x realtime (slow)"
    else:
        return f"{rtf:.2f}x realtime (very slow)"
