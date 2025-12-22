import { useState, useRef, useCallback, useEffect } from 'react'
import { Mic, MicOff, Square, Loader2 } from 'lucide-react'

interface TranscriptLine {
  id: number
  text: string
  language?: string
  isFinal: boolean
  timestamp: Date
}

export default function LiveTranscribe() {
  const [isRecording, setIsRecording] = useState(false)
  const [isConnected, setIsConnected] = useState(false)
  const [transcripts, setTranscripts] = useState<TranscriptLine[]>([])
  const [error, setError] = useState<string | null>(null)
  
  const wsRef = useRef<WebSocket | null>(null)
  const audioContextRef = useRef<AudioContext | null>(null)
  const processorRef = useRef<ScriptProcessorNode | null>(null)
  const streamRef = useRef<MediaStream | null>(null)
  const lineIdRef = useRef(0)

  const connectWebSocket = useCallback(() => {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const ws = new WebSocket(`${protocol}//${window.location.host}/api/stream/ws`)
    
    ws.onopen = () => {
      setIsConnected(true)
      setError(null)
    }
    
    ws.onmessage = (event) => {
      const data = JSON.parse(event.data)
      
      if (data.type === 'transcript') {
        setTranscripts(prev => [...prev, {
          id: lineIdRef.current++,
          text: data.text,
          language: data.language,
          isFinal: data.is_final,
          timestamp: new Date(),
        }])
      } else if (data.type === 'error') {
        setError(data.message)
      }
    }
    
    ws.onerror = () => {
      setError('WebSocket connection error')
    }
    
    ws.onclose = () => {
      setIsConnected(false)
    }
    
    wsRef.current = ws
    return ws
  }, [])

  const startRecording = async () => {
    try {
      // Get microphone access
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          sampleRate: 16000,
          channelCount: 1,
          echoCancellation: true,
          noiseSuppression: true,
        },
      })
      
      streamRef.current = stream
      
      // Connect WebSocket
      const ws = connectWebSocket()
      
      // Wait for connection
      await new Promise<void>((resolve, reject) => {
        const timeout = setTimeout(() => reject(new Error('Connection timeout')), 5000)
        ws.onopen = () => {
          clearTimeout(timeout)
          resolve()
        }
        ws.onerror = () => {
          clearTimeout(timeout)
          reject(new Error('Connection failed'))
        }
      })
      
      // Create audio context for processing
      const audioContext = new AudioContext({ sampleRate: 16000 })
      audioContextRef.current = audioContext
      
      const source = audioContext.createMediaStreamSource(stream)
      const processor = audioContext.createScriptProcessor(4096, 1, 1)
      processorRef.current = processor
      
      processor.onaudioprocess = (e) => {
        if (wsRef.current?.readyState === WebSocket.OPEN) {
          const inputData = e.inputBuffer.getChannelData(0)
          
          // Convert Float32 to Int16
          const pcm16 = new Int16Array(inputData.length)
          for (let i = 0; i < inputData.length; i++) {
            const s = Math.max(-1, Math.min(1, inputData[i]))
            pcm16[i] = s < 0 ? s * 0x8000 : s * 0x7FFF
          }
          
          wsRef.current.send(pcm16.buffer)
        }
      }
      
      source.connect(processor)
      processor.connect(audioContext.destination)
      
      setIsRecording(true)
      setError(null)
      
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to start recording')
    }
  }

  const stopRecording = () => {
    // Stop audio processing
    if (processorRef.current) {
      processorRef.current.disconnect()
      processorRef.current = null
    }
    
    if (audioContextRef.current) {
      audioContextRef.current.close()
      audioContextRef.current = null
    }
    
    // Stop media stream
    if (streamRef.current) {
      streamRef.current.getTracks().forEach(track => track.stop())
      streamRef.current = null
    }
    
    // Close WebSocket
    if (wsRef.current) {
      wsRef.current.close()
      wsRef.current = null
    }
    
    setIsRecording(false)
  }

  const clearTranscripts = () => {
    setTranscripts([])
    lineIdRef.current = 0
  }

  useEffect(() => {
    return () => {
      stopRecording()
    }
  }, [])

  return (
    <div className="space-y-6 animate-fade-in">
      <div>
        <h2 className="text-3xl font-serif text-surface-900 dark:text-surface-100">Live Transcribe</h2>
        <p className="mt-2 text-surface-600 dark:text-surface-400">
          Real-time speech-to-text transcription
        </p>
      </div>

      {/* Controls */}
      <div className="card">
        <div className="flex items-center gap-4">
          {!isRecording ? (
            <button
              onClick={startRecording}
              className="flex items-center gap-2 px-6 py-3 rounded-xl bg-olive-600 text-white hover:bg-olive-700 transition-colors"
            >
              <Mic className="w-5 h-5" />
              Start Recording
            </button>
          ) : (
            <button
              onClick={stopRecording}
              className="flex items-center gap-2 px-6 py-3 rounded-xl bg-red-500 text-white hover:bg-red-600 transition-colors"
            >
              <Square className="w-5 h-5" />
              Stop Recording
            </button>
          )}
          
          <button
            onClick={clearTranscripts}
            className="px-4 py-2 text-surface-600 hover:text-surface-800 dark:text-surface-400 dark:hover:text-surface-200"
          >
            Clear
          </button>
          
          {/* Status indicators */}
          <div className="ml-auto flex items-center gap-2">
            {isRecording && (
              <div className="flex items-center gap-2 text-red-500">
                <span className="w-2 h-2 rounded-full bg-red-500 animate-pulse" />
                Recording
              </div>
            )}
            {isConnected && (
              <div className="flex items-center gap-2 text-green-500">
                <span className="w-2 h-2 rounded-full bg-green-500" />
                Connected
              </div>
            )}
          </div>
        </div>

        {error && (
          <div className="mt-4 p-4 bg-red-50 dark:bg-red-900/20 rounded-xl text-red-600 dark:text-red-400">
            {error}
          </div>
        )}
      </div>

      {/* Transcript Display */}
      <div className="card min-h-[400px]">
        <h3 className="text-lg font-serif text-surface-800 dark:text-surface-200 mb-4">Transcript</h3>
        
        {transcripts.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-64 text-surface-400">
            <MicOff className="w-12 h-12 mb-4" />
            <p>Start recording to see live transcription</p>
          </div>
        ) : (
          <div className="space-y-3">
            {transcripts.map((line) => (
              <div
                key={line.id}
                className={`p-3 rounded-lg ${
                  line.isFinal
                    ? 'bg-cream-50 dark:bg-dark-100'
                    : 'bg-olive-50 dark:bg-olive-900/20 border border-olive-200 dark:border-olive-700'
                }`}
              >
                <p className="text-surface-800 dark:text-surface-200">{line.text}</p>
                <div className="flex items-center gap-2 mt-1 text-xs text-surface-400">
                  {line.language && <span>Language: {line.language}</span>}
                  <span>{line.timestamp.toLocaleTimeString()}</span>
                  {!line.isFinal && (
                    <span className="flex items-center gap-1 text-olive-600">
                      <Loader2 className="w-3 h-3 animate-spin" />
                      processing
                    </span>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
