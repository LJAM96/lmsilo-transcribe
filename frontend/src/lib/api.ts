import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  timeout: 30000,
})

// Types
export interface Job {
  id: string
  filename: string
  status: string
  progress: number
  language: string
  detected_language?: string
  model_id: string
  enable_diarization: boolean
  enable_tts: boolean
  sync_tts_timing: boolean
  output_formats: string[]
  priority: number
  queue_position?: number
  created_at: string
  started_at?: string
  completed_at?: string
  duration?: number
  transcript_url?: string
  audio_url?: string
  error_message?: string
}

export interface Model {
  id: string
  name: string
  model_type: 'whisper' | 'diarization' | 'tts'
  engine: string
  source: string
  model_id: string
  is_default: boolean
  is_downloaded: boolean
  download_progress?: number
  info: {
    size_mb?: number
    languages?: string[]
    description?: string
    recommended_vram_gb?: number
  }
}

export interface QueueStatus {
  status_counts: Record<string, number>
  total_pending: number
  total_processing: number
  total_completed: number
  total_failed: number
  queue: Array<{
    id: string
    filename: string
    status: string
    progress: number
    priority: number
    position: number
    created_at: string
    started_at?: string
  }>
}

export interface SystemEvaluation {
  hardware: {
    summary: string
    score: number
    score_description: string
    can_run_gpu: boolean
    gpu_memory_gb: number
    recommended_compute_type: string
    max_concurrent_jobs: number
  }
  compatibility: Record<string, Record<string, boolean>>
  warnings: string[]
  recommendations: Array<{
    current: string
    recommended: string
    reason: string
    expected_speedup: string
    quality_tradeoff: string
  }>
  estimate?: {
    realtime_factor: number
    realtime_description: string
    estimated_seconds: number
    estimated_time: string
    confidence: string
    bottleneck: string
  }
}

export interface TranscriptResponse {
  job_id: string
  language: string
  duration: number
  segments: Array<{
    id: number
    start: number
    end: number
    text: string
    speaker?: string
    confidence?: number
    words?: Array<{
      word: string
      start: number
      end: number
      probability: number
    }>
  }>
  speakers?: string[]
}

// API functions
export const apiClient = {
  // Jobs
  createJob: async (formData: FormData): Promise<Job> => {
    const response = await api.post('/jobs', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      timeout: 120000, // 2 minutes for large files
    })
    return response.data
  },

  getJobs: async (status?: string): Promise<Job[]> => {
    const params = status ? { status } : {}
    const response = await api.get('/jobs', { params })
    return response.data
  },

  getJob: async (jobId: string): Promise<Job> => {
    const response = await api.get(`/jobs/${jobId}`)
    return response.data
  },

  deleteJob: async (jobId: string): Promise<void> => {
    await api.delete(`/jobs/${jobId}`)
  },

  getTranscript: async (jobId: string, format: string = 'json'): Promise<TranscriptResponse | string> => {
    const response = await api.get(`/jobs/${jobId}/transcript`, {
      params: { format },
      responseType: format === 'json' ? 'json' : 'text',
    })
    return response.data
  },

  updateSegment: async (transcriptId: string, segmentIndex: number, text: string, speaker?: string): Promise<void> => {
    await api.patch(`/transcripts/${transcriptId}/segments/${segmentIndex}`, { text, speaker })
  },

  // Models
  getModels: async (modelType?: string): Promise<Model[]> => {
    const params = modelType ? { model_type: modelType } : {}
    const response = await api.get('/models', { params })
    return response.data
  },

  getModel: async (modelId: string): Promise<Model> => {
    const response = await api.get(`/models/${modelId}`)
    return response.data
  },

  registerModel: async (model: Partial<Model>): Promise<Model> => {
    const response = await api.post('/models', model)
    return response.data
  },

  downloadModel: async (modelId: string): Promise<void> => {
    await api.post(`/models/${modelId}/download`, { model_id: modelId, force: false })
  },

  setDefaultModel: async (modelId: string): Promise<Model> => {
    const response = await api.post(`/models/${modelId}/set-default`)
    return response.data
  },

  deleteModel: async (modelId: string, deleteFiles: boolean = true): Promise<void> => {
    await api.delete(`/models/${modelId}`, { params: { delete_files: deleteFiles } })
  },

  getEngines: async (): Promise<Record<string, string[]>> => {
    const response = await api.get('/models/engines')
    return response.data
  },

  getBuiltinModels: async (): Promise<Record<string, Record<string, object>>> => {
    const response = await api.get('/models/builtin')
    return response.data
  },

  // Queue
  getQueue: async (): Promise<QueueStatus> => {
    const response = await api.get('/queue')
    return response.data
  },

  updatePriority: async (jobId: string, priority: number): Promise<void> => {
    await api.post(`/queue/${jobId}/priority`, null, { params: { priority } })
  },

  reorderQueue: async (jobIds: string[]): Promise<void> => {
    await api.post('/queue/reorder', { job_ids: jobIds })
  },

  // System
  getHardware: async () => {
    const response = await api.get('/system/hardware')
    return response.data
  },

  getGpuUsage: async (): Promise<{
    gpus: Array<{
      index: number
      memory_used_mb: number
      memory_total_mb: number
      memory_percent: number
      utilization_percent: number | null
      temperature_c: number | null
    }>
    message?: string
  }> => {
    const response = await api.get('/system/gpu-usage')
    return response.data
  },

  evaluateSystem: async (params: {
    stt_model?: string
    diarization_model?: string
    tts_model?: string
    audio_duration?: number
  }): Promise<SystemEvaluation> => {
    const response = await api.get('/system/evaluate', { params })
    return response.data
  },

  getBenchmark: async (model: string = 'base'): Promise<object> => {
    const response = await api.get('/system/benchmark', { params: { model } })
    return response.data
  },

  // Jobs - Speaker management
  updateSpeakers: async (jobId: string, speakerMap: Record<string, string>): Promise<void> => {
    await api.patch(`/jobs/${jobId}/speakers`, { speaker_map: speakerMap })
  },

  // Files
  getOriginalFileUrl: (jobId: string): string => `/api/files/${jobId}/original`,
  getTtsAudioUrl: (jobId: string): string => `/api/files/${jobId}/audio`,
  getVideoWithTtsUrl: (jobId: string): string => `/api/files/${jobId}/video-with-tts`,
  getSubtitlesUrl: (jobId: string, format: 'srt' | 'vtt' = 'vtt'): string => 
    `/api/files/${jobId}/subtitles?format=${format}`,
}

// Export as default for convenience
export { apiClient as api }
