"""
Model Manager with Idle Timeout Unloading for Transcribe

Manages Whisper and other models with automatic unloading after idle period.
"""

import os
import time
import threading
import logging
import gc
from typing import Optional, Any, Dict

logger = logging.getLogger(__name__)

DEFAULT_IDLE_TIMEOUT = int(os.getenv("MODEL_IDLE_TIMEOUT", "600"))


class ModelManager:
    """Thread-safe model manager with idle timeout unloading."""
    
    def __init__(self, idle_timeout: int = DEFAULT_IDLE_TIMEOUT):
        self._models: Dict[str, Any] = {}
        self._last_used: Dict[str, float] = {}
        self._timeout = idle_timeout
        self._lock = threading.RLock()
        self._running = True
        
        # Start background cleanup thread
        self._start_cleanup_thread()
        logger.info(f"ModelManager initialized with {idle_timeout}s idle timeout")
    
    def _start_cleanup_thread(self):
        def cleanup_loop():
            while self._running:
                time.sleep(60)
                self._check_timeouts()
        
        thread = threading.Thread(target=cleanup_loop, daemon=True)
        thread.start()
    
    def _check_timeouts(self):
        with self._lock:
            now = time.time()
            keys_to_remove = []
            
            for key, last_used in self._last_used.items():
                if now - last_used > self._timeout:
                    keys_to_remove.append(key)
            
            for key in keys_to_remove:
                logger.info(f"Unloading idle model: {key}")
                self._unload_model(key)
    
    def _unload_model(self, key: str):
        if key in self._models:
            del self._models[key]
            del self._last_used[key]
            gc.collect()
            
            try:
                import torch
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
            except ImportError:
                pass
    
    def get_model(self, key: str, loader_fn):
        """Get model by key, loading with loader_fn if not cached."""
        with self._lock:
            self._last_used[key] = time.time()
            
            if key not in self._models:
                logger.info(f"Loading model: {key}")
                start = time.time()
                self._models[key] = loader_fn()
                logger.info(f"Model {key} loaded in {time.time() - start:.1f}s")
            
            return self._models[key]
    
    def is_loaded(self, key: str) -> bool:
        return key in self._models
    
    def unload_all(self):
        with self._lock:
            keys = list(self._models.keys())
            for key in keys:
                self._unload_model(key)
    
    def shutdown(self):
        self._running = False
        self.unload_all()


# Global singleton
_manager: Optional[ModelManager] = None


def get_model_manager() -> ModelManager:
    global _manager
    if _manager is None:
        _manager = ModelManager()
    return _manager


def get_whisper_model(model_id: str, device: str, compute_type: str):
    """Get cached Whisper model with idle timeout."""
    def loader():
        from faster_whisper import WhisperModel
        return WhisperModel(model_id, device=device, compute_type=compute_type, num_workers=4)
    
    key = f"whisper:{model_id}:{device}:{compute_type}"
    return get_model_manager().get_model(key, loader)
