import { useParams, Link } from 'react-router-dom'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { formatDistanceToNow } from 'date-fns'
import { ArrowLeft, Clock, Loader2, Volume2, Eye, EyeOff } from 'lucide-react'
import { useState, useRef, useEffect } from 'react'
import { api } from '../lib/api'
import TranscriptViewer, { type TranscriptSegment } from '../components/TranscriptViewer'
import ExportMenu from '../components/ExportMenu'
import Waveform from '../components/Waveform'
import { useProgressStore, formatStage, type JobStage } from '../hooks/useWebSocket'

export default function JobDetails() {
  const { jobId } = useParams<{ jobId: string }>()
  const queryClient = useQueryClient()
  const [currentTime, setCurrentTime] = useState(0)
  const [showConfidence, setShowConfidence] = useState(false)
  const mediaRef = useRef<HTMLVideoElement | HTMLAudioElement>(null)
  
  // Get real-time progress from WebSocket
  const wsProgress = useProgressStore((s) => s.jobProgress[jobId || ''])
  
  const { data: job, isLoading } = useQuery({
    queryKey: ['job', jobId],
    queryFn: () => api.getJob(jobId!),
    refetchInterval: (query) => {
      const data = query.state.data
      return data?.status === 'completed' || data?.status === 'failed' ? false : 2000
    },
  })
  
  const { data: transcript } = useQuery({
    queryKey: ['transcript', jobId],
    queryFn: () => api.getTranscript(jobId!, 'json'),
    enabled: job?.status === 'completed',
  })
  
  // Update currentTime from media element
  useEffect(() => {
    const media = mediaRef.current
    if (!media) return
    
    const handleTimeUpdate = () => setCurrentTime(media.currentTime)
    media.addEventListener('timeupdate', handleTimeUpdate)
    return () => media.removeEventListener('timeupdate', handleTimeUpdate)
  }, [job?.status])
  
  // Seek handler
  const handleSeek = (time: number) => {
    if (mediaRef.current) {
      mediaRef.current.currentTime = time
      mediaRef.current.play()
    }
  }

  // Update segment handler
  const handleUpdateSegment = async (id: number, text: string) => {
    if (!transcript || typeof transcript === 'string') return
    
    // Cast to access dynamic id property from updated backend response
    const transcriptData = transcript as any
    if (transcriptData.id) {
       await api.updateSegment(transcriptData.id, id, text)
       await queryClient.invalidateQueries({ queryKey: ['transcript', jobId] })
    }
  }
  
  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <Loader2 className="w-8 h-8 text-olive-600 animate-spin" />
      </div>
    )
  }
  
  if (!job) {
    return (
      <div className="text-center py-12">
        <p className="text-surface-600">Job not found</p>
        <Link to="/" className="btn-primary mt-4 inline-block">
          Back to Dashboard
        </Link>
      </div>
    )
  }
  
  const isVideo = job.filename.match(/\.(mp4|webm|mkv|mov|avi)$/i)
  const currentStage = wsProgress?.stage || (job.status as JobStage)
  const currentProgress = wsProgress?.progress ?? job.progress
  
  // Parse transcript segments
  const segments: TranscriptSegment[] = 
    transcript && typeof transcript !== 'string' && transcript.segments
      ? transcript.segments.map((seg: any) => ({
          id: seg.id,
          start: seg.start,
          end: seg.end,
          text: seg.text,
          speaker: seg.speaker,
          words: seg.words?.map((w: any) => ({
            word: w.word,
            start: w.start,
            end: w.end,
            confidence: w.confidence,
          })),
        }))
      : []
  
  return (
    <div className="space-y-6 animate-fade-in">
      {/* Header */}
      <div className="flex items-start gap-4">
        <Link 
          to="/"
          className="p-2 hover:bg-cream-200 dark:hover:bg-dark-100 rounded-lg transition-colors"
        >
          <ArrowLeft className="w-5 h-5 text-surface-600" />
        </Link>
        
        <div className="flex-1">
          <h2 className="text-2xl font-serif text-surface-900">{job.filename}</h2>
          <div className="flex items-center gap-4 mt-2 text-sm text-surface-500">
            <span className="flex items-center gap-1">
              <Clock className="w-4 h-4" />
              {formatDistanceToNow(new Date(job.created_at), { addSuffix: true })}
            </span>
            {job.duration && (
              <span>{formatDuration(job.duration)}</span>
            )}
            {job.detected_language && (
              <span>Language: {job.detected_language}</span>
            )}
          </div>
        </div>
        
        <div className="flex items-center gap-3">
          {job.status === 'completed' && (
            <ExportMenu jobId={job.id} filename={job.filename.replace(/\.[^.]+$/, '')} />
          )}
          <StatusBadge status={currentStage} />
        </div>
      </div>
      
      {/* Progress (if processing) */}
      {job.status !== 'completed' && job.status !== 'failed' && (
        <div className="card">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              <Loader2 className="w-4 h-4 text-olive-600 animate-spin" />
              <span className="font-medium text-surface-800">{formatStage(currentStage)}</span>
            </div>
            <span className="text-sm font-medium text-olive-600">{Math.round(currentProgress)}%</span>
          </div>
          <div className="progress">
            <div 
              className="progress-bar" 
              style={{ width: `${currentProgress}%` }}
            />
          </div>
          {/* Stage indicators */}
          <div className="flex justify-between mt-3 text-xs">
            <StageIndicator stage="extracting_audio" current={currentStage} label="Extract" />
            <StageIndicator stage="transcribing" current={currentStage} label="Transcribe" />
            <StageIndicator stage="diarizing" current={currentStage} label="Diarize" />
            <StageIndicator stage="generating_tts" current={currentStage} label="TTS" />
            <StageIndicator stage="syncing" current={currentStage} label="Sync" />
          </div>
        </div>
      )}
      
      {/* Error message */}
      {job.status === 'failed' && job.error_message && (
        <div className="card bg-red-50 dark:bg-red-900/20 border-red-200 dark:border-red-800">
          <h3 className="font-medium text-red-800 dark:text-red-300 mb-2">Error</h3>
          <p className="text-red-700 dark:text-red-400">{job.error_message}</p>
        </div>
      )}
      
      {/* Main content grid */}
      {job.status === 'completed' && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Media Player */}
          <div className="card">
            <h3 className="text-lg font-serif text-surface-800 mb-4">Media Player</h3>
            
            <div className="bg-surface-900 rounded-xl overflow-hidden">
              {isVideo ? (
                <video
                  ref={mediaRef as React.RefObject<HTMLVideoElement>}
                  src={api.getOriginalFileUrl(job.id)}
                  controls
                  className="w-full aspect-video"
                >
                  <track 
                    kind="subtitles" 
                    src={api.getSubtitlesUrl(job.id, 'vtt')}
                    srcLang={job.detected_language || 'en'}
                    default
                  />
                </video>
              ) : (
                <Waveform
                  audioUrl={api.getOriginalFileUrl(job.id)}
                  currentTime={currentTime}
                  onSeek={handleSeek}
                  onTimeUpdate={setCurrentTime}
                  height={100}
                  className="mt-4"
                />
              )}
            </div>
            
            {/* TTS Audio (if available) */}
            {job.enable_tts && job.audio_url && (
              <div className="mt-4 p-4 bg-cream-50 dark:bg-dark-100 rounded-xl">
                <div className="flex items-center gap-2 mb-2">
                  <Volume2 className="w-4 h-4 text-olive-600" />
                  <h4 className="font-medium text-surface-700 dark:text-surface-300">Synthesized Audio</h4>
                </div>
                <audio
                  src={api.getTtsAudioUrl(job.id)}
                  controls
                  className="w-full"
                />
              </div>
            )}
          </div>
          
          {/* Transcript */}
          <div className="card flex flex-col" style={{ maxHeight: '70vh' }}>
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-serif text-surface-800">Transcript</h3>
              
              {/* Confidence toggle */}
              {segments.some(s => s.words?.some(w => w.confidence !== undefined)) && (
                <button
                  onClick={() => setShowConfidence(!showConfidence)}
                  className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm transition-colors ${
                    showConfidence 
                      ? 'bg-olive-100 dark:bg-olive-900/30 text-olive-700 dark:text-olive-300' 
                      : 'bg-cream-200 dark:bg-dark-100 text-surface-600'
                  }`}
                >
                  {showConfidence ? <Eye className="w-4 h-4" /> : <EyeOff className="w-4 h-4" />}
                  Confidence
                </button>
              )}
            </div>
            
            <TranscriptViewer
              segments={segments}
              currentTime={currentTime}
              onSeek={handleSeek}
              showConfidence={showConfidence}
              onUpdateSegment={handleUpdateSegment}
            />
          </div>
        </div>
      )}
    </div>
  )
}

function StatusBadge({ status }: { status: string }) {
  const configs: Record<string, { label: string; className: string }> = {
    completed: { label: 'Completed', className: 'bg-olive-100 dark:bg-olive-900/30 text-olive-700 dark:text-olive-300' },
    failed: { label: 'Failed', className: 'bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-300' },
    processing: { label: 'Processing', className: 'bg-amber-100 dark:bg-amber-900/30 text-amber-700 dark:text-amber-300' },
    transcribing: { label: 'Transcribing', className: 'bg-olive-100 dark:bg-olive-900/30 text-olive-700 dark:text-olive-300' },
    diarizing: { label: 'Diarizing', className: 'bg-purple-100 dark:bg-purple-900/30 text-purple-700 dark:text-purple-300' },
    generating_tts: { label: 'Generating TTS', className: 'bg-amber-100 dark:bg-amber-900/30 text-amber-700 dark:text-amber-300' },
    queued: { label: 'Queued', className: 'bg-cream-200 dark:bg-dark-100 text-surface-600' },
  }
  
  const config = configs[status] || { label: status, className: 'bg-cream-200 dark:bg-dark-100 text-surface-600' }
  
  return (
    <span className={`px-3 py-1 rounded-full text-sm font-medium ${config.className}`}>
      {config.label}
    </span>
  )
}

function StageIndicator({ stage, current, label }: { stage: JobStage, current: JobStage, label: string }) {
  const stages: JobStage[] = ['extracting_audio', 'transcribing', 'diarizing', 'generating_tts', 'syncing']
  const currentIndex = stages.indexOf(current)
  const stageIndex = stages.indexOf(stage)
  
  const isComplete = currentIndex > stageIndex
  const isCurrent = current === stage
  
  return (
    <div className="flex flex-col items-center">
      <div 
        className={`w-3 h-3 rounded-full transition-all duration-300 ${
          isComplete ? 'bg-olive-500' :
          isCurrent ? 'bg-olive-500 animate-pulse ring-2 ring-olive-300' :
          'bg-cream-300 dark:bg-dark-50'
        }`}
      />
      <span className={`mt-1 transition-colors ${
        isComplete || isCurrent ? 'text-olive-600 dark:text-olive-400 font-medium' : 'text-surface-400'
      }`}>
        {label}
      </span>
    </div>
  )
}

function formatDuration(seconds: number): string {
  const h = Math.floor(seconds / 3600)
  const m = Math.floor((seconds % 3600) / 60)
  const s = Math.floor(seconds % 60)
  
  if (h > 0) return `${h}h ${m}m ${s}s`
  if (m > 0) return `${m}m ${s}s`
  return `${s}s`
}
