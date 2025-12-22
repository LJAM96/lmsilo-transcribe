import { useState, useEffect } from 'react'
import { User, Edit2, Check, X, Palette } from 'lucide-react'
import toast from 'react-hot-toast'

interface Speaker {
  id: string
  name: string
  color: string
  segmentCount: number
}

interface SpeakerManagerProps {
  jobId: string
  speakers: Speaker[]
  onSpeakersChange: (speakers: Speaker[]) => void
}

// Predefined color palette
const COLOR_PALETTE = [
  { name: 'Blue', value: '#3b82f6', bg: 'bg-blue-500' },
  { name: 'Purple', value: '#8b5cf6', bg: 'bg-purple-500' },
  { name: 'Pink', value: '#ec4899', bg: 'bg-pink-500' },
  { name: 'Red', value: '#ef4444', bg: 'bg-red-500' },
  { name: 'Orange', value: '#f97316', bg: 'bg-orange-500' },
  { name: 'Amber', value: '#f59e0b', bg: 'bg-amber-500' },
  { name: 'Green', value: '#22c55e', bg: 'bg-green-500' },
  { name: 'Teal', value: '#14b8a6', bg: 'bg-teal-500' },
  { name: 'Cyan', value: '#06b6d4', bg: 'bg-cyan-500' },
  { name: 'Indigo', value: '#6366f1', bg: 'bg-indigo-500' },
]

export default function SpeakerManager({ jobId, speakers, onSpeakersChange }: SpeakerManagerProps) {
  const [editingId, setEditingId] = useState<string | null>(null)
  const [editName, setEditName] = useState('')
  const [showColorPicker, setShowColorPicker] = useState<string | null>(null)
  
  const startEditing = (speaker: Speaker) => {
    setEditingId(speaker.id)
    setEditName(speaker.name)
  }
  
  const cancelEditing = () => {
    setEditingId(null)
    setEditName('')
  }
  
  const saveName = async (speaker: Speaker) => {
    if (!editName.trim()) {
      cancelEditing()
      return
    }
    
    const updatedSpeakers = speakers.map(s => 
      s.id === speaker.id ? { ...s, name: editName.trim() } : s
    )
    
    try {
      // API call would go here
      // await api.updateSpeakers(jobId, updatedSpeakers)
      onSpeakersChange(updatedSpeakers)
      toast.success(`Renamed to "${editName.trim()}"`)
    } catch (error) {
      toast.error('Failed to rename speaker')
    }
    
    cancelEditing()
  }
  
  const changeColor = (speaker: Speaker, color: string) => {
    const updatedSpeakers = speakers.map(s =>
      s.id === speaker.id ? { ...s, color } : s
    )
    onSpeakersChange(updatedSpeakers)
    setShowColorPicker(null)
  }
  
  if (speakers.length === 0) {
    return null
  }
  
  return (
    <div className="space-y-2">
      <h4 className="text-sm font-medium text-surface-700 dark:text-surface-300 mb-3">
        Speakers ({speakers.length})
      </h4>
      
      {speakers.map(speaker => (
        <div 
          key={speaker.id}
          className="flex items-center gap-3 p-3 bg-cream-50 dark:bg-dark-100 rounded-xl"
        >
          {/* Color dot */}
          <div className="relative">
            <button
              onClick={() => setShowColorPicker(showColorPicker === speaker.id ? null : speaker.id)}
              className="w-8 h-8 rounded-full flex items-center justify-center hover:ring-2 ring-offset-2 ring-olive-400 transition-all"
              style={{ backgroundColor: speaker.color }}
            >
              <User className="w-4 h-4 text-white" />
            </button>
            
            {/* Color picker dropdown */}
            {showColorPicker === speaker.id && (
              <div className="absolute top-full left-0 mt-2 p-2 bg-white dark:bg-dark-200 rounded-xl shadow-lg border border-cream-200 dark:border-dark-50 z-10">
                <div className="grid grid-cols-5 gap-1">
                  {COLOR_PALETTE.map(color => (
                    <button
                      key={color.value}
                      onClick={() => changeColor(speaker, color.value)}
                      className={`w-6 h-6 rounded-full hover:scale-110 transition-transform ${color.bg}`}
                      title={color.name}
                    />
                  ))}
                </div>
              </div>
            )}
          </div>
          
          {/* Name (editable) */}
          <div className="flex-1 min-w-0">
            {editingId === speaker.id ? (
              <input
                type="text"
                value={editName}
                onChange={(e) => setEditName(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') saveName(speaker)
                  if (e.key === 'Escape') cancelEditing()
                }}
                className="input py-1 text-sm w-full"
                autoFocus
              />
            ) : (
              <span className="text-surface-800 dark:text-surface-200 font-medium">
                {speaker.name}
              </span>
            )}
          </div>
          
          {/* Segment count */}
          <span className="text-xs text-surface-500">
            {speaker.segmentCount} segment{speaker.segmentCount !== 1 ? 's' : ''}
          </span>
          
          {/* Edit/Save buttons */}
          <div className="flex gap-1">
            {editingId === speaker.id ? (
              <>
                <button
                  onClick={() => saveName(speaker)}
                  className="p-1.5 hover:bg-olive-100 dark:hover:bg-olive-900/30 rounded-lg transition-colors"
                >
                  <Check className="w-4 h-4 text-olive-600 dark:text-olive-400" />
                </button>
                <button
                  onClick={cancelEditing}
                  className="p-1.5 hover:bg-red-100 dark:hover:bg-red-900/30 rounded-lg transition-colors"
                >
                  <X className="w-4 h-4 text-red-600 dark:text-red-400" />
                </button>
              </>
            ) : (
              <button
                onClick={() => startEditing(speaker)}
                className="p-1.5 hover:bg-cream-200 dark:hover:bg-dark-50 rounded-lg transition-colors"
              >
                <Edit2 className="w-4 h-4 text-surface-500" />
              </button>
            )}
          </div>
        </div>
      ))}
    </div>
  )
}

// Hook to extract speakers from transcript
export function useSpeakers(segments: Array<{ speaker?: string }>) {
  const [speakers, setSpeakers] = useState<Speaker[]>([])
  
  useEffect(() => {
    // Extract unique speakers and count segments
    const speakerMap = new Map<string, { count: number; color: string }>()
    
    segments.forEach(segment => {
      if (segment.speaker) {
        const existing = speakerMap.get(segment.speaker)
        if (existing) {
          existing.count++
        } else {
          // Assign a consistent color based on speaker name
          const colorIndex = segment.speaker.split('').reduce(
            (acc, char) => acc + char.charCodeAt(0), 0
          ) % COLOR_PALETTE.length
          speakerMap.set(segment.speaker, {
            count: 1,
            color: COLOR_PALETTE[colorIndex].value,
          })
        }
      }
    })
    
    const extracted: Speaker[] = Array.from(speakerMap.entries()).map(([name, data]) => ({
      id: name,
      name,
      color: data.color,
      segmentCount: data.count,
    }))
    
    setSpeakers(extracted)
  }, [segments])
  
  return { speakers, setSpeakers }
}
