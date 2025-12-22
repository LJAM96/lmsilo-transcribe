import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { 
  Folder, 
  ChevronDown, 
  ChevronRight, 
  CheckCircle, 
  Clock, 
  XCircle,
  Loader2,
  Download,
} from 'lucide-react'

interface BatchJob {
  id: string
  filename: string
  status: string
  progress: number
  current_stage?: string
  error_message?: string
}

interface Batch {
  id: string
  name: string
  total_files: number
  completed_files: number
  failed_files: number
  status: string
  progress: number
  created_at: string
  jobs?: BatchJob[]
}

export default function BatchQueue() {
  const navigate = useNavigate()
  const [expandedBatches, setExpandedBatches] = useState<Set<string>>(new Set())

  const { data: batchesData } = useQuery({
    queryKey: ['batches'],
    queryFn: async () => {
      const response = await fetch('/api/batches')
      return response.json()
    },
    refetchInterval: 2000,
  })

  const toggleExpand = (batchId: string) => {
    const newExpanded = new Set(expandedBatches)
    if (newExpanded.has(batchId)) {
      newExpanded.delete(batchId)
    } else {
      newExpanded.add(batchId)
    }
    setExpandedBatches(newExpanded)
  }

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'completed':
        return <CheckCircle className="w-4 h-4 text-green-500" />
      case 'failed':
        return <XCircle className="w-4 h-4 text-red-500" />
      case 'processing':
        return <Loader2 className="w-4 h-4 text-olive-500 animate-spin" />
      default:
        return <Clock className="w-4 h-4 text-surface-400" />
    }
  }

  const batches: Batch[] = batchesData?.batches || []

  if (batches.length === 0) {
    return null
  }

  return (
    <div className="space-y-2">
      <h3 className="text-sm font-medium text-surface-500 dark:text-surface-400 uppercase tracking-wide">
        Batch Jobs
      </h3>
      
      {batches.map((batch) => (
        <div key={batch.id} className="card overflow-hidden">
          {/* Batch Header */}
          <div
            onClick={() => toggleExpand(batch.id)}
            className="flex items-center gap-3 p-4 cursor-pointer hover:bg-cream-50 dark:hover:bg-dark-100 transition-colors"
          >
            <button className="p-1">
              {expandedBatches.has(batch.id) ? (
                <ChevronDown className="w-4 h-4 text-surface-400" />
              ) : (
                <ChevronRight className="w-4 h-4 text-surface-400" />
              )}
            </button>
            
            <Folder className="w-5 h-5 text-olive-500" />
            
            <div className="flex-1 min-w-0">
              <div className="font-medium text-surface-800 dark:text-surface-200 truncate">
                {batch.name}
              </div>
              <div className="text-sm text-surface-500">
                {batch.completed_files}/{batch.total_files} completed
                {batch.failed_files > 0 && (
                  <span className="text-red-500 ml-2">
                    ({batch.failed_files} failed)
                  </span>
                )}
              </div>
            </div>
            
            <div className="flex items-center gap-3">
              {/* Progress bar */}
              <div className="w-24 h-2 bg-surface-200 dark:bg-dark-50 rounded-full overflow-hidden">
                <div
                  className={`h-full transition-all duration-300 ${
                    batch.status === 'completed'
                      ? 'bg-green-500'
                      : batch.status === 'failed'
                      ? 'bg-red-500'
                      : 'bg-olive-500'
                  }`}
                  style={{ width: `${batch.progress}%` }}
                />
              </div>
              
              <span className="text-sm text-surface-500 w-12 text-right">
                {Math.round(batch.progress)}%
              </span>
              
              {getStatusIcon(batch.status)}
            </div>
          </div>
          
          {/* Expanded Job List */}
          {expandedBatches.has(batch.id) && (
            <BatchJobList 
              batchId={batch.id} 
              onJobClick={(jobId) => navigate(`/jobs/${jobId}`)}
            />
          )}
        </div>
      ))}
    </div>
  )
}

interface BatchJobListProps {
  batchId: string
  onJobClick: (jobId: string) => void
}

function BatchJobList({ batchId, onJobClick }: BatchJobListProps) {
  const { data: batchData } = useQuery({
    queryKey: ['batch', batchId],
    queryFn: async () => {
      const response = await fetch(`/api/batches/${batchId}`)
      return response.json()
    },
    refetchInterval: 2000,
  })

  const jobs: BatchJob[] = batchData?.jobs || []

  const getJobStatusIcon = (status: string) => {
    switch (status) {
      case 'completed':
        return <CheckCircle className="w-3 h-3 text-green-500" />
      case 'failed':
        return <XCircle className="w-3 h-3 text-red-500" />
      case 'processing':
      case 'transcribing':
        return <Loader2 className="w-3 h-3 text-olive-500 animate-spin" />
      default:
        return <Clock className="w-3 h-3 text-surface-400" />
    }
  }

  const handleExport = async () => {
    const response = await fetch(`/api/batches/${batchId}/export?format=txt`)
    const blob = await response.blob()
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `${batchData?.name || 'batch'}.zip`
    a.click()
    URL.revokeObjectURL(url)
  }

  return (
    <div className="border-t border-surface-100 dark:border-dark-100">
      <div className="max-h-64 overflow-y-auto">
        {jobs.map((job) => (
          <div
            key={job.id}
            onClick={() => onJobClick(job.id)}
            className="flex items-center gap-3 px-4 py-2 pl-12 hover:bg-cream-50 dark:hover:bg-dark-100 cursor-pointer transition-colors text-sm"
          >
            {getJobStatusIcon(job.status)}
            <span className="flex-1 truncate text-surface-700 dark:text-surface-300">
              {job.filename}
            </span>
            {job.current_stage && job.status !== 'completed' && job.status !== 'failed' && (
              <span className="text-xs text-surface-400">{job.current_stage}</span>
            )}
            {job.status === 'failed' && job.error_message && (
              <span className="text-xs text-red-500 truncate max-w-32">
                {job.error_message}
              </span>
            )}
          </div>
        ))}
      </div>
      
      {/* Export button */}
      {batchData?.status === 'completed' && (
        <div className="border-t border-surface-100 dark:border-dark-100 p-3 pl-12">
          <button
            onClick={handleExport}
            className="flex items-center gap-2 text-sm text-olive-600 hover:text-olive-700"
          >
            <Download className="w-4 h-4" />
            Export All Transcripts
          </button>
        </div>
      )}
    </div>
  )
}
