# Architecture Overview

This document explains "how the tool works" under the hood. The application is built as a split-stack web application with a Python backend and React frontend.

## System Components

### 1. Backend (Python/FastAPI)
The backend is the core of the application, responsible for API handling, data management, and orchestration of AI tasks.

*   **API Layer (`backend/api/`)**: Built with **FastAPI**. Exposes REST endpoints for jobs, files, and models. Handles WebSocket connections for real-time updates.
*   **Database (`backend/services/database.py`)**: Uses **SQLAlchemy** (async) with SQLite. Stores metadata for jobs, transcripts, and history.
*   **Task Queue**: Uses a background worker system (custom async implementation or Celery) to process long-running transcription jobs without blocking the API.
*   **AI Models**:
    *   **Transcription**: Uses `faster-whisper` (CTranslate2 backend) for high-performance inference.
    *   **Diarization**: Uses `pyannote.audio` (optional) for speaker separation.
    *   **TTS**: Uses `coqui-tts` (optional) for voice cloning and synthesis.

### 2. Frontend (React/Vite)
The frontend is a Single Page Application (SPA) that provides the user interface.

*   **Framework**: **React** with **Vite** for fast development and building.
*   **State Management**: **TanStack Query** (React Query) for server state and caching. **Zustand** for transient global state (like WebSocket connection status).
*   **Styling**: **Tailwind CSS** for utility-first styling.
*   **Real-time Updates**: Connects to the backend via **WebSockets** to receive live progress updates on transcription jobs.

## Data Flow

1.  **Upload**: User uploads a file -> Backend saves to `uploads/` -> Creates `Job` record (Status: PENDING).
2.  **Queue**: Background worker picks up the job -> Updates status to PROCESSING.
3.  **Processing**:
    *   Audio extraction (ffmpeg).
    *   Transcription (Whisper).
    *   Diarization (Pyannote).
4.  **Completion**: Results saved to `outputs/` (JSON, SRT, VTT) -> Database updated -> WebSocket notifies frontend.
5.  **Review**: User views `JobDetails` -> Frontend fetches transcript -> User edits (PATCH request) -> Backend updates database.

## Directory Structure
```
stt-server/
├── backend/            # Python FastAPI server
│   ├── api/            # API Route handlers
│   ├── core/           # Core logic (transcriber, diarizer)
│   ├── models/         # Database models
│   └── main.py         # Entry point
├── frontend/           # React application
│   ├── src/
│   │   ├── components/ # Reusable UI components
│   │   ├── pages/      # Route pages
│   │   └── lib/        # API client & utilities
│   └── index.css       # Global styles (Tailwind)
└── docs/               # Documentation
```
