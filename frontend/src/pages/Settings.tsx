import { useQuery } from '@tanstack/react-query'
import { api } from '../lib/api'
import { Cpu, Activity } from 'lucide-react'

// GPU Monitoring Component with live polling
function GpuMonitor() {
  const { data: gpuData, isLoading } = useQuery({
    queryKey: ['gpu-usage'],
    queryFn: () => api.getGpuUsage(),
    refetchInterval: 2000, // Poll every 2 seconds
  })

  if (isLoading) {
    return (
      <div className="card">
        <h3 className="text-lg font-serif text-surface-800 dark:text-surface-200 mb-4">GPU Monitoring</h3>
        <div className="flex items-center gap-2 text-surface-500">
          <Activity className="w-4 h-4 animate-pulse" />
          <span>Loading GPU data...</span>
        </div>
      </div>
    )
  }

  if (!gpuData?.gpus || gpuData.gpus.length === 0) {
    return (
      <div className="card">
        <h3 className="text-lg font-serif text-surface-800 dark:text-surface-200 mb-4">GPU Monitoring</h3>
        <div className="p-4 bg-cream-50 dark:bg-dark-100 rounded-xl">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-surface-200 dark:bg-dark-50 flex items-center justify-center">
              <Cpu className="w-5 h-5 text-surface-500" />
            </div>
            <div>
              <p className="font-medium text-surface-700 dark:text-surface-300">No GPU Detected</p>
              <p className="text-sm text-surface-500">Running on CPU only</p>
            </div>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="card">
      <h3 className="text-lg font-serif text-surface-800 dark:text-surface-200 mb-4">GPU Monitoring</h3>
      <div className="space-y-4">
        {gpuData.gpus.map((gpu) => (
          <div key={gpu.index} className="p-4 bg-cream-50 dark:bg-dark-100 rounded-xl">
            <div className="flex items-center justify-between mb-3">
              <span className="font-medium text-surface-700 dark:text-surface-300">GPU {gpu.index}</span>
              {gpu.temperature_c !== null && (
                <span className="text-sm text-surface-500">{gpu.temperature_c}°C</span>
              )}
            </div>
            
            {/* Memory Usage Bar */}
            <div className="mb-3">
              <div className="flex justify-between text-sm mb-1">
                <span className="text-surface-600 dark:text-surface-400">Memory</span>
                <span className="text-surface-700 dark:text-surface-300">
                  {(gpu.memory_used_mb / 1024).toFixed(1)} / {(gpu.memory_total_mb / 1024).toFixed(1)} GB
                </span>
              </div>
              <div className="h-3 bg-surface-200 dark:bg-dark-50 rounded-full overflow-hidden">
                <div 
                  className={`h-full transition-all duration-500 rounded-full ${
                    gpu.memory_percent > 90 ? 'bg-red-500' :
                    gpu.memory_percent > 70 ? 'bg-amber-500' : 'bg-olive-500'
                  }`}
                  style={{ width: `${gpu.memory_percent}%` }}
                />
              </div>
              <div className="text-right text-xs text-surface-500 mt-1">{gpu.memory_percent.toFixed(1)}%</div>
            </div>
            
            {/* Utilization Bar */}
            {gpu.utilization_percent !== null && (
              <div>
                <div className="flex justify-between text-sm mb-1">
                  <span className="text-surface-600 dark:text-surface-400">Utilization</span>
                  <span className="text-surface-700 dark:text-surface-300">{gpu.utilization_percent}%</span>
                </div>
                <div className="h-3 bg-surface-200 dark:bg-dark-50 rounded-full overflow-hidden">
                  <div 
                    className={`h-full transition-all duration-500 rounded-full ${
                      gpu.utilization_percent > 90 ? 'bg-purple-500' :
                      gpu.utilization_percent > 50 ? 'bg-blue-500' : 'bg-cyan-500'
                    }`}
                    style={{ width: `${gpu.utilization_percent}%` }}
                  />
                </div>
              </div>
            )}
          </div>
        ))}
      </div>
      <p className="text-xs text-surface-400 mt-3">Updates every 2 seconds during active jobs</p>
    </div>
  )
}

export default function Settings() {
  const { data: hardware } = useQuery({
    queryKey: ['hardware'],
    queryFn: api.getHardware,
  })
  
  return (
    <div className="space-y-8 animate-fade-in max-w-3xl">
      <div>
        <h2 className="text-3xl font-serif text-surface-900">Settings</h2>
        <p className="mt-2 text-surface-600">
          Configure server settings and view system information
        </p>
      </div>
      
      {/* System Information */}
      <div className="card">
        <h3 className="text-lg font-serif text-surface-800 mb-4">System Information</h3>
        
        {hardware && (
          <div className="space-y-4">
            {/* CPU */}
            <div className="p-4 bg-cream-50 rounded-xl">
              <h4 className="font-medium text-surface-700 mb-2">CPU</h4>
              <div className="grid grid-cols-2 gap-4 text-sm">
                <div>
                  <span className="text-surface-500">Cores:</span>
                  <span className="ml-2 text-surface-800">{hardware.cpu.cores}</span>
                </div>
                <div>
                  <span className="text-surface-500">Threads:</span>
                  <span className="ml-2 text-surface-800">{hardware.cpu.threads}</span>
                </div>
              </div>
            </div>
            
            {/* Memory */}
            <div className="p-4 bg-cream-50 rounded-xl">
              <h4 className="font-medium text-surface-700 mb-2">Memory</h4>
              <div className="text-sm">
                <span className="text-surface-500">RAM:</span>
                <span className="ml-2 text-surface-800">{hardware.ram_gb.toFixed(1)} GB</span>
              </div>
            </div>
            
            {/* GPUs */}
            <div className="p-4 bg-cream-50 rounded-xl">
              <h4 className="font-medium text-surface-700 mb-2">GPU</h4>
              {hardware.gpus.length > 0 ? (
                <div className="space-y-2">
                  {hardware.gpus.map((gpu: any, i: number) => (
                    <div key={i} className="text-sm">
                      <div className="font-medium text-surface-800">{gpu.name}</div>
                      <div className="text-surface-500">
                        {gpu.memory_gb.toFixed(1)} GB VRAM • {gpu.vendor}
                        {gpu.compute_capability && ` • Compute ${gpu.compute_capability}`}
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-sm text-surface-500">No GPU detected - using CPU</p>
              )}
            </div>
            
            {/* Recommended Settings */}
            <div className="p-4 bg-olive-50 dark:bg-olive-900/20 rounded-xl border border-olive-200 dark:border-olive-800">
              <h4 className="font-medium text-olive-800 dark:text-olive-300 mb-2">Recommended Settings</h4>
              <div className="grid grid-cols-2 gap-4 text-sm">
                <div>
                  <span className="text-olive-600 dark:text-olive-400">Device:</span>
                  <span className="ml-2 text-olive-800 dark:text-olive-200 font-medium">{hardware.preferred_device}</span>
                </div>
                <div>
                  <span className="text-olive-600 dark:text-olive-400">Compute Type:</span>
                  <span className="ml-2 text-olive-800 dark:text-olive-200 font-medium">{hardware.recommended_compute_type}</span>
                </div>
                <div>
                  <span className="text-olive-600 dark:text-olive-400">Batch Size:</span>
                  <span className="ml-2 text-olive-800 dark:text-olive-200 font-medium">{hardware.recommended_batch_size}</span>
                </div>
                <div>
                  <span className="text-olive-600 dark:text-olive-400">Workers:</span>
                  <span className="ml-2 text-olive-800 dark:text-olive-200 font-medium">{hardware.recommended_num_workers}</span>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
      
      {/* GPU Monitoring */}
      <GpuMonitor />
      
      {/* API Documentation */}
      <div className="card">
        <h3 className="text-lg font-serif text-surface-800 mb-4">API Access</h3>
        <p className="text-sm text-surface-600 mb-4">
          This server provides a REST API that can be consumed by any client application,
          including C# WinUI3, Python, or other frontends.
        </p>
        
        <div className="space-y-3">
          <a 
            href="/docs"
            target="_blank"
            className="block p-4 bg-cream-50 hover:bg-cream-100 rounded-xl transition-colors"
          >
            <div className="font-medium text-surface-800">Interactive API Documentation</div>
            <p className="text-sm text-surface-500">Swagger UI with try-it-out functionality</p>
          </a>
          
          <a 
            href="/redoc"
            target="_blank"
            className="block p-4 bg-cream-50 hover:bg-cream-100 rounded-xl transition-colors"
          >
            <div className="font-medium text-surface-800">ReDoc Documentation</div>
            <p className="text-sm text-surface-500">Clean, readable API reference</p>
          </a>
        </div>
      </div>
      
      {/* About */}
      <div className="card">
        <h3 className="text-lg font-serif text-surface-800 mb-4">About</h3>
        <div className="prose prose-sm text-surface-600">
          <p>
            <strong>STT Server</strong> is a speech-to-text application supporting multiple
            transcription engines (Whisper, WhisperX), speaker diarization (pyannote), and
            text-to-speech synthesis (Coqui TTS, Piper, MARS5).
          </p>
          <p className="mt-2">
            Features include:
          </p>
          <ul className="list-disc list-inside mt-2 space-y-1">
            <li>Multi-format support (audio and video)</li>
            <li>Word-level timestamps with forced alignment</li>
            <li>Speaker identification and labeling</li>
            <li>TTS synthesis with original timing sync</li>
            <li>Real-time queue with WebSocket updates</li>
            <li>Pluggable model support</li>
          </ul>
        </div>
      </div>
    </div>
  )
}
