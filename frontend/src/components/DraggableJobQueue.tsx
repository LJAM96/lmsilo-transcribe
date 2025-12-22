import { useState } from 'react'
import { Link } from 'react-router-dom'
import { formatDistanceToNow } from 'date-fns'
import { 
  DndContext, 
  closestCenter,
  KeyboardSensor,
  PointerSensor,
  useSensor,
  useSensors,
  DragEndEvent,
} from '@dnd-kit/core'
import {
  arrayMove,
  SortableContext,
  sortableKeyboardCoordinates,
  useSortable,
  verticalListSortingStrategy,
} from '@dnd-kit/sortable'
import { CSS } from '@dnd-kit/utilities'
import { 
  FileAudio, CheckCircle2, XCircle, Clock, Loader2, 
  GripVertical, Volume2, Mic, Users, Wand2 
} from 'lucide-react'
import { useProgressStore, formatStage, formatEta, type JobStage } from '../hooks/useWebSocket'
import toast from 'react-hot-toast'

interface Job {
  id: string
  filename: string
  status: string
  progress: number
  priority: number
  position: number
  created_at: string
}

interface DraggableJobQueueProps {
  jobs: Job[]
  onReorder?: (jobIds: string[]) => Promise<void>
}

export default function DraggableJobQueue({ jobs, onReorder }: DraggableJobQueueProps) {
  const [items, setItems] = useState(jobs.map(j => j.id))
  
  const sensors = useSensors(
    useSensor(PointerSensor, {
      activationConstraint: {
        distance: 8, // Require 8px drag before activating
      },
    }),
    useSensor(KeyboardSensor, {
      coordinateGetter: sortableKeyboardCoordinates,
    })
  )
  
  const handleDragEnd = async (event: DragEndEvent) => {
    const { active, over } = event
    
    if (over && active.id !== over.id) {
      const oldIndex = items.indexOf(active.id as string)
      const newIndex = items.indexOf(over.id as string)
      
      const newItems = arrayMove(items, oldIndex, newIndex)
      setItems(newItems)
      
      // Call API to persist reorder
      if (onReorder) {
        try {
          await onReorder(newItems)
          toast.success('Queue reordered')
        } catch (error) {
          // Revert on error
          setItems(items)
          toast.error('Failed to reorder queue')
        }
      }
    }
  }
  
  // Update items when jobs prop changes
  if (JSON.stringify(jobs.map(j => j.id)) !== JSON.stringify(items)) {
    setItems(jobs.map(j => j.id))
  }
  
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
    <DndContext
      sensors={sensors}
      collisionDetection={closestCenter}
      onDragEnd={handleDragEnd}
    >
      <SortableContext items={items} strategy={verticalListSortingStrategy}>
        <div className="space-y-2">
          {items.map((id, index) => {
            const job = jobs.find(j => j.id === id)
            if (!job) return null
            return (
              <SortableJobCard 
                key={id} 
                job={job} 
                position={index + 1}
                isDraggable={job.status === 'queued' || job.status === 'pending'}
              />
            )
          })}
        </div>
      </SortableContext>
    </DndContext>
  )
}

function SortableJobCard({ 
  job, 
  position,
  isDraggable 
}: { 
  job: Job
  position: number
  isDraggable: boolean
}) {
  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
    isDragging,
  } = useSortable({ 
    id: job.id,
    disabled: !isDraggable,
  })
  
  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    zIndex: isDragging ? 50 : undefined,
  }
  
  // Get real-time progress from WebSocket store
  const wsProgress = useProgressStore((s) => s.jobProgress[job.id])
  const currentStage = wsProgress?.stage || (job.status as JobStage)
  const currentProgress = wsProgress?.progress ?? job.progress
  const eta = wsProgress?.eta
  
  const statusConfig = getStatusConfig(currentStage)
  const isProcessing = !['completed', 'failed', 'queued', 'pending'].includes(currentStage)
  
  return (
    <div
      ref={setNodeRef}
      style={style}
      className={`relative ${isDragging ? 'opacity-90 shadow-xl' : ''}`}
    >
      <Link
        to={`/jobs/${job.id}`}
        className={`flex items-center gap-3 p-4 rounded-xl transition-all duration-200 group ${
          isDragging 
            ? 'bg-olive-50 dark:bg-olive-900/20 ring-2 ring-olive-400' 
            : 'bg-cream-50 dark:bg-dark-100 hover:bg-cream-100 dark:hover:bg-dark-50'
        }`}
      >
        {/* Drag handle */}
        {isDraggable && (
          <button
            {...attributes}
            {...listeners}
            className="p-1 -ml-1 cursor-grab active:cursor-grabbing hover:bg-cream-200 dark:hover:bg-dark-50 rounded-lg transition-colors"
            onClick={(e) => e.preventDefault()}
          >
            <GripVertical className="w-5 h-5 text-surface-400" />
          </button>
        )}
        
        {/* Status Icon */}
        <div className={`w-10 h-10 rounded-xl flex items-center justify-center flex-shrink-0 ${statusConfig.bgColor}`}>
          <statusConfig.icon className={`w-5 h-5 ${statusConfig.iconColor}`} />
        </div>
        
        {/* Job Info */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <p className="font-medium text-surface-800 dark:text-surface-200 truncate group-hover:text-olive-700 dark:group-hover:text-olive-400 transition-colors">
              {job.filename}
            </p>
            <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium ${statusConfig.pillClass}`}>
              <statusConfig.stageIcon className="w-3 h-3" />
              {formatStage(currentStage)}
            </span>
          </div>
          
          <div className="flex items-center gap-3 mt-1 text-sm text-surface-500">
            <span>#{position}</span>
            <span>•</span>
            <span>{formatDistanceToNow(new Date(job.created_at), { addSuffix: true })}</span>
            {eta && (
              <>
                <span>•</span>
                <span className="text-olive-600 dark:text-olive-400">{formatEta(eta)}</span>
              </>
            )}
          </div>
          
          {/* Progress bar */}
          {isProcessing && (
            <div className="mt-2">
              <div className="h-1.5 bg-cream-200 dark:bg-dark-50 rounded-full overflow-hidden">
                <div 
                  className={`h-full transition-all duration-300 ${statusConfig.progressColor}`}
                  style={{ width: `${currentProgress}%` }}
                />
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
      </Link>
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
    case 'pending':
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
