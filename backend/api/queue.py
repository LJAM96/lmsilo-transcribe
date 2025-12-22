"""Queue management API routes with WebSocket support."""

from typing import List
from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
import json
import asyncio

from services.database import get_session, async_session_maker
from models.database import Job
from schemas.job import JobStatus, JobResponse, OutputFormat

router = APIRouter()


class ConnectionManager:
    """Manage WebSocket connections for real-time queue updates."""
    
    def __init__(self):
        self.active_connections: List[WebSocket] = []
    
    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
    
    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
    
    async def broadcast(self, message: dict):
        """Send message to all connected clients."""
        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception:
                disconnected.append(connection)
        
        for conn in disconnected:
            self.disconnect(conn)


manager = ConnectionManager()


@router.get("")
async def get_queue_status(
    session: AsyncSession = Depends(get_session),
):
    """
    Get current queue status and statistics.
    """
    # Count jobs by status
    status_counts = {}
    for status in JobStatus:
        result = await session.execute(
            select(func.count(Job.id)).where(Job.status == status)
        )
        status_counts[status.value] = result.scalar() or 0
    
    # Get queued jobs ordered by priority and creation time
    result = await session.execute(
        select(Job)
        .where(Job.status.in_([JobStatus.QUEUED, JobStatus.PROCESSING, JobStatus.TRANSCRIBING]))
        .order_by(Job.priority.asc(), Job.created_at.asc())
        .limit(50)
    )
    queued_jobs = result.scalars().all()
    
    return {
        "status_counts": status_counts,
        "total_pending": status_counts.get("pending", 0) + status_counts.get("queued", 0),
        "total_processing": sum(
            status_counts.get(s, 0)
            for s in ["processing", "transcribing", "diarizing", "synthesizing", "syncing"]
        ),
        "total_completed": status_counts.get("completed", 0),
        "total_failed": status_counts.get("failed", 0),
        "queue": [
            {
                "id": job.id,
                "filename": job.filename,
                "status": job.status.value,
                "progress": job.progress,
                "priority": job.priority,
                "position": i + 1,
                "created_at": job.created_at.isoformat(),
                "started_at": job.started_at.isoformat() if job.started_at else None,
            }
            for i, job in enumerate(queued_jobs)
        ],
    }


@router.post("/{job_id}/priority")
async def update_job_priority(
    job_id: str,
    priority: int,
    session: AsyncSession = Depends(get_session),
):
    """
    Update the priority of a queued job.
    
    Priority 1 is highest, 10 is lowest.
    """
    if priority < 1 or priority > 10:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="Priority must be between 1 and 10")
    
    result = await session.execute(select(Job).where(Job.id == job_id))
    job = result.scalar_one_or_none()
    
    if not job:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Job not found")
    
    if job.status not in [JobStatus.PENDING, JobStatus.QUEUED]:
        from fastapi import HTTPException
        raise HTTPException(
            status_code=400,
            detail="Can only change priority for pending/queued jobs",
        )
    
    job.priority = priority
    await session.commit()
    
    # Notify all clients about the change
    await manager.broadcast({
        "type": "priority_changed",
        "job_id": job_id,
        "priority": priority,
    })
    
    return {"message": "Priority updated", "job_id": job_id, "priority": priority}


@router.post("/{job_id}/move")
async def move_job_in_queue(
    job_id: str,
    new_position: int,
    session: AsyncSession = Depends(get_session),
):
    """
    Move a job to a specific position in the queue.
    """
    result = await session.execute(select(Job).where(Job.id == job_id))
    job = result.scalar_one_or_none()
    
    if not job:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Job not found")
    
    if job.status not in [JobStatus.PENDING, JobStatus.QUEUED]:
        from fastapi import HTTPException
        raise HTTPException(
            status_code=400,
            detail="Can only reorder pending/queued jobs",
        )
    
    job.queue_position = new_position
    await session.commit()
    
    await manager.broadcast({
        "type": "queue_reordered",
        "job_id": job_id,
        "position": new_position,
    })
    
    return {"message": "Job moved", "job_id": job_id, "position": new_position}


