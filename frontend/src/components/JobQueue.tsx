import { Link } from 'react-router-dom'
import { formatDistanceToNow } from 'date-fns'
import { FileAudio, CheckCircle2, XCircle, Clock, Loader2, Volume2, Users, Mic, Wand2 } from 'lucide-react'
import { useProgressStore, formatStage, formatEta, type JobStage } from '../hooks/useWebSocket'

interface Job {
  id: string
  filename: string
  status: string
  progress: number
  priority: number
  position: number
  created_at: string
  started_at?: string
}

interface JobQueueProps {
  jobs: Job[]
}

export default function JobQueue({ jobs }: JobQueueProps) {
  if (jobs.length === 0) {
    return (
      <div className="text-center py-12">
        <div className="w-16 h-16 bg-cream-200 dark:bg-dark-100 rounded-2xl flex items-center justify-center mx-auto mb-4">
          <FileAudio className="w-8 h-8 text-surface-400" />
        </div>
        <p className="text-surface-500">No jobs in queue</p>
        <p className="text-sm text-surface-400 mt-1">Upload a file to get started</p>
      </div>
    )
  }
  
  return (
    <div className="space-y-3">
      {jobs.map((job) => (
        <JobCard key={job.id} job={job} />
      ))}
    </div>
  )
}

