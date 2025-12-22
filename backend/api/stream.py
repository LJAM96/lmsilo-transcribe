"""Streaming transcription via WebSocket."""

import asyncio
from typing import Optional
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from starlette.websockets import WebSocketState

router = APIRouter()


class StreamingTranscriber:
    """Real-time audio transcription using faster-whisper with VAD."""
    
    def __init__(self, model_id: str = "tiny", device: str = "auto"):
        self.model = None
        self.model_id = model_id
        self.device = device
        self.is_initialized = False
        self.audio_buffer = bytearray()
        self.sample_rate = 16000
    
    async def initialize(self):
        """Lazy load the model."""
        if self.is_initialized:
            return
        
        try:
            from faster_whisper import WhisperModel
            
            self.model = WhisperModel(
                self.model_id,
                device=self.device,
                compute_type="int8",
            )
            self.is_initialized = True
        except ImportError:
            raise RuntimeError("faster-whisper not installed")
    
    async def process_audio_chunk(self, audio_data: bytes) -> Optional[dict]:
        """
        Process an audio chunk and return transcript if VAD detects speech end.
        
        Audio should be 16kHz mono PCM16.
        """
        import numpy as np
        
        if not self.is_initialized:
            await self.initialize()
        
        # Add to buffer
        self.audio_buffer.extend(audio_data)
        
        # Need minimum ~1 second of audio for meaningful transcription
        min_samples = self.sample_rate * 1  # 1 second
        current_samples = len(self.audio_buffer) // 2  # 16-bit = 2 bytes per sample
        
        if current_samples < min_samples:
            return None
        
        # Convert to numpy array
        audio = np.frombuffer(bytes(self.audio_buffer), dtype=np.int16)
        audio = audio.astype(np.float32) / 32768.0
        
        # Check for voice activity (simple energy-based VAD)
        rms = np.sqrt(np.mean(audio[-self.sample_rate:] ** 2))
        
        # If voice ended (low energy), transcribe
        if rms < 0.01 and len(audio) > self.sample_rate * 2:
            # Transcribe the buffer
            segments, info = self.model.transcribe(
                audio,
                language=None,  # Auto-detect
                vad_filter=True,
                word_timestamps=True,
            )
            
            text_parts = []
            for segment in segments:
                text_parts.append(segment.text.strip())
            
            # Clear buffer
            self.audio_buffer = bytearray()
            
            if text_parts:
                return {
                    "type": "transcript",
                    "text": " ".join(text_parts),
                    "language": info.language,
                    "is_final": True,
                }
        
        # Check if buffer is getting too large (5 seconds)
        max_samples = self.sample_rate * 5
        if current_samples > max_samples:
            # Force transcription
            audio = np.frombuffer(bytes(self.audio_buffer), dtype=np.int16)
            audio = audio.astype(np.float32) / 32768.0
            
            segments, info = self.model.transcribe(
                audio,
                language=None,
                vad_filter=True,
                word_timestamps=True,
            )
            
            text_parts = []
            for segment in segments:
                text_parts.append(segment.text.strip())
            
            # Clear buffer
            self.audio_buffer = bytearray()
            
            if text_parts:
                return {
                    "type": "transcript",
                    "text": " ".join(text_parts),
                    "language": info.language,
                    "is_final": False,
                }
        
        return None


# Transcriber instances per connection
active_transcribers: dict[str, StreamingTranscriber] = {}


@router.websocket("/ws")
async def stream_transcription(websocket: WebSocket):
    """
    WebSocket endpoint for real-time transcription.
    
    Protocol:
    1. Client connects
    2. Client sends audio chunks (PCM16 16kHz mono, as binary)
    3. Server responds with transcript JSON when speech ends
    4. Client can send {"type": "config", "model": "tiny"} to configure
    """
    await websocket.accept()
    
    connection_id = str(id(websocket))
    transcriber = StreamingTranscriber()
    active_transcribers[connection_id] = transcriber
    
    try:
        # Send ready message
        await websocket.send_json({
            "type": "ready",
            "message": "Streaming transcription ready. Send PCM16 audio at 16kHz.",
        })
        
        while True:
            # Receive message
            message = await websocket.receive()
            
            if message["type"] == "websocket.disconnect":
                break
            
            if "bytes" in message:
                # Audio data
                audio_chunk = message["bytes"]
                
                try:
                    result = await transcriber.process_audio_chunk(audio_chunk)
                    if result:
                        await websocket.send_json(result)
                except Exception as e:
                    await websocket.send_json({
                        "type": "error",
                        "message": str(e),
                    })
            
            elif "text" in message:
                # JSON command
                import json
                try:
                    data = json.loads(message["text"])
                    
                    if data.get("type") == "config":
                        # Reconfigure transcriber
                        model = data.get("model", "tiny")
                        transcriber.model_id = model
                        transcriber.is_initialized = False
                        await transcriber.initialize()
                        
                        await websocket.send_json({
                            "type": "configured",
                            "model": model,
                        })
                    
                    elif data.get("type") == "clear":
                        # Clear buffer
                        transcriber.audio_buffer = bytearray()
                        await websocket.send_json({
                            "type": "cleared",
                        })
                
                except json.JSONDecodeError:
                    pass
    
    except WebSocketDisconnect:
        pass
    finally:
        # Cleanup
        active_transcribers.pop(connection_id, None)


@router.get("/status")
async def get_streaming_status():
    """Get streaming service status."""
    return {
        "active_connections": len(active_transcribers),
        "supported_models": ["tiny", "base", "small", "medium", "large-v3"],
        "audio_format": {
            "sample_rate": 16000,
            "channels": 1,
            "format": "PCM16",
        },
    }
