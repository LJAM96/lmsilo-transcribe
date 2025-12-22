"""
Speech-to-Text Server - FastAPI Application

Main entry point for the STT server with:
- REST API for job management, file uploads, and model management
- WebSocket support for real-time queue updates
- Celery integration for background task processing
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from api import jobs, models, files, queue, history, stream, metrics, batches, transcripts, subtitles
from api import system as system_api
from services.database import init_db
from config import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events."""
    # Startup
    await init_db()
    yield
    # Shutdown
    pass


app = FastAPI(
    title="Speech-to-Text Server",
    description="Transcription service with speaker diarization and TTS synthesis",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS middleware for frontend access
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount API routes
app.include_router(jobs.router, prefix="/api/jobs", tags=["Jobs"])
app.include_router(models.router, prefix="/api/models", tags=["Models"])
app.include_router(files.router, prefix="/api/files", tags=["Files"])
app.include_router(queue.router, prefix="/api/queue", tags=["Queue"])
app.include_router(system_api.router, prefix="/api/system", tags=["System"])
app.include_router(history.router, prefix="/api/history", tags=["History"])
app.include_router(stream.router, prefix="/api/stream", tags=["Stream"])
app.include_router(metrics.router, prefix="/metrics", tags=["Metrics"])
app.include_router(batches.router, prefix="/api/batches", tags=["Batches"])
app.include_router(transcripts.router, prefix="/api/transcripts", tags=["Transcripts"])
app.include_router(subtitles.router, prefix="/api/jobs", tags=["Subtitles"])

# Include audit log routes
import sys
sys.path.insert(0, "/app")  # Add parent for shared imports
try:
    from shared.api.audit import create_audit_router
    from services.database import get_session
    audit_router = create_audit_router(get_session)
    app.include_router(audit_router, prefix="/api/audit", tags=["Audit"])
except ImportError:
    pass  # Shared module not available

# Mount static files for uploaded content
app.mount("/uploads", StaticFiles(directory=settings.upload_dir), name="uploads")
app.mount("/outputs", StaticFiles(directory=settings.output_dir), name="outputs")


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "version": "1.0.0"}


@app.get("/")
async def root():
    """Root endpoint with API info."""
    return {
        "name": "Speech-to-Text Server",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health",
    }
