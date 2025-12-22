# LMSilo Transcribe

Speech-to-text service with speaker diarization, multiple Whisper backends, and TTS synthesis.

## Features

- **Multiple Engines**: Faster-Whisper, WhisperX, HuggingFace Whisper
- **Speaker Diarization**: Identify and label speakers
- **Batch Processing**: Process multiple files
- **Subtitle Burning**: Embed subtitles into video
- **Real-time Updates**: WebSocket progress events
- **Model Management**: Download and manage models
- **Shared Workspace**: All users see job queue

## Architecture

```
transcribe/
├── backend/
│   ├── main.py           # FastAPI application
│   ├── api/
│   │   ├── jobs.py       # Job management
│   │   ├── models.py     # Model management
│   │   ├── files.py      # File streaming
│   │   ├── transcripts.py
│   │   └── subtitles.py
│   ├── models/
│   │   └── database.py   # SQLAlchemy models
│   ├── services/
│   │   └── model_downloader.py
│   └── workers/
│       ├── celery_app.py
│       └── tasks.py
├── frontend/
│   └── src/
│       ├── App.tsx
│       └── components/
└── Dockerfile
```

## API Endpoints

### Jobs
- `POST /api/jobs` - Create transcription job
- `GET /api/jobs` - List all jobs
- `GET /api/jobs/{id}` - Get job details
- `DELETE /api/jobs/{id}` - Delete job

### Transcripts
- `GET /api/jobs/{id}/transcript` - Get transcript (json/srt/vtt/txt)
- `PATCH /api/transcripts/{id}/segments/{seg_id}` - Edit segment

### Models
- `GET /api/models` - List installed models
- `POST /api/models` - Register model
- `POST /api/models/{id}/download` - Download model

### Files
- `GET /api/files/{id}/original` - Stream original media
- `GET /api/files/{id}/subtitles` - Get subtitle file

## Supported Models

| Engine | Models |
|--------|--------|
| Faster-Whisper | tiny, base, small, medium, large-v2, large-v3 |
| WhisperX | Same + word-level timestamps |
| Pyannote | Speaker diarization |

## Development

```bash
cd transcribe

# Backend
cd backend
pip install -r requirements.txt
uvicorn main:app --reload

# Frontend
cd frontend
npm install
npm run dev

# Worker
celery -A workers.celery_app worker -l info
```

## License

MIT
