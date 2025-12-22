"""Model-related Pydantic schemas with pluggable engine support."""

from datetime import datetime
from enum import Enum
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class ModelType(str, Enum):
    """Type of ML model."""

    WHISPER = "whisper"
    DIARIZATION = "diarization"
    TTS = "tts"


class ModelEngine(str, Enum):
    """
    Supported model engines.
    
    Users can upload models for any of these engines.
    """

    # STT Engines
    FASTER_WHISPER = "faster-whisper"
    WHISPERX = "whisperx"
    OPENAI_WHISPER = "openai-whisper"
    HUGGINGFACE_WHISPER = "huggingface-whisper"

    # Diarization Engines
    PYANNOTE = "pyannote"
    NEMO = "nemo"
    SPEECHBRAIN = "speechbrain"

    # TTS Engines
    COQUI_XTTS = "coqui-xtts"
    COQUI_VITS = "coqui-vits"
    PIPER = "piper"
    MARS5 = "mars5"
    BARK = "bark"
    TORTOISE = "tortoise"


class ModelSource(str, Enum):
    """Where the model comes from."""

    HUGGINGFACE = "huggingface"
    LOCAL_UPLOAD = "local"
    URL = "url"
    BUILTIN = "builtin"


class ModelInfo(BaseModel):
    """Information about a model's capabilities."""

    size_mb: Optional[int] = Field(default=None, description="Model size in megabytes")
    languages: List[str] = Field(default=["multilingual"], description="Supported languages")
    description: str = Field(default="", description="Model description")
    recommended_vram_gb: Optional[float] = Field(default=None, description="Recommended VRAM in GB")
    supports_streaming: bool = Field(default=False, description="Whether model supports streaming output")
    sample_rate: Optional[int] = Field(default=None, description="Required audio sample rate")
    extra_config: Dict[str, Any] = Field(default_factory=dict, description="Engine-specific configuration")


class ModelCreate(BaseModel):
    """Schema for registering a new model."""

    name: str = Field(..., description="Model display name")
    model_type: ModelType = Field(..., description="Type of model (whisper, diarization, tts)")
    engine: ModelEngine = Field(..., description="Processing engine for this model")
    
    # Model source
    source: ModelSource = Field(default=ModelSource.HUGGINGFACE, description="Where to get the model")
    model_id: str = Field(
        ...,
        description="Model identifier - HuggingFace repo ID, local path, or URL",
    )
    revision: Optional[str] = Field(default=None, description="HuggingFace revision/branch")
    
    # Configuration
    info: ModelInfo = Field(default_factory=ModelInfo, description="Model information")
    is_default: bool = Field(default=False, description="Set as default for this type")
    
    # Engine-specific options
    compute_type: Optional[str] = Field(
        default=None,
        description="Compute type: float16, int8, float32 (engine-specific)",
    )
    device: Optional[str] = Field(
        default=None,
        description="Override device: cuda, cpu, auto",
    )


class ModelResponse(BaseModel):
    """Schema for model response."""

    id: str = Field(..., description="Unique model ID")
    name: str
    model_type: ModelType
    engine: ModelEngine
    source: ModelSource
    model_id: str
    revision: Optional[str] = None
    
    info: ModelInfo
    is_default: bool
    compute_type: Optional[str] = None
    device: Optional[str] = None
    
    # Status
    is_downloaded: bool = Field(default=False, description="Whether model is downloaded locally")
    download_progress: Optional[float] = Field(
        default=None,
        description="Download progress percentage if currently downloading",
    )
    local_path: Optional[str] = Field(default=None, description="Local file path if downloaded")
    
    # Timestamps
    created_at: datetime
    last_used_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class ModelDownloadRequest(BaseModel):
    """Request to download a model."""

    model_id: str = Field(..., description="Model ID to download")
    force: bool = Field(default=False, description="Force re-download even if exists")


class ModelTestRequest(BaseModel):
    """Request to test a model with sample input."""

    model_id: str
    sample_text: Optional[str] = Field(
        default=None,
        description="Sample text for TTS testing",
    )
    sample_audio_url: Optional[str] = Field(
        default=None,
        description="Sample audio URL for STT/diarization testing",
    )


