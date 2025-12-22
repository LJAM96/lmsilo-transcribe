import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import FileUpload from '../components/FileUpload'
import DraggableJobQueue from '../components/DraggableJobQueue'
import BatchQueue from '../components/BatchQueue'
import TranscriptionSettings from '../components/TranscriptionSettings'
import { api } from '../lib/api'
import { useWebSocket } from '../hooks/useWebSocket'

export interface TranscriptionOptions {
  language: string
  modelId: string | null
  diarizationModelId: string | null
  ttsModelId: string | null
  enableDiarization: boolean
  enableTts: boolean
  syncTtsTiming: boolean
  outputFormats: string[]
  priority: number
}

const defaultOptions: TranscriptionOptions = {
  language: 'auto',
  modelId: null,
  diarizationModelId: null,
  ttsModelId: null,
  enableDiarization: false,
  enableTts: false,
  syncTtsTiming: true,
  outputFormats: ['json', 'srt'],
  priority: 5,
}

export default function Dashboard() {
  const [options, setOptions] = useState<TranscriptionOptions>(defaultOptions)
  
  // Connect to WebSocket for real-time job updates
  useWebSocket()
  
  // Fetch queue status
  const { data: queueData, refetch: refetchQueue } = useQuery({
    queryKey: ['queue'],
    queryFn: api.getQueue,
    refetchInterval: 5000, // Slower interval since WebSocket provides real-time updates
  })
  
  // Fetch available models
  const { data: models } = useQuery({
    queryKey: ['models'],
    queryFn: () => api.getModels(),
  })
  
  const handleUploadComplete = () => {
    refetchQueue()
  }
  
  return (
    <div className="space-y-8 animate-fade-in">
      {/* Page Header */}
      <div>
        <h2 className="text-3xl font-serif text-surface-900">
          Transcription Dashboard
        </h2>
        <p className="mt-2 text-surface-600">
          Upload audio or video files for transcription with optional speaker diarization and TTS synthesis.
        </p>
      </div>
      
      {/* Main Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* Left Column - Upload and Queue */}
        <div className="lg:col-span-2 space-y-6">
          {/* Upload Card */}
          <div className="card">
            <h3 className="text-lg font-serif text-surface-800 mb-4">Upload Media</h3>
            <FileUpload 
              options={options} 
              onUploadComplete={handleUploadComplete}
            />
          </div>
          
          {/* Batch Jobs */}
          <BatchQueue />
          
          {/* Queue Card */}
          <div className="card">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-serif text-surface-800">Processing Queue</h3>
              {queueData && (
                <div className="flex gap-4 text-sm">
                  <span className="text-surface-500">
                    <strong className="text-olive-600">{queueData.total_processing}</strong> processing
                  </span>
                  <span className="text-surface-500">
                    <strong className="text-surface-700">{queueData.total_pending}</strong> pending
                  </span>
                </div>
              )}
            </div>
            <DraggableJobQueue 
              jobs={queueData?.queue || []} 
              onReorder={async (jobIds) => {
                await api.reorderQueue(jobIds)
                refetchQueue()
              }}
            />
          </div>
        </div>
        
        {/* Right Column - Settings */}
        <div className="space-y-6">
          <div className="card sticky top-24">
            <h3 className="text-lg font-serif text-surface-800 mb-4">
              Transcription Settings
            </h3>
            <TranscriptionSettings
              options={options}
              onChange={setOptions}
              models={models || []}
            />
          </div>
        </div>
      </div>
    </div>
  )
}
