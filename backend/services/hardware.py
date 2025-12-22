"""
Hardware detection and optimization service.

Automatically detects and configures:
- NVIDIA CUDA GPUs
- AMD ROCm GPUs  
- Intel Arc GPUs (via Intel Extension for PyTorch)
- Apple Metal (MPS) for Apple Silicon
- Vulkan/OpenCL (fallback for other GPUs)
- CPU with optimal threading
"""

import os
import platform
from dataclasses import dataclass
from typing import Optional, List, Tuple
import logging

logger = logging.getLogger(__name__)


@dataclass
class GPUInfo:
    """Information about a detected GPU."""
    
    index: int
    name: str
    vendor: str  # nvidia, amd, intel, apple
    memory_gb: float
    compute_capability: Optional[str] = None
    is_available: bool = True


@dataclass
class HardwareConfig:
    """Detected hardware configuration."""
    
    # CPU info
    cpu_cores: int
    cpu_threads: int
    ram_gb: float
    
    # GPU info
    gpus: List[GPUInfo]
    preferred_device: str  # cuda, rocm, xpu, mps, cpu
    
    # Optimal settings
    recommended_compute_type: str
    recommended_batch_size: int
    recommended_num_workers: int


def detect_hardware() -> HardwareConfig:
    """
    Detect available hardware and determine optimal configuration.
    
    Priority order: CUDA > ROCm > Intel XPU > Apple MPS > CPU
    """
    import psutil
    
    # CPU info
    cpu_cores = psutil.cpu_count(logical=False) or 4
    cpu_threads = psutil.cpu_count(logical=True) or 8
    ram_gb = psutil.virtual_memory().total / (1024 ** 3)
    
    gpus = []
    preferred_device = "cpu"
    compute_type = "float32"
    
    # Try NVIDIA CUDA
    cuda_gpus = detect_cuda_gpus()
    if cuda_gpus:
        gpus.extend(cuda_gpus)
        preferred_device = "cuda"
        # Use float16 for modern GPUs (compute capability >= 7.0)
        if any(gpu.compute_capability and float(gpu.compute_capability.split('.')[0]) >= 7 for gpu in cuda_gpus):
            compute_type = "float16"
        else:
            compute_type = "int8"
        logger.info(f"Detected {len(cuda_gpus)} NVIDIA GPU(s)")
    
    # Try AMD ROCm
    if not gpus:
        rocm_gpus = detect_rocm_gpus()
        if rocm_gpus:
            gpus.extend(rocm_gpus)
            preferred_device = "rocm"
            compute_type = "float16"
            logger.info(f"Detected {len(rocm_gpus)} AMD GPU(s)")
    
    # Try Intel Arc (XPU)
    if not gpus:
        intel_gpus = detect_intel_gpus()
        if intel_gpus:
            gpus.extend(intel_gpus)
            preferred_device = "xpu"
            compute_type = "float16"
            logger.info(f"Detected {len(intel_gpus)} Intel GPU(s)")
    
    # Try Apple Metal (MPS)
    if not gpus and platform.system() == "Darwin":
        mps_available = detect_apple_mps()
        if mps_available:
            gpus.append(GPUInfo(
                index=0,
                name="Apple Silicon GPU",
                vendor="apple",
                memory_gb=ram_gb * 0.75,  # Shared memory
            ))
            preferred_device = "mps"
            compute_type = "float16"
            logger.info("Detected Apple Silicon GPU (MPS)")
    
    # Try Vulkan/OpenCL (fallback for unsupported GPUs)
    if not gpus:
        vulkan_gpus = detect_vulkan_gpus()
        if vulkan_gpus:
            gpus.extend(vulkan_gpus)
            preferred_device = "vulkan"
            compute_type = "float32"  # Vulkan compute typically uses float32
            logger.info(f"Detected {len(vulkan_gpus)} Vulkan-capable GPU(s)")
    
    # Calculate optimal settings
    if gpus:
        max_vram = max(gpu.memory_gb for gpu in gpus)
        batch_size = calculate_batch_size(max_vram)
        num_workers = min(len(gpus), 4)
    else:
        batch_size = 1
        num_workers = max(1, cpu_threads // 4)
        logger.info(f"No GPU detected, using CPU with {num_workers} workers")
    
    return HardwareConfig(
        cpu_cores=cpu_cores,
        cpu_threads=cpu_threads,
        ram_gb=ram_gb,
        gpus=gpus,
        preferred_device=preferred_device,
        recommended_compute_type=compute_type,
        recommended_batch_size=batch_size,
        recommended_num_workers=num_workers,
    )


def detect_cuda_gpus() -> List[GPUInfo]:
    """Detect NVIDIA CUDA GPUs."""
    gpus = []
    
    try:
        import torch
        if not torch.cuda.is_available():
            return []
        
        for i in range(torch.cuda.device_count()):
            props = torch.cuda.get_device_properties(i)
            gpus.append(GPUInfo(
                index=i,
                name=props.name,
                vendor="nvidia",
                memory_gb=props.total_memory / (1024 ** 3),
                compute_capability=f"{props.major}.{props.minor}",
            ))
    except ImportError:
        # Try nvidia-smi as fallback
        try:
            import subprocess
            result = subprocess.run(
                ["nvidia-smi", "--query-gpu=index,name,memory.total", "--format=csv,noheader,nounits"],
                capture_output=True, text=True
            )
            if result.returncode == 0:
                for line in result.stdout.strip().split('\n'):
                    parts = line.split(', ')
                    if len(parts) >= 3:
                        gpus.append(GPUInfo(
                            index=int(parts[0]),
                            name=parts[1],
                            vendor="nvidia",
                            memory_gb=float(parts[2]) / 1024,
                        ))
        except Exception:
            pass
    
    return gpus


def detect_rocm_gpus() -> List[GPUInfo]:
    """Detect AMD ROCm GPUs."""
    gpus = []
    
    try:
        import torch
        if hasattr(torch, 'hip') or (hasattr(torch.version, 'hip') and torch.version.hip):
            if torch.cuda.is_available():  # ROCm uses cuda API
                for i in range(torch.cuda.device_count()):
                    props = torch.cuda.get_device_properties(i)
                    gpus.append(GPUInfo(
                        index=i,
                        name=props.name,
                        vendor="amd",
                        memory_gb=props.total_memory / (1024 ** 3),
                    ))
    except ImportError:
        # Try rocm-smi as fallback
        try:
            import subprocess
            result = subprocess.run(
                ["rocm-smi", "--showproductname", "--showmeminfo", "vram"],
                capture_output=True, text=True
            )
            if result.returncode == 0:
                # Parse rocm-smi output
                lines = result.stdout.strip().split('\n')
                # Simplified parsing
                gpus.append(GPUInfo(
                    index=0,
                    name="AMD GPU",
                    vendor="amd",
                    memory_gb=8.0,  # Default estimate
                ))
        except Exception:
            pass
    
    return gpus


def detect_intel_gpus() -> List[GPUInfo]:
    """Detect Intel Arc GPUs via Intel Extension for PyTorch."""
    gpus = []
    
    try:
        import intel_extension_for_pytorch as ipex
        import torch
        
        if torch.xpu.is_available():
            for i in range(torch.xpu.device_count()):
                props = torch.xpu.get_device_properties(i)
                gpus.append(GPUInfo(
                    index=i,
                    name=getattr(props, 'name', f"Intel GPU {i}"),
                    vendor="intel",
                    memory_gb=getattr(props, 'total_memory', 8 * 1024**3) / (1024 ** 3),
                ))
    except ImportError:
        pass
    
    return gpus


def detect_apple_mps() -> bool:
    """Detect Apple Metal Performance Shaders availability."""
    try:
        import torch
        return torch.backends.mps.is_available()
    except (ImportError, AttributeError):
        return False


def detect_vulkan_gpus() -> List[GPUInfo]:
    """
    Detect Vulkan/OpenCL capable GPUs.
    
    This is a fallback for GPUs not supported by CUDA/ROCm/XPU/MPS.
    Uses vulkaninfo or clinfo to detect available devices.
    Note: Most ML frameworks don't directly support Vulkan compute,
    but this can be used with ONNX Runtime's DirectML backend or
    llama.cpp's Vulkan backend.
    """
    gpus = []
    
    # Try vulkaninfo
    try:
        import subprocess
        result = subprocess.run(
            ["vulkaninfo", "--summary"],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            lines = result.stdout.strip().split('\n')
            for line in lines:
                if 'deviceName' in line or 'GPU' in line.upper():
                    # Parse GPU name
                    if '=' in line:
                        name = line.split('=')[1].strip()
                    else:
                        name = line.strip()
                    if name and 'llvmpipe' not in name.lower():  # Skip software renderer
                        gpus.append(GPUInfo(
                            index=len(gpus),
                            name=name,
                            vendor="vulkan",
                            memory_gb=4.0,  # Estimate, vulkaninfo doesn't always show memory
                        ))
                        break  # Usually just need the first real GPU
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    
    # Try OpenCL (clinfo) as fallback
    if not gpus:
        try:
            import subprocess
            result = subprocess.run(
                ["clinfo", "-l"],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                lines = result.stdout.strip().split('\n')
                for line in lines:
                    # Look for GPU devices
                    if 'GPU' in line.upper() or 'Graphics' in line:
                        name = line.strip()
                        if name:
                            gpus.append(GPUInfo(
                                index=len(gpus),
                                name=f"OpenCL: {name}",
                                vendor="opencl",
                                memory_gb=4.0,  # Estimate
                            ))
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass
    
    return gpus


def calculate_batch_size(vram_gb: float) -> int:
    """Calculate recommended batch size based on VRAM."""
    if vram_gb >= 24:
        return 16
    elif vram_gb >= 16:
        return 12
    elif vram_gb >= 12:
        return 8
    elif vram_gb >= 8:
        return 4
    elif vram_gb >= 6:
        return 2
    else:
        return 1


def get_torch_device(preferred: str = "auto") -> str:
    """
    Get the appropriate torch device string.
    
    Args:
        preferred: Preferred device or "auto" for automatic detection
        
    Returns:
        Device string for torch/compute backend
    """
    if preferred == "auto":
        config = detect_hardware()
        preferred = config.preferred_device
    
    device_map = {
        "cuda": "cuda",
        "rocm": "cuda",  # ROCm uses CUDA API
        "xpu": "xpu",
        "mps": "mps",
        "vulkan": "cpu",  # Vulkan requires specialized backends (ONNX-DML, llama.cpp)
        "opencl": "cpu",  # OpenCL requires specialized backends
        "cpu": "cpu",
    }
    
    return device_map.get(preferred, "cpu")


def optimize_for_hardware(config: HardwareConfig):
    """
    Apply hardware-specific optimizations.
    
    Sets environment variables and torch settings for optimal performance.
    """
    import torch
    
    # CPU optimizations
    if config.preferred_device == "cpu":
        # Use all available cores for PyTorch
        torch.set_num_threads(config.cpu_threads)
        os.environ["OMP_NUM_THREADS"] = str(config.cpu_threads)
        os.environ["MKL_NUM_THREADS"] = str(config.cpu_threads)
    
    # CUDA optimizations
    if config.preferred_device == "cuda":
        # Enable TF32 for Ampere+ GPUs
        torch.backends.cuda.matmul.allow_tf32 = True
        torch.backends.cudnn.allow_tf32 = True
        
        # Enable cudnn benchmarking for consistent input sizes
        torch.backends.cudnn.benchmark = True
    
    # Intel optimizations
    if config.preferred_device == "xpu":
        try:
            import intel_extension_for_pytorch as ipex
            # Apply ipex optimizations
        except ImportError:
            pass
    
    logger.info(f"Hardware optimization applied: device={config.preferred_device}, "
                f"compute_type={config.recommended_compute_type}, "
                f"batch_size={config.recommended_batch_size}")


# Singleton instance
_hardware_config: Optional[HardwareConfig] = None


def get_hardware_config() -> HardwareConfig:
    """Get cached hardware configuration."""
    global _hardware_config
    if _hardware_config is None:
        _hardware_config = detect_hardware()
        optimize_for_hardware(_hardware_config)
    return _hardware_config
