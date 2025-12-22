"""Transcript management API."""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from services.database import get_session
from models.database import Transcript, TranscriptSegment

router = APIRouter()


class SegmentUpdate(BaseModel):
    """Request body for updating a segment."""
    text: str
    speaker: Optional[str] = None


@router.patch("/{transcript_id}/segments/{segment_id}")
async def update_segment(
    transcript_id: str,
    segment_id: int,
    update: SegmentUpdate,
    session: AsyncSession = Depends(get_session),
):
    """
    Update a transcript segment's text or speaker label.
    
    This allows inline editing of transcripts.
    """
    # Verify transcript exists
    result = await session.execute(
        select(Transcript).where(Transcript.id == transcript_id)
    )
    transcript = result.scalar_one_or_none()
    
    if not transcript:
        raise HTTPException(404, "Transcript not found")
    
    # Get segment
    result = await session.execute(
        select(TranscriptSegment).where(
            TranscriptSegment.segment_index == segment_id,
            TranscriptSegment.transcript_id == transcript_id,
        )
    )
    segment = result.scalar_one_or_none()
    
    if not segment:
        raise HTTPException(404, "Segment not found")
    
    # Update segment
    segment.text = update.text
    if update.speaker is not None:
        segment.speaker = update.speaker
    
    # Regenerate full text
    result = await session.execute(
        select(TranscriptSegment)
        .where(TranscriptSegment.transcript_id == transcript_id)
        .order_by(TranscriptSegment.start_time)
    )
    all_segments = result.scalars().all()
    transcript.full_text = " ".join(s.text for s in all_segments)
    
    await session.commit()
    
    return {
        "id": segment.id,
        "text": segment.text,
        "speaker": segment.speaker,
        "start_time": segment.start_time,
        "end_time": segment.end_time,
    }


@router.get("/{transcript_id}")
async def get_transcript(
    transcript_id: str,
    session: AsyncSession = Depends(get_session),
):
    """Get transcript with all segments."""
    result = await session.execute(
        select(Transcript).where(Transcript.id == transcript_id)
    )
    transcript = result.scalar_one_or_none()
    
    if not transcript:
        raise HTTPException(404, "Transcript not found")
    
    result = await session.execute(
        select(TranscriptSegment)
        .where(TranscriptSegment.transcript_id == transcript_id)
        .order_by(TranscriptSegment.start_time)
    )
    segments = result.scalars().all()
    
    return {
        "id": transcript.id,
        "job_id": transcript.job_id,
        "language": transcript.language,
        "duration": transcript.duration,
        "word_count": transcript.word_count,
        "full_text": transcript.full_text,
        "segments": [
            {
                "id": s.id,
                "index": s.segment_index,
                "start_time": s.start_time,
                "end_time": s.end_time,
                "text": s.text,
                "speaker": s.speaker,
                "confidence": s.confidence,
            }
            for s in segments
        ],
    }
