"""Model management API routes with pluggable engine support."""

from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from services.database import get_session
from models.database import Model
from schemas.model import (
    ModelCreate,
    ModelResponse,
    ModelInfo,
    ModelType,
    ModelEngine,
    ModelSource,
    ModelDownloadRequest,
    BUILTIN_MODELS,
    get_engine_for_type,
)

router = APIRouter()


@router.get("/engines", response_model=dict)
async def list_engines():
    """
    List all supported engines grouped by model type.
    
    Returns available engines for STT, diarization, and TTS.
    """
    return {
        "whisper": [e.value for e in get_engine_for_type(ModelType.WHISPER)],
        "diarization": [e.value for e in get_engine_for_type(ModelType.DIARIZATION)],
        "tts": [e.value for e in get_engine_for_type(ModelType.TTS)],
    }


@router.get("/builtin", response_model=dict)
async def list_builtin_models():
    """
    List all pre-defined models available for each engine.
    
    These can be registered and downloaded via the POST endpoint.
    """
    result = {}
    for engine, models in BUILTIN_MODELS.items():
        result[engine.value] = {
            model_id: info.model_dump()
            for model_id, info in models.items()
        }
    return result


@router.post("", response_model=ModelResponse, status_code=201)
async def register_model(
    model: ModelCreate,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
):
    """
    Register a new model.
    
    Supports HuggingFace models, local uploads, or direct URLs.
    The model will be downloaded in the background if not already available.
    """
    # Check if model already exists
    result = await session.execute(
        select(Model).where(
            Model.engine == model.engine,
            Model.model_id == model.model_id,
        )
    )
    existing = result.scalar_one_or_none()
    
    if existing:
        raise HTTPException(
            status_code=400,
            detail=f"Model {model.model_id} for engine {model.engine.value} already registered",
        )
    
    # If setting as default, unset other defaults of same type
    if model.is_default:
        result = await session.execute(
            select(Model).where(
                Model.model_type == model.model_type,
                Model.is_default == True,
            )
        )
        for existing_default in result.scalars():
            existing_default.is_default = False
    
    # Create model record
    db_model = Model(
        name=model.name,
        model_type=model.model_type,
        engine=model.engine,
        source=model.source,
        model_id=model.model_id,
        revision=model.revision,
        info=model.info.model_dump(),
        compute_type=model.compute_type,
        device=model.device,
        is_default=model.is_default,
        is_downloaded=False,
    )
    
    session.add(db_model)
    await session.commit()
    await session.refresh(db_model)
    
    # Queue download in background
    if model.source in [ModelSource.HUGGINGFACE, ModelSource.URL]:
        background_tasks.add_task(download_model_task, db_model.id)
    
    return ModelResponse(
        id=db_model.id,
        name=db_model.name,
        model_type=db_model.model_type,
        engine=db_model.engine,
        source=db_model.source,
        model_id=db_model.model_id,
        revision=db_model.revision,
        info=ModelInfo(**db_model.info),
        is_default=db_model.is_default,
        compute_type=db_model.compute_type,
        device=db_model.device,
        is_downloaded=db_model.is_downloaded,
        download_progress=db_model.download_progress,
        local_path=db_model.local_path,
        created_at=db_model.created_at,
        last_used_at=db_model.last_used_at,
    )


@router.get("", response_model=List[ModelResponse])
async def list_models(
    model_type: Optional[ModelType] = Query(default=None),
    engine: Optional[ModelEngine] = Query(default=None),
    downloaded_only: bool = Query(default=False),
    session: AsyncSession = Depends(get_session),
):
    """
    List all registered models with optional filters.
    """
    query = select(Model).order_by(Model.model_type, Model.name)
    
    if model_type:
        query = query.where(Model.model_type == model_type)
    if engine:
        query = query.where(Model.engine == engine)
    if downloaded_only:
        query = query.where(Model.is_downloaded == True)
    
    result = await session.execute(query)
    models = result.scalars().all()
    
    return [
        ModelResponse(
            id=m.id,
            name=m.name,
            model_type=m.model_type,
            engine=m.engine,
            source=m.source,
            model_id=m.model_id,
            revision=m.revision,
            info=ModelInfo(**m.info) if m.info else ModelInfo(),
            is_default=m.is_default,
            compute_type=m.compute_type,
            device=m.device,
            is_downloaded=m.is_downloaded,
            download_progress=m.download_progress,
            local_path=m.local_path,
            created_at=m.created_at,
            last_used_at=m.last_used_at,
        )
        for m in models
    ]


