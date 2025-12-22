# API Reference

The backend provides a RESTful API documented via OpenAPI (Swagger).
When running the server locally, full interactive docs are available at `http://localhost:8000/docs`.

## Base URL
`http://localhost:8000/api`

## Endpoints

### Jobs
*   `POST /jobs`: Create a new transcription job.
    *   **Body**: `multipart/form-data`
    *   **Params**: `file` (binary), `language`, `model_id`, `enable_diarization`.
*   `GET /jobs`: List all jobs ( supports filtering by status).
*   `GET /jobs/{id}`: Get job details and status.
*   `DELETE /jobs/{id}`: Delete a job and its files.

### Batches
*   `POST /batches`: Create a batch of jobs (5+ files).
*   `GET /batches`: List batches.
*   `GET /batches/{id}/export`: Download batch transcripts as ZIP.

### Transcripts
*   `GET /jobs/{id}/transcript`: Get transcript in various formats.
    *   **Query**: `format` (`json`, `srt`, `vtt`, `txt`).
*   `PATCH /transcripts/{id}/segments/{seg_id}`: Inline edit specific segment.
    *   **Body**: `{"text": "new text", "speaker": "Speaker 1"}`

### Files
*   `GET /files/{job_id}/original`: Stream original audio/video.
*   `GET /files/{job_id}/subtitles`: Stream subtitle file (`vtt` or `srt`).

### Subtitles
*   `POST /jobs/{id}/burn-subtitles`: Trigger video processing to burn in subtitles.

## WebSocket API
`ws://localhost:8000/ws`

Connect to receive real-time events about job progress.
**Events**:
```json
{
  "type": "job_update",
  "job_id": "uuid",
  "status": "transcribing",
  "progress": 45.5,
  "stage": "transcribing"
}
```
