"""Celery application and task configuration."""

from celery import Celery
from config import settings

celery_app = Celery(
    "stt_worker",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=[
        "workers.stt_worker",
        "workers.diarization_worker",
        "workers.tts_worker",
        "workers.sync_worker",
    ],
)

# Celery configuration
celery_app.conf.update(
    # Task settings
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    
    # Task routing
    task_routes={
        "workers.stt_worker.*": {"queue": "stt"},
        "workers.diarization_worker.*": {"queue": "diarization"},
        "workers.tts_worker.*": {"queue": "tts"},
        "workers.sync_worker.*": {"queue": "sync"},
    },
    
    # Result settings
    result_expires=3600,  # 1 hour
    
    # Worker settings
    worker_prefetch_multiplier=1,  # Process one task at a time (GPU bound)
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    
    # Retry settings
    task_default_retry_delay=60,
    task_max_retries=3,
)
