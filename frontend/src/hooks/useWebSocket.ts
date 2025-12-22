import { useEffect, useRef, useCallback } from 'react'
import { create } from 'zustand'

// Job progress stages
export type JobStage = 
  | 'queued'
  | 'extracting_audio'
  | 'transcribing'
  | 'diarizing'
  | 'generating_tts'
  | 'syncing'
  | 'completed'
  | 'failed'

export interface JobProgress {
  jobId: string
  stage: JobStage
  progress: number  // 0-100
  eta?: number      // seconds remaining
  currentWord?: string
  message?: string
}

export interface QueueUpdate {
  type: 'job_progress' | 'job_complete' | 'job_failed' | 'queue_reorder'
  data: JobProgress | { jobId: string; error?: string } | { order: string[] }
}

// Zustand store for job progress
interface ProgressState {
  jobProgress: Record<string, JobProgress>
  setJobProgress: (jobId: string, progress: JobProgress) => void
  removeJob: (jobId: string) => void
  clearAll: () => void
}

export const useProgressStore = create<ProgressState>((set) => ({
  jobProgress: {},
  setJobProgress: (jobId, progress) => 
    set((state) => ({
      jobProgress: { ...state.jobProgress, [jobId]: progress }
    })),
  removeJob: (jobId) =>
    set((state) => {
      const { [jobId]: _, ...rest } = state.jobProgress
      return { jobProgress: rest }
    }),
  clearAll: () => set({ jobProgress: {} }),
}))

// WebSocket connection hook
export function useWebSocket(url: string = '/api/queue/ws') {
  const wsRef = useRef<WebSocket | null>(null)
  const reconnectTimeoutRef = useRef<ReturnType<typeof setTimeout>>()
  const reconnectAttempts = useRef(0)
  const maxReconnectAttempts = 10
  const setJobProgress = useProgressStore((s) => s.setJobProgress)

  const connect = useCallback(() => {
    // Build full WebSocket URL
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const host = window.location.host
    const fullUrl = `${protocol}//${host}${url}`
    
    try {
      const ws = new WebSocket(fullUrl)
      wsRef.current = ws

      ws.onopen = () => {
        console.log('[WebSocket] Connected')
        reconnectAttempts.current = 0
      }

      ws.onmessage = (event) => {
        try {
          const update: QueueUpdate = JSON.parse(event.data)
          
          switch (update.type) {
            case 'job_progress':
              const progress = update.data as JobProgress
              setJobProgress(progress.jobId, progress)
              break
              
            case 'job_complete':
              const completeData = update.data as { jobId: string }
              setJobProgress(completeData.jobId, {
                jobId: completeData.jobId,
                stage: 'completed',
                progress: 100,
              })
              break
              
            case 'job_failed':
              const failData = update.data as { jobId: string; error?: string }
              setJobProgress(failData.jobId, {
                jobId: failData.jobId,
                stage: 'failed',
                progress: 0,
                message: failData.error,
              })
              break
              
            case 'queue_reorder':
              // Trigger a refetch of the queue
              break
          }
        } catch (e) {
          console.error('[WebSocket] Failed to parse message:', e)
        }
      }

      ws.onerror = (error) => {
        console.error('[WebSocket] Error:', error)
      }

      ws.onclose = () => {
        console.log('[WebSocket] Disconnected')
        wsRef.current = null
        
        // Exponential backoff reconnection
        if (reconnectAttempts.current < maxReconnectAttempts) {
          const delay = Math.min(1000 * Math.pow(2, reconnectAttempts.current), 30000)
          console.log(`[WebSocket] Reconnecting in ${delay}ms...`)
          reconnectTimeoutRef.current = setTimeout(() => {
            reconnectAttempts.current++
            connect()
          }, delay)
        }
      }
    } catch (e) {
      console.error('[WebSocket] Failed to connect:', e)
    }
  }, [url, setJobProgress])

  const disconnect = useCallback(() => {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current)
    }
    if (wsRef.current) {
      wsRef.current.close()
      wsRef.current = null
    }
  }, [])

  useEffect(() => {
    connect()
    return () => disconnect()
  }, [connect, disconnect])

  return {
    isConnected: wsRef.current?.readyState === WebSocket.OPEN,
    disconnect,
    reconnect: connect,
  }
}

// Helper to format stage for display
export function formatStage(stage: JobStage): string {
  const labels: Record<JobStage, string> = {
    queued: 'Queued',
    extracting_audio: 'Extracting Audio',
    transcribing: 'Transcribing',
    diarizing: 'Identifying Speakers',
    generating_tts: 'Generating Speech',
    syncing: 'Syncing Audio',
    completed: 'Completed',
    failed: 'Failed',
  }
  return labels[stage] || stage
}

// Helper to format ETA
export function formatEta(seconds?: number): string {
  if (!seconds || seconds <= 0) return ''
  
  if (seconds < 60) {
    return `${Math.ceil(seconds)}s remaining`
  } else if (seconds < 3600) {
    const mins = Math.floor(seconds / 60)
    const secs = Math.ceil(seconds % 60)
    return `${mins}m ${secs}s remaining`
  } else {
    const hours = Math.floor(seconds / 3600)
    const mins = Math.floor((seconds % 3600) / 60)
    return `${hours}h ${mins}m remaining`
  }
}

// Stage to color mapping
export function getStageColor(stage: JobStage): string {
  const colors: Record<JobStage, string> = {
    queued: 'bg-surface-400',
    extracting_audio: 'bg-blue-500',
    transcribing: 'bg-olive-500',
    diarizing: 'bg-purple-500',
    generating_tts: 'bg-amber-500',
    syncing: 'bg-cyan-500',
    completed: 'bg-green-500',
    failed: 'bg-red-500',
  }
  return colors[stage] || 'bg-surface-400'
}