@router.get("/{model_id}", response_model=ModelResponse)
async def get_model(
    model_id: str,
    session: AsyncSession = Depends(get_session),
):
    """Get details for a specific model."""
    result = await session.execute(select(Model).where(Model.id == model_id))
    model = result.scalar_one_or_none()
    
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")
    
    return ModelResponse(
        id=model.id,
        name=model.name,
        model_type=model.model_type,
        engine=model.engine,
        source=model.source,
        model_id=model.model_id,
        revision=model.revision,
        info=ModelInfo(**model.info) if model.info else ModelInfo(),
        is_default=model.is_default,
        compute_type=model.compute_type,
        device=model.device,
        is_downloaded=model.is_downloaded,
        download_progress=model.download_progress,
        local_path=model.local_path,
        created_at=model.created_at,
        last_used_at=model.last_used_at,
    )


@router.post("/{model_id}/download", status_code=202)
async def download_model(
    model_id: str,
    request: ModelDownloadRequest,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
):
    """
    Trigger download for a registered model.
    """
    result = await session.execute(select(Model).where(Model.id == model_id))
    model = result.scalar_one_or_none()
    
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")
    
    if model.is_downloaded and not request.force:
        return {"message": "Model already downloaded", "path": model.local_path}
    
    background_tasks.add_task(download_model_task, model_id)
    
    return {"message": "Download started", "model_id": model_id}


@router.post("/{model_id}/set-default", response_model=ModelResponse)
async def set_default_model(
    model_id: str,
    session: AsyncSession = Depends(get_session),
):
    """Set a model as the default for its type."""
    result = await session.execute(select(Model).where(Model.id == model_id))
    model = result.scalar_one_or_none()
    
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")
    
    # Unset other defaults
    result = await session.execute(
        select(Model).where(
            Model.model_type == model.model_type,
            Model.is_default == True,
        )
    )
    for other in result.scalars():
        other.is_default = False
    
    model.is_default = True
    await session.commit()
    await session.refresh(model)
    
    return ModelResponse(
        id=model.id,
        name=model.name,
        model_type=model.model_type,
        engine=model.engine,
        source=model.source,
        model_id=model.model_id,
        revision=model.revision,
        info=ModelInfo(**model.info) if model.info else ModelInfo(),
        is_default=model.is_default,
        compute_type=model.compute_type,
        device=model.device,
        is_downloaded=model.is_downloaded,
        download_progress=model.download_progress,
        local_path=model.local_path,
        created_at=model.created_at,
        last_used_at=model.last_used_at,
    )


@router.delete("/{model_id}", status_code=204)
async def delete_model(
    model_id: str,
    delete_files: bool = Query(default=True),
    session: AsyncSession = Depends(get_session),
):
    """
    Delete a model registration and optionally its downloaded files.
    """
    import shutil
    
    result = await session.execute(select(Model).where(Model.id == model_id))
    model = result.scalar_one_or_none()
    
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")
    
    # Delete local files if requested
    if delete_files and model.local_path:
        import os
        if os.path.isdir(model.local_path):
            shutil.rmtree(model.local_path, ignore_errors=True)
        elif os.path.exists(model.local_path):
            os.remove(model.local_path)
    
    await session.delete(model)
    await session.commit()


async def download_model_task(model_id: str):
    """
    Background task to download a model.
    
    This handles different engines and sources appropriately.
    """
    from services.database import async_session_maker
    from services.model_downloader import download_model_for_engine
    from config import settings
    
    async with async_session_maker() as session:
        result = await session.execute(select(Model).where(Model.id == model_id))
        model = result.scalar_one_or_none()
        
        if not model:
            return
        
        try:
            # Update progress
            model.download_progress = 0.0
            await session.commit()
            
            # Download based on engine
            local_path = await download_model_for_engine(
                engine=model.engine,
                model_id=model.model_id,
                source=model.source,
                revision=model.revision,
                target_dir=settings.model_dir,
                progress_callback=lambda p: update_download_progress(session, model, p),
            )
            
            model.local_path = str(local_path)
            model.is_downloaded = True
            model.download_progress = 100.0
            await session.commit()
            
        except Exception as e:
            model.download_progress = None
            model.info = {**model.info, "download_error": str(e)}
            await session.commit()
            raise


async def update_download_progress(session: AsyncSession, model: Model, progress: float):
    """Update download progress for a model."""
    model.download_progress = progress
    await session.commit()