# Pre-defined models by engine
BUILTIN_MODELS: Dict[ModelEngine, Dict[str, ModelInfo]] = {
    # Faster-Whisper models
    ModelEngine.FASTER_WHISPER: {
        "tiny": ModelInfo(
            size_mb=75,
            languages=["multilingual"],
            description="Fastest, lowest accuracy. Good for testing.",
            recommended_vram_gb=1.0,
        ),
        "base": ModelInfo(
            size_mb=142,
            languages=["multilingual"],
            description="Fast with decent accuracy.",
            recommended_vram_gb=1.0,
        ),
        "small": ModelInfo(
            size_mb=466,
            languages=["multilingual"],
            description="Good balance of speed and accuracy.",
            recommended_vram_gb=2.0,
        ),
        "medium": ModelInfo(
            size_mb=1500,
            languages=["multilingual"],
            description="High accuracy, moderate speed.",
            recommended_vram_gb=5.0,
        ),
        "large-v2": ModelInfo(
            size_mb=2900,
            languages=["multilingual"],
            description="Very high accuracy.",
            recommended_vram_gb=10.0,
        ),
        "large-v3": ModelInfo(
            size_mb=2900,
            languages=["multilingual"],
            description="Latest large model with best accuracy.",
            recommended_vram_gb=10.0,
        ),
        "large-v3-turbo": ModelInfo(
            size_mb=1600,
            languages=["multilingual"],
            description="Faster variant of large-v3 with similar accuracy.",
            recommended_vram_gb=6.0,
        ),
        "distil-large-v3": ModelInfo(
            size_mb=756,
            languages=["multilingual"],
            description="Distilled model - 6x faster than large-v3.",
            recommended_vram_gb=4.0,
        ),
    },
    # Pyannote diarization models
    ModelEngine.PYANNOTE: {
        "pyannote/speaker-diarization-3.1": ModelInfo(
            size_mb=500,
            description="State-of-the-art speaker diarization.",
            recommended_vram_gb=4.0,
            extra_config={"requires_hf_token": True},
        ),
        "pyannote/speaker-diarization-3.0": ModelInfo(
            size_mb=500,
            description="Previous generation diarization model.",
            recommended_vram_gb=4.0,
            extra_config={"requires_hf_token": True},
        ),
    },
    # Coqui XTTS models
    ModelEngine.COQUI_XTTS: {
        "tts_models/multilingual/multi-dataset/xtts_v2": ModelInfo(
            size_mb=1800,
            languages=["en", "es", "fr", "de", "it", "pt", "pl", "tr", "ru", "nl", "cs", "ar", "zh-cn", "ja", "hu", "ko"],
            description="Multilingual TTS with voice cloning support.",
            recommended_vram_gb=6.0,
            supports_streaming=True,
            sample_rate=24000,
        ),
    },
    # Piper models
    ModelEngine.PIPER: {
        "en_US-lessac-medium": ModelInfo(
            size_mb=75,
            languages=["en-US"],
            description="Fast, lightweight English TTS.",
            recommended_vram_gb=0.5,
            sample_rate=22050,
        ),
        "en_GB-alba-medium": ModelInfo(
            size_mb=75,
            languages=["en-GB"],
            description="British English voice.",
            recommended_vram_gb=0.5,
            sample_rate=22050,
        ),
    },
    # MARS5 models
    ModelEngine.MARS5: {
        "Camb-ai/mars5-tts": ModelInfo(
            size_mb=2000,
            languages=["en"],
            description="High quality TTS with natural prosody.",
            recommended_vram_gb=8.0,
            supports_streaming=False,
        ),
    },
}


def get_engine_for_type(model_type: ModelType) -> List[ModelEngine]:
    """Get available engines for a model type."""
    engines = {
        ModelType.WHISPER: [
            ModelEngine.FASTER_WHISPER,
            ModelEngine.WHISPERX,
            ModelEngine.OPENAI_WHISPER,
            ModelEngine.HUGGINGFACE_WHISPER,
        ],
        ModelType.DIARIZATION: [
            ModelEngine.PYANNOTE,
            ModelEngine.NEMO,
            ModelEngine.SPEECHBRAIN,
        ],
        ModelType.TTS: [
            ModelEngine.COQUI_XTTS,
            ModelEngine.COQUI_VITS,
            ModelEngine.PIPER,
            ModelEngine.MARS5,
            ModelEngine.BARK,
            ModelEngine.TORTOISE,
        ],
    }
    return engines.get(model_type, [])
