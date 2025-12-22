import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { Search, CheckCircle, XCircle, Clock, ChevronRight } from 'lucide-react'

interface HistoryJob {
  id: string
  filename: string
  status: string
  language: string
  detected_language?: string
  duration?: number
  created_at: string
  completed_at?: string
  has_transcript: boolean
  has_tts: boolean
  error_message?: string
}

interface HistoryResponse {
  total: number
  offset: number
  limit: number
  jobs: HistoryJob[]
}

export default function History() {
  const navigate = useNavigate()
  const [searchQuery, setSearchQuery] = useState('')
  const [statusFilter, setStatusFilter] = useState<string>('')
  const [page, setPage] = useState(0)
  const limit = 20

  const { data: history, isLoading } = useQuery<HistoryResponse>({
    queryKey: ['history', searchQuery, statusFilter, page],
    queryFn: async () => {
      const params = new URLSearchParams()
      if (searchQuery) params.set('q', searchQuery)
      if (statusFilter) params.set('status', statusFilter)
      params.set('limit', String(limit))
      params.set('offset', String(page * limit))
      
      const response = await fetch(`/api/history?${params}`)
      return response.json()
    },
  })

  const { data: stats } = useQuery({
    queryKey: ['history-stats'],
    queryFn: async () => {
      const response = await fetch('/api/history/stats')
      return response.json()
    },
  })

  const formatDuration = (seconds?: number) => {
    if (!seconds) return '-'
    const mins = Math.floor(seconds / 60)
    const secs = Math.floor(seconds % 60)
    return `${mins}:${secs.toString().padStart(2, '0')}`
  }

  const formatDate = (date: string) => {
    return new Date(date).toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    })
  }

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'completed':
        return <CheckCircle className="w-4 h-4 text-green-500" />
      case 'failed':
        return <XCircle className="w-4 h-4 text-red-500" />
      case 'cancelled':
        return <XCircle className="w-4 h-4 text-surface-400" />
      default:
        return <Clock className="w-4 h-4 text-surface-400" />
    }
  }

  return (
    <div className="space-y-6 animate-fade-in">
      <div>
        <h2 className="text-3xl font-serif text-surface-900 dark:text-surface-100">History</h2>
        <p className="mt-2 text-surface-600 dark:text-surface-400">
          Browse and search past transcriptions
        </p>
      </div>

      {/* Stats Cards */}
      {stats && (
        <div className="space-y-4">
          <div className="grid grid-cols-4 gap-4">
            <div className="card p-4">
              <div className="text-2xl font-bold text-olive-600">{stats.total_completed}</div>
              <div className="text-sm text-surface-500">Completed</div>
            </div>
            <div className="card p-4">
              <div className="text-2xl font-bold text-red-500">{stats.total_failed}</div>
              <div className="text-sm text-surface-500">Failed</div>
            </div>
            <div className="card p-4">
              <div className="text-2xl font-bold text-surface-700 dark:text-surface-300">
                {stats.total_duration_hours}h
              </div>
              <div className="text-sm text-surface-500">Audio Processed</div>
            </div>
            <div className="card p-4">
              <div className="text-2xl font-bold text-surface-700 dark:text-surface-300">
                {stats.avg_processing_seconds}s
              </div>
              <div className="text-sm text-surface-500">Avg Processing</div>
            </div>
          </div>
          
          {/* Language Chart */}
          {stats.top_languages && stats.top_languages.length > 0 && (
            <div className="card p-4">
              <h4 className="text-sm font-medium text-surface-600 dark:text-surface-400 mb-3">
                Top Languages
              </h4>
              <div className="flex items-center gap-4">
                {/* Simple bar chart */}
                <div className="flex-1 space-y-2">
                  {stats.top_languages.slice(0, 5).map((lang: { language: string; count: number }, i: number) => {
                    const maxCount = stats.top_languages[0].count
                    const percentage = (lang.count / maxCount) * 100
                    return (
                      <div key={lang.language} className="flex items-center gap-2">
                        <span className="w-20 text-sm text-surface-600 dark:text-surface-400 truncate">
                          {lang.language || 'Unknown'}
                        </span>
                        <div className="flex-1 h-4 bg-cream-100 dark:bg-dark-50 rounded-full overflow-hidden">
                          <div
                            className="h-full rounded-full"
                            style={{
                              width: `${percentage}%`,
                              backgroundColor: `hsl(${(i * 60) % 360 + 80}, 50%, 50%)`,
                            }}
                          />
                        </div>
                        <span className="w-8 text-sm text-surface-500 text-right">
                          {lang.count}
                        </span>
                      </div>
                    )
                  })}
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Filters */}
      <div className="card">
        <div className="flex gap-4">
          <div className="flex-1 relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-surface-400" />
            <input
              type="text"
              placeholder="Search by filename..."
              value={searchQuery}
              onChange={(e) => {
                setSearchQuery(e.target.value)
                setPage(0)
              }}
              className="w-full pl-10 pr-4 py-2 rounded-xl bg-cream-50 dark:bg-dark-100 border border-surface-200 dark:border-dark-50 focus:outline-none focus:ring-2 focus:ring-olive-300"
            />
          </div>
          <select
            value={statusFilter}
            onChange={(e) => {
              setStatusFilter(e.target.value)
              setPage(0)
            }}
            className="px-4 py-2 rounded-xl bg-cream-50 dark:bg-dark-100 border border-surface-200 dark:border-dark-50"
          >
            <option value="">All Statuses</option>
            <option value="completed">Completed</option>
            <option value="failed">Failed</option>
            <option value="cancelled">Cancelled</option>
          </select>
        </div>
      </div>

      {/* Job List */}
      <div className="card divide-y divide-surface-100 dark:divide-dark-100">
        {isLoading ? (
          <div className="p-8 text-center text-surface-500">Loading...</div>
        ) : history?.jobs.length === 0 ? (
          <div className="p-8 text-center text-surface-500">
            No jobs found matching your criteria
          </div>
        ) : (
          history?.jobs.map((job) => (
            <div
              key={job.id}
              onClick={() => navigate(`/jobs/${job.id}`)}
              className="flex items-center gap-4 p-4 hover:bg-cream-50 dark:hover:bg-dark-100 cursor-pointer transition-colors"
            >
              {getStatusIcon(job.status)}
              <div className="flex-1 min-w-0">
                <div className="font-medium text-surface-800 dark:text-surface-200 truncate">
                  {job.filename}
                </div>
                <div className="text-sm text-surface-500">
                  {job.detected_language || job.language} • {formatDuration(job.duration)}
                </div>
              </div>
              <div className="text-sm text-surface-400">
                {job.completed_at ? formatDate(job.completed_at) : formatDate(job.created_at)}
              </div>
              <ChevronRight className="w-4 h-4 text-surface-400" />
            </div>
          ))
        )}
      </div>

      {/* Pagination */}
      {history && history.total > limit && (
        <div className="flex justify-center gap-2">
          <button
            onClick={() => setPage((p) => Math.max(0, p - 1))}
            disabled={page === 0}
            className="px-4 py-2 rounded-lg bg-surface-100 dark:bg-dark-100 disabled:opacity-50"
          >
            Previous
          </button>
          <span className="px-4 py-2 text-surface-600">
            Page {page + 1} of {Math.ceil(history.total / limit)}
          </span>
          <button
            onClick={() => setPage((p) => p + 1)}
            disabled={(page + 1) * limit >= history.total}
            className="px-4 py-2 rounded-lg bg-surface-100 dark:bg-dark-100 disabled:opacity-50"
          >
            Next
          </button>
        </div>
      )}
    </div>
  )
}
