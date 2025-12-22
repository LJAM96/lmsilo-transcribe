import { useEffect, useRef, useState } from 'react'
import WaveSurfer from 'wavesurfer.js'
import { Play, Pause, Volume2, VolumeX } from 'lucide-react'

interface WaveformProps {
  audioUrl: string
  currentTime?: number
  onSeek?: (time: number) => void
  onTimeUpdate?: (time: number) => void
  height?: number
  waveColor?: string
  progressColor?: string
  className?: string
}

export default function Waveform({
  audioUrl,
  currentTime,
  onSeek,
  onTimeUpdate,
  height = 80,
  waveColor = '#d4c9b8',
  progressColor = '#6d7a4e',
  className = '',
}: WaveformProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const wavesurfer = useRef<WaveSurfer | null>(null)
  const [isPlaying, setIsPlaying] = useState(false)
  const [isMuted, setIsMuted] = useState(false)
  const [duration, setDuration] = useState(0)
  const [currentPosition, setCurrentPosition] = useState(0)
  const [isReady, setIsReady] = useState(false)
  
  // Initialize WaveSurfer
  useEffect(() => {
    if (!containerRef.current) return
    
    wavesurfer.current = WaveSurfer.create({
      container: containerRef.current,
      waveColor,
      progressColor,
      height,
      barWidth: 2,
      barGap: 1,
      barRadius: 2,
      cursorWidth: 2,
      cursorColor: progressColor,
      normalize: true,
      fillParent: true,
    })
    
    wavesurfer.current.load(audioUrl)
    
    wavesurfer.current.on('ready', () => {
      setDuration(wavesurfer.current?.getDuration() || 0)
      setIsReady(true)
    })
    
    wavesurfer.current.on('audioprocess', () => {
      const time = wavesurfer.current?.getCurrentTime() || 0
      setCurrentPosition(time)
      onTimeUpdate?.(time)
    })
    
    wavesurfer.current.on('seeking', () => {
      const time = wavesurfer.current?.getCurrentTime() || 0
      setCurrentPosition(time)
      onSeek?.(time)
    })
    
    wavesurfer.current.on('play', () => setIsPlaying(true))
    wavesurfer.current.on('pause', () => setIsPlaying(false))
    wavesurfer.current.on('finish', () => setIsPlaying(false))
    
    return () => {
      wavesurfer.current?.destroy()
    }
  }, [audioUrl, height, waveColor, progressColor])
  
  // Sync external currentTime to waveform
  useEffect(() => {
    if (currentTime !== undefined && wavesurfer.current && isReady) {
      const wsTime = wavesurfer.current.getCurrentTime()
      // Only seek if there's a significant difference (avoid jitter)
      if (Math.abs(wsTime - currentTime) > 0.5) {
        wavesurfer.current.seekTo(currentTime / duration)
      }
    }
  }, [currentTime, duration, isReady])
  
  const togglePlay = () => {
    wavesurfer.current?.playPause()
  }
  
  const toggleMute = () => {
    if (wavesurfer.current) {
      wavesurfer.current.setMuted(!isMuted)
      setIsMuted(!isMuted)
    }
  }
  
  return (
    <div className={`rounded-xl bg-cream-50 dark:bg-dark-100 p-4 ${className}`}>
      {/* Waveform container */}
      <div 
        ref={containerRef} 
        className="w-full mb-3 cursor-pointer"
        style={{ minHeight: height }}
      />
      
      {/* Controls */}
      <div className="flex items-center gap-4">
        <button
          onClick={togglePlay}
          disabled={!isReady}
          className="w-10 h-10 bg-olive-600 hover:bg-olive-700 disabled:bg-surface-400 text-white rounded-full flex items-center justify-center transition-colors"
        >
          {isPlaying ? (
            <Pause className="w-5 h-5" />
          ) : (
            <Play className="w-5 h-5 ml-0.5" />
          )}
        </button>
        
        <div className="flex-1">
          <div className="flex justify-between text-xs text-surface-500 mb-1">
            <span>{formatTime(currentPosition)}</span>
            <span>{formatTime(duration)}</span>
          </div>
        </div>
        
        <button
          onClick={toggleMute}
          className="p-2 hover:bg-cream-200 dark:hover:bg-dark-50 rounded-lg transition-colors"
        >
          {isMuted ? (
            <VolumeX className="w-5 h-5 text-surface-500" />
          ) : (
            <Volume2 className="w-5 h-5 text-surface-500" />
          )}
        </button>
      </div>
    </div>
  )
}

function formatTime(seconds: number): string {
  const mins = Math.floor(seconds / 60)
  const secs = Math.floor(seconds % 60)
  return `${mins}:${secs.toString().padStart(2, '0')}`
}

// Mini waveform for upload preview
export function MiniWaveform({ 
  file 
}: { 
  file: File 
}) {
  const containerRef = useRef<HTMLDivElement>(null)
  const [isLoaded, setIsLoaded] = useState(false)
  
  useEffect(() => {
    if (!containerRef.current) return
    
    const wavesurfer = WaveSurfer.create({
      container: containerRef.current,
      waveColor: '#d4c9b8',
      progressColor: '#6d7a4e',
      height: 40,
      barWidth: 2,
      barGap: 1,
      barRadius: 2,
      cursorWidth: 0,
      interact: false,
      normalize: true,
    })
    
    const url = URL.createObjectURL(file)
    wavesurfer.load(url)
    
    wavesurfer.on('ready', () => setIsLoaded(true))
    
    return () => {
      wavesurfer.destroy()
      URL.revokeObjectURL(url)
    }
  }, [file])
  
  return (
    <div 
      ref={containerRef} 
      className={`w-full transition-opacity ${isLoaded ? 'opacity-100' : 'opacity-0'}`}
      style={{ minHeight: 40 }}
    />
  )
}
