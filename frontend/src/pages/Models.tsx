import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Download, Trash2, Check, Loader2, Plus, AlertCircle } from 'lucide-react'
import toast from 'react-hot-toast'
import { api } from '../lib/api'
import { useState } from 'react'
import AddModelModal from '../components/AddModelModal'
import ConfirmModal from '../components/ConfirmModal'

export default function Models() {
  const queryClient = useQueryClient()
  const [showAddModal, setShowAddModal] = useState(false)
  const [deleteTarget, setDeleteTarget] = useState<{ id: string; name: string } | null>(null)
  
  const { data: models, isLoading } = useQuery({
    queryKey: ['models'],
    queryFn: () => api.getModels(),
    refetchInterval: (query) => {
      // Poll every second if any model is downloading
      const isDownloading = query.state.data?.some(
        (m) => m.download_progress !== null && m.download_progress !== undefined && m.download_progress < 100
      )
      return isDownloading ? 1000 : false
    },
  })
  
  const { data: systemEval } = useQuery({
    queryKey: ['system-eval'],
    queryFn: () => api.evaluateSystem({}),
  })
  
  const whisperModels = models?.filter(m => m.model_type === 'whisper') || []
  const diarizationModels = models?.filter(m => m.model_type === 'diarization') || []
  const ttsModels = models?.filter(m => m.model_type === 'tts') || []
  
  return (
    <div className="space-y-8 animate-fade-in">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-3xl font-serif text-surface-900">Model Management</h2>
          <p className="mt-2 text-surface-600">
            Configure STT, diarization, and TTS models
          </p>
        </div>
        <button 
          onClick={() => setShowAddModal(true)}
          className="btn-primary flex items-center gap-2"
        >
          <Plus className="w-4 h-4" />
          Add Model
        </button>
      </div>
      
      {/* System Info Card */}
      {systemEval && (
        <div className="card">
          <div className="flex items-start justify-between">
            <div>
              <h3 className="text-lg font-serif text-surface-800">System Capabilities</h3>
              <p className="text-sm text-surface-500 mt-1">{systemEval.hardware.summary}</p>
            </div>
            <div className="text-right">
              <div className="text-3xl font-bold text-olive-600">
                {systemEval.hardware.score}
              </div>
              <div className="text-xs text-surface-500">Hardware Score</div>
            </div>
          </div>
          
          <div className="mt-4 grid grid-cols-3 gap-4 text-sm">
            <div className="p-3 bg-cream-100 dark:bg-dark-100 rounded-xl border border-cream-200 dark:border-dark-50">
              <div className="text-xs font-medium text-surface-500 uppercase tracking-wide">GPU Memory</div>
              <div className="text-lg font-semibold text-olive-600 mt-1">
                {systemEval.hardware.gpu_memory_gb > 0 
                  ? `${systemEval.hardware.gpu_memory_gb.toFixed(0)} GB` 
                  : 'CPU Only'}
              </div>
            </div>
            <div className="p-3 bg-cream-100 dark:bg-dark-100 rounded-xl border border-cream-200 dark:border-dark-50">
              <div className="text-xs font-medium text-surface-500 uppercase tracking-wide">Compute Type</div>
              <div className="text-lg font-semibold text-olive-600 mt-1">
                {systemEval.hardware.recommended_compute_type}
              </div>
            </div>
            <div className="p-3 bg-cream-100 dark:bg-dark-100 rounded-xl border border-cream-200 dark:border-dark-50">
              <div className="text-xs font-medium text-surface-500 uppercase tracking-wide">Max Concurrent</div>
              <div className="text-lg font-semibold text-olive-600 mt-1">
                {systemEval.hardware.max_concurrent_jobs} jobs
              </div>
            </div>
          </div>
          
          {/* Warnings */}
          {systemEval.warnings.length > 0 && (
            <div className="mt-4 space-y-2">
              {systemEval.warnings.map((warning, i) => (
                <div key={i} className="flex items-start gap-2 text-sm text-amber-700 dark:text-amber-400 bg-amber-50 dark:bg-amber-900/20 p-3 rounded-xl border border-amber-200 dark:border-amber-800">
                  <AlertCircle className="w-4 h-4 flex-shrink-0 mt-0.5" />
                  <span>{warning}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
      
      {isLoading ? (
        <div className="flex items-center justify-center py-12">
          <Loader2 className="w-8 h-8 text-olive-600 animate-spin" />
        </div>
      ) : (
        <div className="space-y-8">
          {/* Whisper Models */}
          <ModelSection
            title="Speech-to-Text Models"
            description="Whisper and compatible models for transcription"
            models={whisperModels}
            compatibility={systemEval?.compatibility?.whisper}
            onDownload={(id) => downloadModel(id, queryClient)}
            onSetDefault={(id) => setDefaultModel(id, queryClient)}
            onDelete={(id, name) => setDeleteTarget({ id, name })}
          />
          
          {/* Diarization Models */}
          <ModelSection
            title="Diarization Models"
            description="Speaker identification models"
            models={diarizationModels}
            compatibility={systemEval?.compatibility?.diarization}
            onDownload={(id) => downloadModel(id, queryClient)}
            onSetDefault={(id) => setDefaultModel(id, queryClient)}
            onDelete={(id, name) => setDeleteTarget({ id, name })}
          />
          
          {/* TTS Models */}
          <ModelSection
            title="Text-to-Speech Models"
            description="Voice synthesis engines"
            models={ttsModels}
            compatibility={systemEval?.compatibility?.tts}
            onDownload={(id) => downloadModel(id, queryClient)}
            onSetDefault={(id) => setDefaultModel(id, queryClient)}
            onDelete={(id, name) => setDeleteTarget({ id, name })}
          />
        </div>
      )}
      
      {/* Add Model Modal */}
      <AddModelModal 
        isOpen={showAddModal} 
        onClose={() => setShowAddModal(false)} 
      />
      
      {/* Delete Confirmation Modal */}
      <ConfirmModal
        isOpen={deleteTarget !== null}
        onClose={() => setDeleteTarget(null)}
        onConfirm={async () => {
          if (deleteTarget) {
            await deleteModel(deleteTarget.id, queryClient)
          }
        }}
        title="Delete Model"
        message={`Are you sure you want to delete "${deleteTarget?.name}"? This action cannot be undone.`}
        confirmText="Delete"
        variant="danger"
      />
    </div>
  )
}

interface Model {
  id: string
  name: string
  model_type: string
  engine: string
  is_default: boolean
  is_downloaded: boolean
  download_progress?: number
  info: {
    size_mb?: number
    description?: string
    recommended_vram_gb?: number
  }
}

interface ModelSectionProps {
  title: string
  description: string
  models: Model[]
  compatibility?: Record<string, boolean>
  onDownload: (id: string) => void
  onSetDefault: (id: string) => void
  onDelete: (id: string, name: string) => void
}

function ModelSection({ title, description, models, compatibility, onDownload, onSetDefault, onDelete }: ModelSectionProps) {
  if (models.length === 0) {
    return (
      <div className="card">
        <h3 className="text-lg font-serif text-surface-800">{title}</h3>
        <p className="text-sm text-surface-500 mt-1">{description}</p>
        <div className="mt-4 text-center py-8 text-surface-400">
          No models registered. Click "Add Model" to get started.
        </div>
      </div>
    )
  }
  
  return (
    <div className="card">
      <h3 className="text-lg font-serif text-surface-800">{title}</h3>
      <p className="text-sm text-surface-500 mt-1">{description}</p>
      
      <div className="mt-4 space-y-3">
        {models.map((model) => {
          const canRun = compatibility ? compatibility[model.info?.recommended_vram_gb ? 'large-v3' : 'base'] !== false : true
          
          return (
            <div 
              key={model.id}
              className={`p-4 rounded-xl border ${
                model.is_default 
                  ? 'bg-olive-50 border-olive-200' 
                  : 'bg-cream-50 border-cream-200'
              }`}
            >
              <div className="flex items-start gap-4">
                <div className="flex-1">
                  <div className="flex items-center gap-2">
                    <span className="font-medium text-surface-800">{model.name}</span>
                    <span className="text-xs text-surface-500 bg-cream-200 px-2 py-0.5 rounded">
                      {model.engine}
                    </span>
                    {model.is_default && (
                      <span className="badge badge-success">Default</span>
                    )}
                    {!canRun && (
                      <span className="badge badge-warning">May be slow</span>
                    )}
                  </div>
                  
                  {model.info?.description && (
                    <p className="text-sm text-surface-600 mt-1">{model.info.description}</p>
                  )}
                  
                  <div className="flex items-center gap-4 mt-2 text-xs text-surface-500">
                    {model.info?.size_mb && (
                      <span>{(model.info.size_mb / 1024).toFixed(1)} GB</span>
                    )}
                    {model.info?.recommended_vram_gb && (
                      <span>Needs {model.info.recommended_vram_gb} GB VRAM</span>
                    )}
                  </div>
                  
                  {/* Download progress */}
                  {model.download_progress !== null && model.download_progress !== undefined && model.download_progress < 100 && (
                    <div className="mt-2">
                      <div className="progress">
                        <div 
                          className="progress-bar" 
                          style={{ width: `${model.download_progress}%` }}
                        />
                      </div>
                    </div>
                  )}
                </div>
                
                <div className="flex items-center gap-2">
                  {!model.is_downloaded ? (
                    <button
                      onClick={() => onDownload(model.id)}
                      className="p-2 hover:bg-cream-200 rounded-lg transition-colors"
                      title="Download model"
                    >
                      <Download className="w-4 h-4 text-olive-600" />
                    </button>
                  ) : !model.is_default ? (
                    <button
                      onClick={() => onSetDefault(model.id)}
                      className="p-2 hover:bg-cream-200 rounded-lg transition-colors"
                      title="Set as default"
                    >
                      <Check className="w-4 h-4 text-surface-600" />
                    </button>
                  ) : null}
                  
                  <button
                    onClick={() => onDelete(model.id, model.name)}
                    className="p-2 hover:bg-red-100 rounded-lg transition-colors"
                    title="Delete model"
                  >
                    <Trash2 className="w-4 h-4 text-red-500" />
                  </button>
                </div>
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}

async function downloadModel(id: string, queryClient: any) {
  try {
    await api.downloadModel(id)
    toast.success('Download started')
    queryClient.invalidateQueries(['models'])
  } catch (e) {
    toast.error('Failed to start download')
  }
}

async function setDefaultModel(id: string, queryClient: any) {
  try {
    await api.setDefaultModel(id)
    toast.success('Default model updated')
    queryClient.invalidateQueries(['models'])
  } catch (e) {
    toast.error('Failed to update default')
  }
}

async function deleteModel(id: string, queryClient: any) {
  try {
    await api.deleteModel(id)
    toast.success('Model deleted')
    queryClient.invalidateQueries(['models'])
  } catch (e) {
    toast.error('Failed to delete model')
  }
}
