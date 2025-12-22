"""Model downloader service for different engines."""

from pathlib import Path
from typing import Optional, Callable
import asyncio

from schemas.model import ModelEngine, ModelSource


async def download_model_for_engine(
    engine: ModelEngine,
    model_id: str,
    source: ModelSource,
    revision: Optional[str],
    target_dir: Path,
    progress_callback: Optional[Callable[[float], None]] = None,
) -> Path:
    """
    Download a model based on its engine and source.
    
    Returns the local path where the model is stored.
    """
    if source == ModelSource.HUGGINGFACE:
        return await download_from_huggingface(
            model_id=model_id,
            engine=engine,
            revision=revision,
            target_dir=target_dir,
            progress_callback=progress_callback,
        )
    elif source == ModelSource.URL:
        return await download_from_url(
            url=model_id,
            target_dir=target_dir,
            progress_callback=progress_callback,
        )
    elif source == ModelSource.LOCAL_UPLOAD:
        # Already local, just verify it exists
        path = Path(model_id)
        if not path.exists():
            raise ValueError(f"Local model not found: {model_id}")
        return path
    elif source == ModelSource.BUILTIN:
        # Let the engine handle its own model loading
        return await download_builtin_model(
            engine=engine,
            model_id=model_id,
            target_dir=target_dir,
            progress_callback=progress_callback,
        )
    else:
        raise ValueError(f"Unknown model source: {source}")


async def download_from_huggingface(
    model_id: str,
    engine: ModelEngine,
    revision: Optional[str],
    target_dir: Path,
    progress_callback: Optional[Callable[[float], None]] = None,
) -> Path:
    """Download model from HuggingFace Hub."""
    from huggingface_hub import snapshot_download, hf_hub_download
    
    # Create engine-specific directory
    engine_dir = target_dir / engine.value
    engine_dir.mkdir(parents=True, exist_ok=True)
    
    # Sanitize model name for directory
    safe_name = model_id.replace("/", "_")
    model_dir = engine_dir / safe_name
    
    if progress_callback:
        progress_callback(10)
    
    # Different engines need different download approaches
    if engine in [ModelEngine.FASTER_WHISPER, ModelEngine.WHISPERX]:
        # These use CTranslate2 format, download full repo
        local_path = snapshot_download(
            repo_id=f"Systran/faster-whisper-{model_id}" if "/" not in model_id else model_id,
            revision=revision,
            local_dir=str(model_dir),
        )
    elif engine == ModelEngine.HUGGINGFACE_WHISPER:
        # Standard HF transformers model
        local_path = snapshot_download(
            repo_id=model_id,
            revision=revision,
            local_dir=str(model_dir),
        )
    elif engine == ModelEngine.PYANNOTE:
        # Pyannote models
        local_path = snapshot_download(
            repo_id=model_id,
            revision=revision,
            local_dir=str(model_dir),
        )
    elif engine == ModelEngine.COQUI_XTTS:
        # Coqui TTS models have their own download mechanism
        local_path = str(model_dir)
        # TTS library handles download internally
    elif engine == ModelEngine.PIPER:
        # Piper models are individual files
        model_file = f"{model_id}.onnx"
        config_file = f"{model_id}.onnx.json"
        
        hf_hub_download(
            repo_id="rhasspy/piper-voices",
            filename=model_file,
            local_dir=str(model_dir),
        )
        hf_hub_download(
            repo_id="rhasspy/piper-voices",
            filename=config_file,
            local_dir=str(model_dir),
        )
        local_path = str(model_dir)
    elif engine == ModelEngine.MARS5:
        local_path = snapshot_download(
            repo_id=model_id,
            revision=revision,
            local_dir=str(model_dir),
        )
    else:
        # Generic HF download
        local_path = snapshot_download(
            repo_id=model_id,
            revision=revision,
            local_dir=str(model_dir),
        )
    
    if progress_callback:
        progress_callback(100)
    
    return Path(local_path)


async def download_from_url(
    url: str,
    target_dir: Path,
    progress_callback: Optional[Callable[[float], None]] = None,
) -> Path:
    """Download model from direct URL."""
    import aiohttp
    from urllib.parse import urlparse
    
    # Get filename from URL
    parsed = urlparse(url)
    filename = Path(parsed.path).name
    
    output_path = target_dir / "url_models" / filename
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            total = int(response.headers.get('content-length', 0))
            downloaded = 0
            
            with open(output_path, 'wb') as f:
                async for chunk in response.content.iter_chunked(8192):
                    f.write(chunk)
                    downloaded += len(chunk)
                    
                    if total > 0 and progress_callback:
                        progress_callback(downloaded / total * 100)
    
    return output_path


async def download_builtin_model(
    engine: ModelEngine,
    model_id: str,
    target_dir: Path,
    progress_callback: Optional[Callable[[float], None]] = None,
) -> Path:
    """
    Download built-in models using engine-specific mechanisms.
    
    For many engines, the model will be downloaded automatically
    when first used. This function just prepares the cache directory.
    """
    cache_dir = target_dir / engine.value / model_id.replace("/", "_")
    cache_dir.mkdir(parents=True, exist_ok=True)
    
    if progress_callback:
        progress_callback(10)
    
    if engine == ModelEngine.FASTER_WHISPER:
        # faster-whisper downloads on first use via CTranslate2
        # Just verify the model name is valid
        valid_models = ["tiny", "base", "small", "medium", "large-v2", "large-v3", "large-v3-turbo", "distil-large-v3"]
        if model_id not in valid_models and "/" not in model_id:
            raise ValueError(f"Unknown faster-whisper model: {model_id}")
        
        # Pre-download using the library
        from faster_whisper.utils import download_model
        model_path = download_model(model_id, cache_dir=str(cache_dir.parent))
        
        if progress_callback:
            progress_callback(100)
        
        return Path(model_path)
    
    elif engine == ModelEngine.COQUI_XTTS:
        # TTS library handles its own downloads
        # Models go to ~/.local/share/tts by default
        from TTS.utils.manage import ModelManager
        manager = ModelManager()
        
        if model_id in manager.list_models():
            model_path, _, _ = manager.download_model(model_id)
            return Path(model_path)
        else:
            raise ValueError(f"Unknown TTS model: {model_id}")
    
    elif engine == ModelEngine.PIPER:
        # Piper downloads from GitHub releases
        import subprocess
        
        # Download using piper's built-in mechanism
        subprocess.run([
            "piper", "--download-dir", str(cache_dir),
            "--model", model_id, "--download",
        ], check=True)
        
        if progress_callback:
            progress_callback(100)
        
        return cache_dir
    
    else:
        # For other engines, just create the directory
        # The engine will download on first use
        if progress_callback:
            progress_callback(100)
        
        return cache_dir