function JobCard({ job }: { job: Job }) {
  // Get real-time progress from WebSocket store
  const wsProgress = useProgressStore((s) => s.jobProgress[job.id])
  
  // Use WebSocket progress if available, otherwise fall back to job data
  const currentStage = wsProgress?.stage || (job.status as JobStage)
  const currentProgress = wsProgress?.progress ?? job.progress
  const eta = wsProgress?.eta
  
  const statusConfig = getStatusConfig(currentStage)
  const isProcessing = !['completed', 'failed', 'queued'].includes(currentStage)
  
  return (
    <Link
      to={`/jobs/${job.id}`}
      className="block p-4 bg-cream-50 dark:bg-dark-100 hover:bg-cream-100 dark:hover:bg-dark-50 rounded-xl transition-colors duration-200 group"
    >
      <div className="flex items-center gap-4">
        {/* Status Icon */}
        <div className={`w-10 h-10 rounded-xl flex items-center justify-center flex-shrink-0 ${statusConfig.bgColor}`}>
          <statusConfig.icon className={`w-5 h-5 ${statusConfig.iconColor}`} />
        </div>
        
        {/* Job Info */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <p className="font-medium text-surface-800 truncate group-hover:text-olive-700 transition-colors">
              {job.filename}
            </p>
            {/* Stage pill */}
            <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium ${statusConfig.pillClass}`}>
              <statusConfig.stageIcon className="w-3 h-3" />
              {formatStage(currentStage)}
            </span>
          </div>
          
          <div className="flex items-center gap-3 mt-1 text-sm text-surface-500">
            <span>#{job.position} in queue</span>
            <span>•</span>
            <span>{formatDistanceToNow(new Date(job.created_at), { addSuffix: true })}</span>
            {eta && (
              <>
                <span>•</span>
                <span className="text-olive-600 dark:text-olive-400">{formatEta(eta)}</span>
              </>
            )}
          </div>
          
          {/* Progress bar with stages */}
          {isProcessing && (
            <div className="mt-2">
              <div className="progress">
                <div 
                  className={`progress-bar ${statusConfig.progressColor}`}
                  style={{ width: `${currentProgress}%` }}
                />
              </div>
              {/* Stage indicators */}
              <div className="flex justify-between mt-1">
                <StageIndicator stage="extracting_audio" current={currentStage} label="Extract" />
                <StageIndicator stage="transcribing" current={currentStage} label="Transcribe" />
                <StageIndicator stage="diarizing" current={currentStage} label="Diarize" />
                <StageIndicator stage="generating_tts" current={currentStage} label="TTS" />
                <StageIndicator stage="syncing" current={currentStage} label="Sync" />
              </div>
            </div>
          )}
        </div>
        
        {/* Progress percentage */}
        {isProcessing && (
          <span className="text-lg font-semibold text-olive-600 dark:text-olive-400">
            {Math.round(currentProgress)}%
          </span>
        )}
      </div>
    </Link>
  )
}

// Stage indicator dot
function StageIndicator({ stage, current, label }: { stage: JobStage, current: JobStage, label: string }) {
  const stages: JobStage[] = ['extracting_audio', 'transcribing', 'diarizing', 'generating_tts', 'syncing']
  const currentIndex = stages.indexOf(current)
  const stageIndex = stages.indexOf(stage)
  
  const isComplete = currentIndex > stageIndex
  const isCurrent = current === stage
  
  return (
    <div className="flex flex-col items-center">
      <div 
        className={`w-2 h-2 rounded-full transition-all duration-300 ${
          isComplete ? 'bg-olive-500' :
          isCurrent ? 'bg-olive-500 animate-pulse ring-2 ring-olive-300' :
          'bg-cream-300 dark:bg-dark-50'
        }`}
      />
      <span className={`text-[10px] mt-0.5 transition-colors ${
        isComplete || isCurrent ? 'text-olive-600 dark:text-olive-400 font-medium' : 'text-surface-400'
      }`}>
        {label}
      </span>
    </div>
  )
}

function getStatusConfig(status: JobStage | string) {
  switch (status) {
    case 'completed':
      return {
        icon: CheckCircle2,
        stageIcon: CheckCircle2,
        bgColor: 'bg-olive-100 dark:bg-olive-900/30',
        iconColor: 'text-olive-600 dark:text-olive-400',
        pillClass: 'bg-olive-100 dark:bg-olive-900/30 text-olive-700 dark:text-olive-300',
        progressColor: 'bg-olive-500',
      }
    case 'failed':
      return {
        icon: XCircle,
        stageIcon: XCircle,
        bgColor: 'bg-red-100 dark:bg-red-900/30',
        iconColor: 'text-red-600 dark:text-red-400',
        pillClass: 'bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-300',
        progressColor: 'bg-red-500',
      }
    case 'extracting_audio':
      return {
        icon: Loader2,
        stageIcon: Volume2,
        bgColor: 'bg-blue-100 dark:bg-blue-900/30',
        iconColor: 'text-blue-600 dark:text-blue-400 animate-spin',
        pillClass: 'bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300',
        progressColor: 'bg-blue-500',
      }
    case 'transcribing':
      return {
        icon: Loader2,
        stageIcon: Mic,
        bgColor: 'bg-olive-100 dark:bg-olive-900/30',
        iconColor: 'text-olive-600 dark:text-olive-400 animate-spin',
        pillClass: 'bg-olive-100 dark:bg-olive-900/30 text-olive-700 dark:text-olive-300',
        progressColor: 'bg-olive-500',
      }
    case 'diarizing':
      return {
        icon: Loader2,
        stageIcon: Users,
        bgColor: 'bg-purple-100 dark:bg-purple-900/30',
        iconColor: 'text-purple-600 dark:text-purple-400 animate-spin',
        pillClass: 'bg-purple-100 dark:bg-purple-900/30 text-purple-700 dark:text-purple-300',
        progressColor: 'bg-purple-500',
      }
    case 'generating_tts':
      return {
        icon: Loader2,
        stageIcon: Volume2,
        bgColor: 'bg-amber-100 dark:bg-amber-900/30',
        iconColor: 'text-amber-600 dark:text-amber-400 animate-spin',
        pillClass: 'bg-amber-100 dark:bg-amber-900/30 text-amber-700 dark:text-amber-300',
        progressColor: 'bg-amber-500',
      }
    case 'syncing':
      return {
        icon: Loader2,
        stageIcon: Wand2,
        bgColor: 'bg-cyan-100 dark:bg-cyan-900/30',
        iconColor: 'text-cyan-600 dark:text-cyan-400 animate-spin',
        pillClass: 'bg-cyan-100 dark:bg-cyan-900/30 text-cyan-700 dark:text-cyan-300',
        progressColor: 'bg-cyan-500',
      }
    case 'queued':
    default:
      return {
        icon: Clock,
        stageIcon: Clock,
        bgColor: 'bg-cream-200 dark:bg-dark-50',
        iconColor: 'text-surface-500',
        pillClass: 'bg-cream-200 dark:bg-dark-50 text-surface-600',
        progressColor: 'bg-surface-400',
      }
  }
}
