import { useState, useEffect, useCallback } from 'react'
import { X, Search, Download, Loader2, ExternalLink, Cpu, Mic, Users, Volume2, Star, AlertCircle } from 'lucide-react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import toast from 'react-hot-toast'
import { api } from '../lib/api'

interface AddModelModalProps {
  isOpen: boolean
  onClose: () => void
}

type ModelType = 'whisper' | 'diarization' | 'tts'

interface BuiltinModel {
  id: string
  name: string
  engine: string
  model_type: ModelType
  description: string
  size_mb?: number
  recommended_vram_gb?: number
  hf_id?: string
  popular?: boolean
}

interface HFModel {
  id: string
  modelId: string
  author: string
  downloads: number
  likes: number
  tags: string[]
  pipeline_tag?: string
}

// Expanded list of supported models
const BUILTIN_MODELS: BuiltinModel[] = [
  // ===== WHISPER STT MODELS =====
  // OpenAI Whisper (faster-whisper)
  { id: 'whisper-tiny', name: 'Whisper Tiny', engine: 'faster-whisper', model_type: 'whisper', description: 'Fastest, ~39M params, best for quick tests', size_mb: 75, recommended_vram_gb: 1, hf_id: 'Systran/faster-whisper-tiny', popular: true },
  { id: 'whisper-tiny.en', name: 'Whisper Tiny (English)', engine: 'faster-whisper', model_type: 'whisper', description: 'English-only, slightly better accuracy', size_mb: 75, recommended_vram_gb: 1, hf_id: 'Systran/faster-whisper-tiny.en' },
  { id: 'whisper-base', name: 'Whisper Base', engine: 'faster-whisper', model_type: 'whisper', description: 'Fast with good accuracy, ~74M params', size_mb: 145, recommended_vram_gb: 1, hf_id: 'Systran/faster-whisper-base', popular: true },
  { id: 'whisper-base.en', name: 'Whisper Base (English)', engine: 'faster-whisper', model_type: 'whisper', description: 'English-only base model', size_mb: 145, recommended_vram_gb: 1, hf_id: 'Systran/faster-whisper-base.en' },
  { id: 'whisper-small', name: 'Whisper Small', engine: 'faster-whisper', model_type: 'whisper', description: 'Balanced speed/accuracy, ~244M params', size_mb: 466, recommended_vram_gb: 2, hf_id: 'Systran/faster-whisper-small', popular: true },
  { id: 'whisper-small.en', name: 'Whisper Small (English)', engine: 'faster-whisper', model_type: 'whisper', description: 'English-only small model', size_mb: 466, recommended_vram_gb: 2, hf_id: 'Systran/faster-whisper-small.en' },
  { id: 'whisper-medium', name: 'Whisper Medium', engine: 'faster-whisper', model_type: 'whisper', description: 'High accuracy, ~769M params', size_mb: 1500, recommended_vram_gb: 5, hf_id: 'Systran/faster-whisper-medium', popular: true },
  { id: 'whisper-medium.en', name: 'Whisper Medium (English)', engine: 'faster-whisper', model_type: 'whisper', description: 'English-only medium model', size_mb: 1500, recommended_vram_gb: 5, hf_id: 'Systran/faster-whisper-medium.en' },
  { id: 'whisper-large-v2', name: 'Whisper Large v2', engine: 'faster-whisper', model_type: 'whisper', description: 'Very high accuracy, ~1.5B params', size_mb: 3000, recommended_vram_gb: 10, hf_id: 'Systran/faster-whisper-large-v2' },
  { id: 'whisper-large-v3', name: 'Whisper Large v3', engine: 'faster-whisper', model_type: 'whisper', description: 'Best accuracy, latest version', size_mb: 3000, recommended_vram_gb: 10, hf_id: 'Systran/faster-whisper-large-v3', popular: true },
  { id: 'whisper-large-v3-turbo', name: 'Whisper Large v3 Turbo', engine: 'faster-whisper', model_type: 'whisper', description: 'Faster large v3, optimized for speed', size_mb: 1600, recommended_vram_gb: 6, hf_id: 'deepdml/faster-whisper-large-v3-turbo-ct2', popular: true },
  
  // Distil-Whisper (distil-whisper)
  { id: 'distil-whisper-large-v2', name: 'Distil-Whisper Large v2', engine: 'faster-whisper', model_type: 'whisper', description: '6x faster than large-v2, similar quality', size_mb: 756, recommended_vram_gb: 3, hf_id: 'distil-whisper/distil-large-v2', popular: true },
  { id: 'distil-whisper-large-v3', name: 'Distil-Whisper Large v3', engine: 'faster-whisper', model_type: 'whisper', description: 'Distilled from large-v3, excellent speed', size_mb: 756, recommended_vram_gb: 3, hf_id: 'distil-whisper/distil-large-v3', popular: true },
  { id: 'distil-whisper-medium.en', name: 'Distil-Whisper Medium EN', engine: 'faster-whisper', model_type: 'whisper', description: 'Fast English-only distilled model', size_mb: 394, recommended_vram_gb: 2, hf_id: 'distil-whisper/distil-medium.en' },
  { id: 'distil-whisper-small.en', name: 'Distil-Whisper Small EN', engine: 'faster-whisper', model_type: 'whisper', description: 'Fastest distilled English model', size_mb: 166, recommended_vram_gb: 1, hf_id: 'distil-whisper/distil-small.en' },

  // ===== DIARIZATION MODELS =====
  { id: 'pyannote-3.1', name: 'Pyannote 3.1', engine: 'pyannote', model_type: 'diarization', description: 'State-of-the-art speaker diarization', size_mb: 200, recommended_vram_gb: 2, hf_id: 'pyannote/speaker-diarization-3.1', popular: true },
  { id: 'pyannote-3.0', name: 'Pyannote 3.0', engine: 'pyannote', model_type: 'diarization', description: 'Previous stable version', size_mb: 200, recommended_vram_gb: 2, hf_id: 'pyannote/speaker-diarization-3.0' },
  { id: 'pyannote-segmentation-3.0', name: 'Pyannote Segmentation', engine: 'pyannote', model_type: 'diarization', description: 'Speaker segmentation only', size_mb: 100, recommended_vram_gb: 1, hf_id: 'pyannote/segmentation-3.0' },
  { id: 'wespeaker-voxceleb', name: 'WeSpeaker VoxCeleb', engine: 'wespeaker', model_type: 'diarization', description: 'Speaker verification embeddings', size_mb: 150, recommended_vram_gb: 1, hf_id: 'pyannote/wespeaker-vox-celebrity-resnet34-LM' },

  // ===== TTS MODELS =====
  { id: 'xtts-v2', name: 'XTTS v2', engine: 'coqui-tts', model_type: 'tts', description: 'Multi-lingual voice cloning, 17 languages', size_mb: 1800, recommended_vram_gb: 4, hf_id: 'coqui/XTTS-v2', popular: true },
  { id: 'xtts-v1.1', name: 'XTTS v1.1', engine: 'coqui-tts', model_type: 'tts', description: 'Previous XTTS version', size_mb: 1600, recommended_vram_gb: 4, hf_id: 'coqui/XTTS-v1.1' },
  { id: 'speecht5-tts', name: 'SpeechT5', engine: 'speecht5', model_type: 'tts', description: 'Microsoft speech synthesis', size_mb: 300, recommended_vram_gb: 2, hf_id: 'microsoft/speecht5_tts', popular: true },
  { id: 'bark', name: 'Bark', engine: 'bark', model_type: 'tts', description: 'Highly realistic, supports music/effects', size_mb: 5000, recommended_vram_gb: 8, hf_id: 'suno/bark', popular: true },
  { id: 'bark-small', name: 'Bark Small', engine: 'bark', model_type: 'tts', description: 'Smaller Bark model, faster generation', size_mb: 900, recommended_vram_gb: 4, hf_id: 'suno/bark-small' },
  { id: 'mms-tts', name: 'MMS TTS', engine: 'mms', model_type: 'tts', description: 'Meta MMS, 1100+ languages', size_mb: 200, recommended_vram_gb: 1, hf_id: 'facebook/mms-tts', popular: true },
  { id: 'parler-tts-mini', name: 'Parler TTS Mini', engine: 'parler', model_type: 'tts', description: 'Controllable TTS with text descriptions', size_mb: 600, recommended_vram_gb: 3, hf_id: 'parler-tts/parler-tts-mini-v1' },
  { id: 'parler-tts-large', name: 'Parler TTS Large', engine: 'parler', model_type: 'tts', description: 'Larger Parler model, better quality', size_mb: 2000, recommended_vram_gb: 6, hf_id: 'parler-tts/parler-tts-large-v1' },
  { id: 'tortoise-tts', name: 'Tortoise TTS', engine: 'tortoise', model_type: 'tts', description: 'High quality, slow generation', size_mb: 1000, recommended_vram_gb: 6, hf_id: 'neonbjb/tortoise-tts' },
  { id: 'vits', name: 'VITS', engine: 'vits', model_type: 'tts', description: 'Fast end-to-end TTS', size_mb: 150, recommended_vram_gb: 1, hf_id: 'facebook/mms-tts-eng' },
]

