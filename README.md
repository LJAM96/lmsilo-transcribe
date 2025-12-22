# Speech-to-Text Server

A comprehensive speech-to-text application with speaker diarization, TTS synthesis, and multi-client queue support.

![Dashboard Preview](docs/dashboard-preview.png)

## Features

- **Multi-Engine STT**: Support for faster-whisper, WhisperX, OpenAI Whisper, and HuggingFace Whisper
- **Speaker Diarization**: Identify and label speakers using pyannote, NeMo, or SpeechBrain
- **TTS Synthesis**: Generate audio from transcripts with Coqui TTS, Piper, MARS5, Bark, or Tortoise
- **Timing Synchronization**: Match TTS output to original audio timing with rubberband
- **Video Support**: Process video files, generate subtitles, and remux with new audio
- **Multi-Client Queue**: Real-time WebSocket updates, priority management
- **Hardware Detection**: Automatic optimization for CUDA, ROCm, Intel Arc, Apple MPS, or CPU
- **Performance Estimation**: ETA predictions and model recommendations based on your hardware

## Quick Start

### Prerequisites

- Docker and Docker Compose
- NVIDIA GPU with CUDA (recommended) or CPU
- For diarization: HuggingFace account and token

### Running with Docker

1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/stt-server.git
   cd stt-server
   ```

2. Create environment file:
   ```bash
   cp backend/.env.example .env
   # Edit .env and add your HF_TOKEN
   ```

3. Start all services:
   ```bash
   docker-compose up -d
   ```

4. Access the web UI at http://localhost:3000 or API at http://localhost:8000/docs

## API Usage

The server provides a complete REST API that can be consumed by any client (C#, Python, etc.).

### Key Endpoints

| Endpoint | Description |
|----------|-------------|
| `POST /api/jobs` | Upload file and create transcription job |
| `GET /api/jobs/{id}` | Get job status and details |
| `GET /api/jobs/{id}/transcript` | Get transcript (JSON, SRT, VTT, TXT) |
| `GET /api/models` | List available models |
| `POST /api/models` | Register a new model |
| `GET /api/system/evaluate` | Get hardware evaluation and recommendations |
| `WS /api/queue/ws` | Real-time queue updates |

### Example: Upload and Transcribe

```python
import requests

# Upload a file
with open("audio.mp3", "rb") as f:
    response = requests.post(
        "http://localhost:8000/api/jobs",
        files={"file": f},
        data={
            "language": "auto",
            "enable_diarization": "true",
            "output_formats": "json,srt",
        }
    )
job = response.json()

# Poll for completion
while job["status"] not in ["completed", "failed"]:
    job = requests.get(f"http://localhost:8000/api/jobs/{job['id']}").json()
    print(f"Progress: {job['progress']}%")
    time.sleep(2)

# Get transcript
transcript = requests.get(f"http://localhost:8000/api/jobs/{job['id']}/transcript").json()
```

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL connection string | `postgresql+asyncpg://stt:stt@postgres:5432/stt` |
| `REDIS_URL` | Redis connection string | `redis://redis:6379/0` |
| `HF_TOKEN` | HuggingFace token (for pyannote) | Required for diarization |
| `DEVICE` | Compute device (cuda/cpu/auto) | `cuda` |
| `COMPUTE_TYPE` | Precision (float16/int8/float32) | `float16` |

### Hardware Support

The server automatically detects and optimizes for:

- **NVIDIA CUDA** - Full GPU acceleration
- **AMD ROCm** - GPU support via HIP
- **Intel Arc** - Via Intel Extension for PyTorch
- **Apple Silicon** - Metal Performance Shaders (MPS)
- **CPU** - Optimized multi-threading

Use `/api/system/evaluate` to see your hardware capabilities and recommendations.

## Project Structure

```
stt-server/
├── backend/
│   ├── api/              # FastAPI route handlers
│   ├── workers/          # Celery task workers
│   ├── services/         # Business logic services
│   ├── schemas/          # Pydantic models
│   └── models/           # SQLAlchemy ORM models
├── frontend/
│   ├── src/
│   │   ├── pages/        # React page components
│   │   ├── components/   # Reusable UI components
│   │   └── lib/          # API client and utilities
│   └── tailwind.config.js
├── docker-compose.yml
├── Dockerfile.backend
└── Dockerfile.frontend
```

## Development

### Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

### Running Celery Workers

```bash
celery -A workers.celery_app worker -Q stt,diarization,tts,sync --loglevel=info
```

## License

MIT License
# stt-server
