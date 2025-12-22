import type { TranscriptionOptions } from '../pages/Dashboard'
import Toggle from './Toggle'

interface Model {
  id: string
  name: string
  model_type: 'whisper' | 'diarization' | 'tts'
  engine: string
  is_default: boolean
  is_downloaded: boolean
}

interface TranscriptionSettingsProps {
  options: TranscriptionOptions
  onChange: (options: TranscriptionOptions) => void
  models: Model[]
}

const LANGUAGES = [
  { code: 'auto', name: 'Auto-detect' },
  { code: 'en', name: 'English' },
  { code: 'es', name: 'Spanish' },
  { code: 'fr', name: 'French' },
  { code: 'de', name: 'German' },
  { code: 'it', name: 'Italian' },
  { code: 'pt', name: 'Portuguese' },
  { code: 'ru', name: 'Russian' },
  { code: 'ja', name: 'Japanese' },
  { code: 'ko', name: 'Korean' },
  { code: 'zh', name: 'Chinese' },
  { code: 'ar', name: 'Arabic' },
  { code: 'nl', name: 'Dutch' },
  { code: 'pl', name: 'Polish' },
  { code: 'tr', name: 'Turkish' },
]

export default function TranscriptionSettings({ 
  options, 
  onChange, 
  models 
}: TranscriptionSettingsProps) {
  const whisperModels = models.filter(m => m.model_type === 'whisper')
  const diarizationModels = models.filter(m => m.model_type === 'diarization')
  const ttsModels = models.filter(m => m.model_type === 'tts')
  
  const update = (key: keyof TranscriptionOptions, value: any) => {
    onChange({ ...options, [key]: value })
  }
  
  return (
    <div className="space-y-6">
      {/* STT Model Selection */}
      <div>
        <label className="block text-sm font-medium text-surface-700 mb-2">
          Transcription Model
        </label>
        <select
          className="select"
          value={options.modelId || ''}
          onChange={(e) => update('modelId', e.target.value || null)}
        >
          <option value="">Default Model</option>
          {whisperModels.map(model => (
            <option key={model.id} value={model.id} disabled={!model.is_downloaded}>
              {model.name} ({model.engine})
              {!model.is_downloaded && ' - Not downloaded'}
              {model.is_default && ' ★'}
            </option>
          ))}
        </select>
      </div>
      
      {/* Language Selection */}
      <div>
        <label className="block text-sm font-medium text-surface-700 mb-2">
          Language
        </label>
        <select
          className="select"
          value={options.language}
          onChange={(e) => update('language', e.target.value)}
        >
          {LANGUAGES.map(lang => (
            <option key={lang.code} value={lang.code}>
              {lang.name}
            </option>
          ))}
        </select>
      </div>
      
      {/* Translation */}
      <div>
        <label className="block text-sm font-medium text-surface-700 dark:text-surface-300 mb-2">
          Translate To
        </label>
        <select
          className="select"
          value={(options as any).translateTo || ''}
          onChange={(e) => update('translateTo' as any, e.target.value || null)}
        >
          <option value="">No translation (keep original)</option>
          <option value="en">English</option>
          <option value="es">Spanish</option>
          <option value="fr">French</option>
          <option value="de">German</option>
          <option value="it">Italian</option>
          <option value="pt">Portuguese</option>
          <option value="zh">Chinese (Simplified)</option>
          <option value="ja">Japanese</option>
          <option value="ko">Korean</option>
          <option value="ar">Arabic</option>
        </select>
        <p className="text-xs text-surface-500 mt-1">
          Whisper translates to English. Other languages use LibreTranslate.
        </p>
      </div>
      
      {/* Divider */}
      <div className="border-t border-cream-300 dark:border-dark-50" />
      
      {/* Speaker Diarization */}
      <div>
        <div className="flex items-center gap-3">
          <Toggle
            checked={options.enableDiarization}
            onChange={(checked) => update('enableDiarization', checked)}
          />
          <div className="cursor-pointer" onClick={() => update('enableDiarization', !options.enableDiarization)}>
            <span className="font-medium text-surface-800">Speaker Diarization</span>
            <p className="text-sm text-surface-500">Identify and label different speakers</p>
          </div>
        </div>
        
        {options.enableDiarization && diarizationModels.length > 0 && (
          <div className="mt-3 ml-8">
            <select
              className="select"
              value={options.diarizationModelId || ''}
              onChange={(e) => update('diarizationModelId', e.target.value || null)}
            >
              <option value="">Default Model</option>
              {diarizationModels.map(model => (
                <option key={model.id} value={model.id} disabled={!model.is_downloaded}>
                  {model.name}
                  {!model.is_downloaded && ' - Not downloaded'}
                </option>
              ))}
            </select>
          </div>
        )}
      </div>
      
      {/* TTS Synthesis */}
      <div>
        <div className="flex items-center gap-3">
          <Toggle
            checked={options.enableTts}
            onChange={(checked) => update('enableTts', checked)}
          />
          <div className="cursor-pointer" onClick={() => update('enableTts', !options.enableTts)}>
            <span className="font-medium text-surface-800">TTS Output</span>
            <p className="text-sm text-surface-500">Generate synthesized audio from transcript</p>
          </div>
        </div>
        
        {options.enableTts && (
          <div className="mt-3 ml-8 space-y-3">
            {ttsModels.length > 0 && (
              <select
                className="select"
                value={options.ttsModelId || ''}
                onChange={(e) => update('ttsModelId', e.target.value || null)}
              >
                <option value="">Default Model</option>
                {ttsModels.map(model => (
                  <option key={model.id} value={model.id} disabled={!model.is_downloaded}>
                    {model.name} ({model.engine})
                    {!model.is_downloaded && ' - Not downloaded'}
                  </option>
                ))}
              </select>
            )}
            
            <div className="flex items-center gap-2">
              <Toggle
                size="sm"
                checked={options.syncTtsTiming}
                onChange={(checked) => update('syncTtsTiming', checked)}
              />
              <span 
                className="text-sm text-surface-700 cursor-pointer"
                onClick={() => update('syncTtsTiming', !options.syncTtsTiming)}
              >
                Sync audio timing with original
              </span>
            </div>
          </div>
        )}
      </div>
      
      {/* Divider */}
      <div className="border-t border-cream-300" />
      
      {/* Output Formats */}
      <div>
        <label className="block text-sm font-medium text-surface-700 mb-3">
          Output Formats
        </label>
        <div className="flex flex-wrap gap-2">
          {['json', 'srt', 'vtt', 'txt'].map(format => (
            <label key={format} className="cursor-pointer">
              <input
                type="checkbox"
                className="sr-only peer"
                checked={options.outputFormats.includes(format)}
                onChange={(e) => {
                  if (e.target.checked) {
                    update('outputFormats', [...options.outputFormats, format])
                  } else {
                    update('outputFormats', options.outputFormats.filter(f => f !== format))
                  }
                }}
              />
              <span className="inline-block px-3 py-1.5 rounded-lg border border-cream-300 text-sm font-medium text-surface-600 peer-checked:bg-olive-100 peer-checked:border-olive-400 peer-checked:text-olive-800 transition-colors">
                {format.toUpperCase()}
              </span>
            </label>
          ))}
        </div>
      </div>
      
      {/* Priority */}
      <div>
        <label className="block text-sm font-medium text-surface-700 mb-2">
          Priority
        </label>
        <input
          type="range"
          min="1"
          max="10"
          value={options.priority}
          onChange={(e) => update('priority', Number(e.target.value))}
          className="w-full accent-olive-600"
        />
        <div className="flex justify-between text-xs text-surface-500 mt-1">
          <span>High (1)</span>
          <span className="font-medium text-olive-600">{options.priority}</span>
          <span>Low (10)</span>
        </div>
      </div>
    </div>
  )
}