// Supported HuggingFace model patterns (what we can actually use)
const SUPPORTED_HF_PATTERNS = {
  whisper: [
    'openai/whisper',
    'distil-whisper',
    'Systran/faster-whisper',
    'guillaumekln/faster-whisper',
  ],
  diarization: [
    'pyannote/speaker-diarization',
    'pyannote/segmentation',
    'pyannote/wespeaker',
  ],
  tts: [
    'coqui/XTTS',
    'microsoft/speecht5',
    'suno/bark',
    'facebook/mms-tts',
    'parler-tts',
    'neonbjb/tortoise',
  ],
}

export default function AddModelModal({ isOpen, onClose }: AddModelModalProps) {
  const [activeTab, setActiveTab] = useState<'popular' | 'huggingface' | 'local'>('popular')
  const [searchQuery, setSearchQuery] = useState('')
  const [selectedType, setSelectedType] = useState<ModelType | 'all'>('all')
  const [downloading, setDownloading] = useState<string | null>(null)
  
  // HuggingFace search state
  const [hfSearchQuery, setHfSearchQuery] = useState('')
  const [hfResults, setHfResults] = useState<HFModel[]>([])
  const [hfLoading, setHfLoading] = useState(false)
  const [hfSearchType, setHfSearchType] = useState<ModelType>('whisper')
  
  const queryClient = useQueryClient()
  
  const registerMutation = useMutation({
    mutationFn: async (model: BuiltinModel) => {
      // Map frontend engine names to backend enum values
      const engineMap: Record<string, string> = {
        'faster-whisper': 'faster-whisper',
        'pyannote': 'pyannote',
        'coqui-tts': 'coqui-xtts',
        'speecht5': 'coqui-xtts', // Map to coqui for now
        'bark': 'bark',
        'parler': 'bark', // Map to bark for now
        'mms': 'coqui-vits',
        'tortoise': 'tortoise',
        'vits': 'coqui-vits',
        'wespeaker': 'pyannote',
      }
      
      const backendEngine = engineMap[model.engine] || model.engine
      
      return api.registerModel({
        name: model.name,
        model_type: model.model_type,
        engine: backendEngine,
        source: 'huggingface',
        model_id: model.hf_id || model.id, // Backend expects model_id, not source_path
        info: {
          description: model.description,
          size_mb: model.size_mb,
          recommended_vram_gb: model.recommended_vram_gb,
        },
      })
    },
    onSuccess: (_, model) => {
      toast.success(`${model.name} added`)
      queryClient.invalidateQueries({ queryKey: ['models'] })
    },
    onError: (error) => {
      toast.error(`Failed to add model: ${error}`)
    },
  })
  
  const handleAddModel = async (model: BuiltinModel) => {
    setDownloading(model.id)
    try {
      await registerMutation.mutateAsync(model)
    } finally {
      setDownloading(null)
    }
  }
  
  // HuggingFace search function
  const searchHuggingFace = useCallback(async () => {
    if (!hfSearchQuery.trim()) {
      setHfResults([])
      return
    }
    
    setHfLoading(true)
    try {
      // Build search query based on type
      let searchTerms = hfSearchQuery
      const typeFilters = SUPPORTED_HF_PATTERNS[hfSearchType]
      
      // Use HuggingFace API
      const response = await fetch(
        `https://huggingface.co/api/models?search=${encodeURIComponent(searchTerms)}&limit=20&sort=downloads&direction=-1`
      )
      
      if (!response.ok) throw new Error('Search failed')
      
      const models: HFModel[] = await response.json()
      
      // Filter to only supported models
      const filteredModels = models.filter(model => {
        const modelId = model.modelId || model.id
        return typeFilters.some(pattern => modelId.toLowerCase().includes(pattern.toLowerCase()))
      })
      
      setHfResults(filteredModels)
    } catch (error) {
      console.error('HuggingFace search error:', error)
      toast.error('Failed to search HuggingFace')
      setHfResults([])
    } finally {
      setHfLoading(false)
    }
  }, [hfSearchQuery, hfSearchType])
  
  // Add HuggingFace model
  const handleAddHFModel = async (hfModel: HFModel) => {
    const modelId = hfModel.modelId || hfModel.id
    const engine = getEngineForType(hfSearchType)
    
    const model: BuiltinModel = {
      id: modelId.replace('/', '-'),
      name: modelId.split('/').pop() || modelId,
      engine,
      model_type: hfSearchType,
      description: `From HuggingFace: ${modelId}`,
      hf_id: modelId,
    }
    
    await handleAddModel(model)
  }
  
  // Filter popular models
  const filteredModels = BUILTIN_MODELS.filter(model => {
    const matchesSearch = model.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      model.description.toLowerCase().includes(searchQuery.toLowerCase())
    const matchesType = selectedType === 'all' || model.model_type === selectedType
    return matchesSearch && matchesType
  })
  
  // Separate popular and other models
  const popularModels = filteredModels.filter(m => m.popular)
  const otherModels = filteredModels.filter(m => !m.popular)
  
  // Close on escape
  useEffect(() => {
    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    if (isOpen) {
      document.addEventListener('keydown', handleEscape)
      return () => document.removeEventListener('keydown', handleEscape)
    }
  }, [isOpen, onClose])
  
  if (!isOpen) return null
  
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      {/* Backdrop */}
      <div 
        className="absolute inset-0 bg-black/50 backdrop-blur-sm"
        onClick={onClose}
      />
      
      {/* Modal */}
      <div className="relative bg-white dark:bg-dark-200 rounded-2xl shadow-2xl w-full max-w-3xl max-h-[85vh] flex flex-col animate-fade-in">
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b border-cream-200 dark:border-dark-50">
          <h2 className="text-xl font-serif text-surface-900">Add Model</h2>
          <button
            onClick={onClose}
            className="p-2 hover:bg-cream-200 dark:hover:bg-dark-100 rounded-lg transition-colors"
          >
            <X className="w-5 h-5 text-surface-600" />
          </button>
        </div>
        
        {/* Tabs */}
        <div className="flex border-b border-cream-200 dark:border-dark-50">
          {(['popular', 'huggingface', 'local'] as const).map(tab => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              className={`flex-1 py-3 text-sm font-medium transition-colors ${
                activeTab === tab
                  ? 'text-olive-700 dark:text-olive-300 border-b-2 border-olive-500'
                  : 'text-surface-500 hover:text-surface-700'
              }`}
            >
              {tab === 'popular' && 'Popular Models'}
              {tab === 'huggingface' && 'HuggingFace Search'}
              {tab === 'local' && 'Upload Local'}
            </button>
          ))}
        </div>
        
        {/* Content */}
        <div className="flex-1 overflow-hidden flex flex-col p-6">
          {activeTab === 'popular' && (
            <>
              {/* Filters */}
              <div className="flex gap-4 mb-4">
                <div className="relative flex-1">
                  <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-surface-400" />
                  <input
                    type="text"
                    placeholder="Search models..."
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    className="input pl-10"
                  />
                </div>
                
                <div className="flex gap-1 bg-cream-100 dark:bg-dark-100 p-1 rounded-lg">
                  {(['all', 'whisper', 'diarization', 'tts'] as const).map(type => (
                    <button
                      key={type}
                      onClick={() => setSelectedType(type)}
                      className={`px-3 py-1.5 text-sm rounded-md transition-colors ${
                        selectedType === type
                          ? 'bg-white dark:bg-dark-200 text-surface-800 dark:text-surface-200 shadow-sm'
                          : 'text-surface-600 hover:text-surface-800'
                      }`}
                    >
                      {type === 'all' ? 'All' : type === 'whisper' ? 'STT' : type === 'diarization' ? 'Diarize' : 'TTS'}
                    </button>
                  ))}
                </div>
              </div>
              
              {/* Model List */}
              <div className="flex-1 overflow-y-auto space-y-4">
                {/* Popular section */}
                {popularModels.length > 0 && (
                  <div>
                    <h4 className="flex items-center gap-2 text-sm font-medium text-surface-600 dark:text-surface-400 mb-2">
                      <Star className="w-4 h-4 text-amber-500" />
                      Recommended
                    </h4>
                    <div className="space-y-2">
                      {popularModels.map(model => (
                        <ModelCard 
                          key={model.id} 
                          model={model} 
                          downloading={downloading}
                          onAdd={handleAddModel}
                        />
                      ))}
                    </div>
                  </div>
                )}
                
                {/* Other models */}
                {otherModels.length > 0 && (
                  <div>
                    {popularModels.length > 0 && (
                      <h4 className="text-sm font-medium text-surface-600 dark:text-surface-400 mb-2 mt-4">
                        Other Models
                      </h4>
                    )}
                    <div className="space-y-2">
                      {otherModels.map(model => (
                        <ModelCard 
                          key={model.id} 
                          model={model} 
                          downloading={downloading}
                          onAdd={handleAddModel}
                        />
                      ))}
                    </div>
                  </div>
                )}
                
                {filteredModels.length === 0 && (
                  <div className="text-center py-8 text-surface-500">
                    No models found matching your criteria
                  </div>
                )}
              </div>
            </>
          )}
          
          {activeTab === 'huggingface' && (
            <>
              {/* Search controls */}
              <div className="flex gap-4 mb-4">
                <div className="relative flex-1">
                  <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-surface-400" />
                  <input
                    type="text"
                    placeholder={`Search ${hfSearchType} models on HuggingFace...`}
                    value={hfSearchQuery}
                    onChange={(e) => setHfSearchQuery(e.target.value)}
                    onKeyDown={(e) => e.key === 'Enter' && searchHuggingFace()}
                    className="input pl-10 pr-20"
                  />
                  <button
                    onClick={searchHuggingFace}
                    disabled={hfLoading || !hfSearchQuery.trim()}
                    className="absolute right-2 top-1/2 -translate-y-1/2 px-3 py-1 bg-olive-600 hover:bg-olive-700 disabled:bg-surface-400 text-white text-sm rounded-md transition-colors"
                  >
                    {hfLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : 'Search'}
                  </button>
                </div>
                
                <div className="flex gap-1 bg-cream-100 dark:bg-dark-100 p-1 rounded-lg">
                  {(['whisper', 'diarization', 'tts'] as const).map(type => (
                    <button
                      key={type}
                      onClick={() => {
                        setHfSearchType(type)
                        setHfResults([])
                      }}
                      className={`px-3 py-1.5 text-sm rounded-md transition-colors ${
                        hfSearchType === type
                          ? 'bg-white dark:bg-dark-200 text-surface-800 dark:text-surface-200 shadow-sm'
                          : 'text-surface-600 hover:text-surface-800'
                      }`}
                    >
                      {type === 'whisper' ? 'STT' : type === 'diarization' ? 'Diarize' : 'TTS'}
                    </button>
                  ))}
                </div>
              </div>
              
              {/* Info message */}
              <div className="flex items-start gap-2 p-3 bg-blue-50 dark:bg-blue-900/20 rounded-lg mb-4 text-sm">
                <AlertCircle className="w-4 h-4 text-blue-600 dark:text-blue-400 mt-0.5 flex-shrink-0" />
                <div className="text-blue-800 dark:text-blue-300">
                  <span className="font-medium">Only compatible models shown.</span> Search results are filtered to models supported by this application:
                  <span className="text-blue-600 dark:text-blue-400"> {SUPPORTED_HF_PATTERNS[hfSearchType].join(', ')}</span>
                </div>
              </div>
              
              {/* Results */}
              <div className="flex-1 overflow-y-auto space-y-2">
                {hfResults.length > 0 ? (
                  hfResults.map(model => (
                    <HFModelCard 
                      key={model.id || model.modelId}
                      model={model}
                      type={hfSearchType}
                      downloading={downloading}
                      onAdd={() => handleAddHFModel(model)}
                    />
                  ))
                ) : hfSearchQuery && !hfLoading ? (
                  <div className="text-center py-8 text-surface-500">
                    No compatible models found. Try a different search term.
                  </div>
                ) : (
                  <div className="text-center py-8 text-surface-500">
                    <ExternalLink className="w-10 h-10 mx-auto mb-3 opacity-50" />
                    <p>Search HuggingFace for {hfSearchType === 'whisper' ? 'speech-to-text' : hfSearchType} models</p>
                    <p className="text-xs mt-1">Try: "whisper", "distil", "large-v3"</p>
                  </div>
                )}
              </div>
            </>
          )}
          
          {activeTab === 'local' && (
            <div className="text-center py-12">
              <Upload className="w-12 h-12 text-surface-400 mx-auto mb-4" />
              <h3 className="text-lg font-medium text-surface-700 dark:text-surface-300">
                Upload Local Model
              </h3>
              <p className="text-sm text-surface-500 mt-2 max-w-md mx-auto">
                Upload a model from your local filesystem. Supports GGML, ONNX, and PyTorch formats.
              </p>
              <button className="btn-primary mt-4" disabled>
                Coming Soon
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

// Model card component for popular models
function ModelCard({ model, downloading, onAdd }: { 
  model: BuiltinModel
  downloading: string | null
  onAdd: (model: BuiltinModel) => void
}) {
  return (
    <div className="p-3 bg-cream-50 dark:bg-dark-100 rounded-xl border border-cream-200 dark:border-dark-50">
      <div className="flex items-center gap-3">
        <div className={`w-9 h-9 rounded-lg flex items-center justify-center flex-shrink-0 ${
          model.model_type === 'whisper' ? 'bg-olive-100 dark:bg-olive-900/30' :
          model.model_type === 'diarization' ? 'bg-purple-100 dark:bg-purple-900/30' :
          'bg-amber-100 dark:bg-amber-900/30'
        }`}>
          {model.model_type === 'whisper' && <Mic className="w-4 h-4 text-olive-600 dark:text-olive-400" />}
          {model.model_type === 'diarization' && <Users className="w-4 h-4 text-purple-600 dark:text-purple-400" />}
          {model.model_type === 'tts' && <Volume2 className="w-4 h-4 text-amber-600 dark:text-amber-400" />}
        </div>
        
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="font-medium text-surface-800 dark:text-surface-200 text-sm">{model.name}</span>
            <span className="text-xs text-surface-500 bg-cream-200 dark:bg-dark-50 px-1.5 py-0.5 rounded">
              {model.engine}
            </span>
            {model.popular && (
              <Star className="w-3 h-3 text-amber-500 fill-amber-500" />
            )}
          </div>
          <div className="flex items-center gap-3 text-xs text-surface-500 mt-0.5">
            <span>{model.description}</span>
          </div>
        </div>
        
        <div className="flex items-center gap-3 text-xs text-surface-500 flex-shrink-0">
          {model.size_mb && (
            <span>{(model.size_mb / 1024).toFixed(1)}GB</span>
          )}
          {model.recommended_vram_gb && (
            <span className="flex items-center gap-0.5">
              <Cpu className="w-3 h-3" />
              {model.recommended_vram_gb}GB
            </span>
          )}
        </div>
        
        <button
          onClick={() => onAdd(model)}
          disabled={downloading !== null}
          className={`px-3 py-1.5 text-xs font-medium rounded-lg transition-colors flex items-center gap-1.5 ${
            downloading === model.id
              ? 'bg-olive-100 dark:bg-olive-900/30 text-olive-700'
              : 'bg-olive-600 hover:bg-olive-700 text-white'
          }`}
        >
          {downloading === model.id ? (
            <Loader2 className="w-3 h-3 animate-spin" />
          ) : (
            <Download className="w-3 h-3" />
          )}
          Add
        </button>
      </div>
    </div>
  )
}

// HuggingFace model card
function HFModelCard({ model, type, downloading, onAdd }: {
  model: HFModel
  type: ModelType
  downloading: string | null
  onAdd: () => void
}) {
  const modelId = model.modelId || model.id
  const isDownloading = downloading === modelId.replace('/', '-')
  
  return (
    <div className="p-3 bg-cream-50 dark:bg-dark-100 rounded-xl border border-cream-200 dark:border-dark-50">
      <div className="flex items-center gap-3">
        <div className={`w-9 h-9 rounded-lg flex items-center justify-center flex-shrink-0 ${
          type === 'whisper' ? 'bg-olive-100 dark:bg-olive-900/30' :
          type === 'diarization' ? 'bg-purple-100 dark:bg-purple-900/30' :
          'bg-amber-100 dark:bg-amber-900/30'
        }`}>
          {type === 'whisper' && <Mic className="w-4 h-4 text-olive-600 dark:text-olive-400" />}
          {type === 'diarization' && <Users className="w-4 h-4 text-purple-600 dark:text-purple-400" />}
          {type === 'tts' && <Volume2 className="w-4 h-4 text-amber-600 dark:text-amber-400" />}
        </div>
        
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className="font-medium text-surface-800 dark:text-surface-200 text-sm truncate">{modelId}</span>
          </div>
          <div className="flex items-center gap-3 text-xs text-surface-500 mt-0.5">
            <span>↓ {formatNumber(model.downloads)} downloads</span>
            <span>♥ {formatNumber(model.likes)} likes</span>
          </div>
        </div>
        
        <a
          href={`https://huggingface.co/${modelId}`}
          target="_blank"
          rel="noopener noreferrer"
          className="p-1.5 hover:bg-cream-200 dark:hover:bg-dark-50 rounded-lg transition-colors"
        >
          <ExternalLink className="w-4 h-4 text-surface-500" />
        </a>
        
        <button
          onClick={onAdd}
          disabled={downloading !== null}
          className={`px-3 py-1.5 text-xs font-medium rounded-lg transition-colors flex items-center gap-1.5 ${
            isDownloading
              ? 'bg-olive-100 dark:bg-olive-900/30 text-olive-700'
              : 'bg-olive-600 hover:bg-olive-700 text-white'
          }`}
        >
          {isDownloading ? (
            <Loader2 className="w-3 h-3 animate-spin" />
          ) : (
            <Download className="w-3 h-3" />
          )}
          Add
        </button>
      </div>
    </div>
  )
}

function formatNumber(num: number): string {
  if (num >= 1000000) return `${(num / 1000000).toFixed(1)}M`
  if (num >= 1000) return `${(num / 1000).toFixed(1)}K`
  return String(num)
}

function getEngineForType(type: ModelType): string {
  switch (type) {
    case 'whisper': return 'faster-whisper'
    case 'diarization': return 'pyannote'
    case 'tts': return 'coqui-tts'
  }
}

// Upload icon component
function Upload(props: React.SVGProps<SVGSVGElement>) {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" {...props}>
      <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
      <polyline points="17 8 12 3 7 8" />
      <line x1="12" x2="12" y1="3" y2="15" />
    </svg>
  )
}