from pydantic import BaseModel

class ReorderRequest(BaseModel):
    """Request body for batch queue reorder."""
    job_ids: List[str]


@router.post("/reorder")
async def batch_reorder_queue(
    request: ReorderRequest,
    session: AsyncSession = Depends(get_session),
):
    """
    Reorder multiple jobs in the queue at once.
    
    Accepts an array of job IDs in the desired order.
    Priority is assigned based on position (1 = highest priority).
    """
    from fastapi import HTTPException
    
    if not request.job_ids:
        raise HTTPException(status_code=400, detail="job_ids list cannot be empty")
    
    # Fetch all jobs
    result = await session.execute(
        select(Job).where(Job.id.in_(request.job_ids))
    )
    jobs_map = {job.id: job for job in result.scalars().all()}
    
    # Verify all jobs exist and are reorderable
    for job_id in request.job_ids:
        if job_id not in jobs_map:
            raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
        
        job = jobs_map[job_id]
        if job.status not in [JobStatus.PENDING, JobStatus.QUEUED]:
            raise HTTPException(
                status_code=400,
                detail=f"Job {job_id} is not in a reorderable state (status: {job.status.value})",
            )
    
    # Update priorities based on position
    # Lower position = higher priority (1-10 scale mapped from position)
    for position, job_id in enumerate(request.job_ids):
        job = jobs_map[job_id]
        # Map position to priority 1-10 (first 10 get priority 1-10, rest get 10)
        job.priority = min(position + 1, 10)
        job.queue_position = position + 1
    
    await session.commit()
    
    # Notify all clients about the reorder
    await manager.broadcast({
        "type": "queue_batch_reordered",
        "job_ids": request.job_ids,
    })
    
    return {
        "message": "Queue reordered",
        "jobs_updated": len(request.job_ids),
    }


@router.websocket("/ws")
async def queue_websocket(websocket: WebSocket):
    """
    WebSocket endpoint for real-time queue updates.
    
    Clients receive messages when:
    - A new job is added
    - A job status changes
    - A job completes or fails
    - Queue priority/order changes
    """
    await manager.connect(websocket)
    
    try:
        # Send initial queue state
        async with async_session_maker() as session:
            result = await session.execute(
                select(Job)
                .where(Job.status.in_([
                    JobStatus.QUEUED, JobStatus.PROCESSING,
                    JobStatus.TRANSCRIBING, JobStatus.DIARIZING,
                    JobStatus.SYNTHESIZING,
                ]))
                .order_by(Job.priority.asc(), Job.created_at.asc())
            )
            jobs = result.scalars().all()
            
            await websocket.send_json({
                "type": "initial_state",
                "queue": [
                    {
                        "id": job.id,
                        "filename": job.filename,
                        "status": job.status.value,
                        "progress": job.progress,
                        "priority": job.priority,
                    }
                    for job in jobs
                ],
            })
        
        # Keep connection alive and handle client messages
        while True:
            try:
                data = await asyncio.wait_for(
                    websocket.receive_text(),
                    timeout=30.0,
                )
                
                # Handle ping/pong for keepalive
                message = json.loads(data)
                if message.get("type") == "ping":
                    await websocket.send_json({"type": "pong"})
                    
            except asyncio.TimeoutError:
                # Send keepalive ping
                await websocket.send_json({"type": "ping"})
                
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception:
        manager.disconnect(websocket)


async def notify_job_update(job: Job, update_type: str = "status_changed"):
    """
    Broadcast a job update to all connected WebSocket clients.
    
    Called by workers when job state changes.
    """
    await manager.broadcast({
        "type": update_type,
        "job": {
            "id": job.id,
            "filename": job.filename,
            "status": job.status.value,
            "progress": job.progress,
            "priority": job.priority,
            "error_message": job.error_message,
        },
    })
