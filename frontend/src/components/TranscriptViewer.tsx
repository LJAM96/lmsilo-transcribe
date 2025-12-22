import { useState, useEffect, useRef, useCallback } from 'react'
import { User, Copy, Check, Search, X } from 'lucide-react'
import toast from 'react-hot-toast'

export interface Word {
  word: string
  start: number
  end: number
  confidence?: number
}

export interface TranscriptSegment {
  id: number
  start: number
  end: number
  text: string
  speaker?: string
  words?: Word[]
}

interface TranscriptViewerProps {
  segments: TranscriptSegment[]
  currentTime: number
  onSeek: (time: number) => void
  showConfidence?: boolean
  onUpdateSegment?: (id: number, text: string) => Promise<void>
}

export default function TranscriptViewer({ 
  segments, 
  currentTime, 
  onSeek,
  showConfidence = false,
  onUpdateSegment
}: TranscriptViewerProps) {
  const [searchQuery, setSearchQuery] = useState('')
  const [copiedFull, setCopiedFull] = useState(false)
  const [editingId, setEditingId] = useState<number | null>(null)
  const [editText, setEditText] = useState('')
  const [isSaving, setIsSaving] = useState(false)
  
  const containerRef = useRef<HTMLDivElement>(null)
  const activeSegmentRef = useRef<HTMLDivElement>(null)
  
  // Find current segment and word based on playback time
  const currentSegmentIndex = segments.findIndex(
    seg => currentTime >= seg.start && currentTime < seg.end
  )
  
  // Auto-scroll to active segment
  useEffect(() => {
    if (activeSegmentRef.current && containerRef.current && !editingId) {
      const container = containerRef.current
      const element = activeSegmentRef.current
      const elementTop = element.offsetTop - container.offsetTop
      const elementBottom = elementTop + element.offsetHeight
      const containerScroll = container.scrollTop
      const containerHeight = container.clientHeight
      
      // Scroll if element is outside visible area
      if (elementTop < containerScroll || elementBottom > containerScroll + containerHeight) {
        container.scrollTo({
          top: elementTop - containerHeight / 3,
          behavior: 'smooth'
        })
      }
    }
  }, [currentSegmentIndex, editingId])
  
  // Filter segments by search
  const filteredSegments = searchQuery
    ? segments.filter(seg => 
        seg.text.toLowerCase().includes(searchQuery.toLowerCase()) ||
        seg.speaker?.toLowerCase().includes(searchQuery.toLowerCase())
      )
    : segments
  
  // Copy full transcript
  const copyFullTranscript = useCallback(() => {
    const text = segments.map(seg => {
      const speaker = seg.speaker ? `[${seg.speaker}] ` : ''
      return `${speaker}${seg.text}`
    }).join('\n\n')
    
    navigator.clipboard.writeText(text)
    setCopiedFull(true)
    toast.success('Transcript copied to clipboard')
    setTimeout(() => setCopiedFull(false), 2000)
  }, [segments])
  
  // Copy selected text
  const copySelection = useCallback(() => {
    const selection = window.getSelection()?.toString()
    if (selection) {
      navigator.clipboard.writeText(selection)
      toast.success('Selection copied')
    }
  }, [])

  // Start editing
  const handleStartEdit = (segment: TranscriptSegment) => {
    if (!onUpdateSegment) return
    setEditingId(segment.id)
    setEditText(segment.text)
  }

  // Save edit
  const handleSaveEdit = async () => {
    if (!editingId || !onUpdateSegment) return
    
    try {
      setIsSaving(true)
      await onUpdateSegment(editingId, editText)
      setEditingId(null)
      toast.success('Segment updated')
    } catch (error) {
      toast.error('Failed to update segment')
      console.error(error)
    } finally {
      setIsSaving(false)
    }
  }
  
  return (
    <div className="flex flex-col h-full">
      {/* Toolbar */}
      <div className="flex items-center gap-2 mb-4 flex-wrap">
        {/* Search */}
        <div className="relative flex-1 min-w-[200px]">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-surface-400" />
          <input
            type="text"
            placeholder="Search transcript..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="input pl-9 py-2 text-sm"
          />
          {searchQuery && (
            <button
              onClick={() => setSearchQuery('')}
              className="absolute right-3 top-1/2 -translate-y-1/2 text-surface-400 hover:text-surface-600"
            >
              <X className="w-4 h-4" />
            </button>
          )}
        </div>
        
        {/* Copy buttons */}
        <button
          onClick={copyFullTranscript}
          className="px-3 py-2 text-sm font-medium bg-cream-200 dark:bg-dark-100 hover:bg-cream-300 dark:hover:bg-dark-50 text-surface-700 dark:text-surface-300 rounded-lg transition-colors flex items-center gap-1.5"
        >
          {copiedFull ? <Check className="w-4 h-4" /> : <Copy className="w-4 h-4" />}
          Copy All
        </button>
        
        <button
          onClick={copySelection}
          className="px-3 py-2 text-sm font-medium bg-cream-200 dark:bg-dark-100 hover:bg-cream-300 dark:hover:bg-dark-50 text-surface-700 dark:text-surface-300 rounded-lg transition-colors flex items-center gap-1.5"
        >
          <Copy className="w-4 h-4" />
          Copy Selection
        </button>
      </div>
      
      {/* Segments */}
      <div 
        ref={containerRef}
        className="flex-1 overflow-y-auto space-y-2 pr-2"
      >
        {filteredSegments.map((segment, index) => {
          const isActive = index === currentSegmentIndex && !searchQuery
          const isEditing = editingId === segment.id
          const segmentRef = isActive ? activeSegmentRef : null
          
          return (
            <div
              key={segment.id}
              ref={segmentRef}
              className={`p-3 rounded-xl transition-all duration-200 ${
                isEditing 
                  ? 'bg-white dark:bg-dark-200 ring-2 ring-olive-500 shadow-lg'
                  : isActive 
                    ? 'bg-olive-100 dark:bg-olive-900/30 ring-2 ring-olive-400 cursor-pointer' 
                    : 'bg-cream-50 dark:bg-dark-100 hover:bg-cream-100 dark:hover:bg-dark-50 cursor-pointer'
              }`}
              onClick={() => !isEditing && onSeek(segment.start)}
              onDoubleClick={() => !isEditing && handleStartEdit(segment)}
            >
              {/* Segment header */}
              <div className="flex items-center gap-2 mb-1.5">
                <span className={`text-xs font-mono ${isActive ? 'text-olive-700 dark:text-olive-300' : 'text-surface-500'}`}>
                  {formatTimestamp(segment.start)}
                </span>
                {segment.speaker && (
                  <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium ${
                    getSpeakerColor(segment.speaker)
                  }`}>
                    <User className="w-3 h-3" />
                    {segment.speaker}
                  </span>
                )}
                {onUpdateSegment && !isEditing && (
                  <span className="text-[10px] text-surface-400 opacity-0 group-hover:opacity-100 transition-opacity ml-auto">
                    Double-click to edit
                  </span>
                )}
              </div>
              
              {/* Content */}
              {isEditing ? (
                <div className="space-y-2" onClick={e => e.stopPropagation()}>
                  <textarea
                    value={editText}
                    onChange={(e) => setEditText(e.target.value)}
                    className="w-full h-24 p-2 text-sm bg-transparent border border-surface-200 dark:border-surface-700 rounded-lg focus:outline-none focus:ring-2 focus:ring-olive-500 resize-none"
                    autoFocus
                  />
                  <div className="flex justify-end gap-2">
                    <button
                      onClick={() => setEditingId(null)}
                      className="px-3 py-1 text-xs font-medium text-surface-600 hover:bg-surface-100 dark:hover:bg-dark-50 rounded-md"
                      disabled={isSaving}
                    >
                      Cancel
                    </button>
                    <button
                      onClick={handleSaveEdit}
                      className="px-3 py-1 text-xs font-medium bg-olive-600 text-white hover:bg-olive-700 rounded-md disabled:opacity-50"
                      disabled={isSaving}
                    >
                      {isSaving ? 'Saving...' : 'Save'}
                    </button>
                  </div>
                </div>
              ) : (
                <div className="text-surface-800 dark:text-surface-200 leading-relaxed group relative">
                  {segment.words && segment.words.length > 0 ? (
                    segment.words.map((word, wordIndex) => {
                      const isCurrentWord = currentTime >= word.start && currentTime < word.end
                      const confidenceClass = showConfidence ? getConfidenceClass(word.confidence) : ''
                      
                      return (
                        <span
                          key={wordIndex}
                          onClick={(e) => {
                            e.stopPropagation()
                            onSeek(word.start)
                          }}
                          className={`inline hover:bg-olive-200 dark:hover:bg-olive-800/50 rounded px-0.5 transition-colors ${
                            isCurrentWord ? 'bg-olive-300 dark:bg-olive-700 font-medium' : ''
                          } ${confidenceClass}`}
                        >
                          {word.word}{' '}
                        </span>
                      )
                    })
                  ) : (
                    <HighlightedText 
                      text={segment.text} 
                      query={searchQuery}
                      isActive={isActive}
                    />
                  )}
                </div>
              )}
            </div>
          )
        })}
        
        {filteredSegments.length === 0 && (
          <div className="text-center py-8 text-surface-500">
            {searchQuery ? 'No results found' : 'No transcript available'}
          </div>
        )}
      </div>
    </div>
  )
}

// Highlight search matches
function HighlightedText({ text, query, isActive }: { text: string, query: string, isActive: boolean }) {
  if (!query) {
    return <span>{text}</span>
  }
  
  const parts = text.split(new RegExp(`(${query})`, 'gi'))
  
  return (
    <>
      {parts.map((part, i) => 
        part.toLowerCase() === query.toLowerCase() ? (
          <mark key={i} className="bg-amber-200 dark:bg-amber-700 rounded px-0.5">{part}</mark>
        ) : (
          <span key={i}>{part}</span>
        )
      )}
    </>
  )
}

// Format timestamp as MM:SS
function formatTimestamp(seconds: number): string {
  const m = Math.floor(seconds / 60)
  const s = Math.floor(seconds % 60)
  return `${m}:${s.toString().padStart(2, '0')}`
}

// Get speaker color based on speaker name
function getSpeakerColor(speaker: string): string {
  const colors = [
    'bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300',
    'bg-purple-100 dark:bg-purple-900/30 text-purple-700 dark:text-purple-300',
    'bg-pink-100 dark:bg-pink-900/30 text-pink-700 dark:text-pink-300',
    'bg-cyan-100 dark:bg-cyan-900/30 text-cyan-700 dark:text-cyan-300',
    'bg-amber-100 dark:bg-amber-900/30 text-amber-700 dark:text-amber-300',
    'bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-300',
  ]
  
  // Simple hash to get consistent color for same speaker
  const hash = speaker.split('').reduce((acc, char) => acc + char.charCodeAt(0), 0)
  return colors[hash % colors.length]
}

// Get confidence-based styling
function getConfidenceClass(confidence?: number): string {
  if (confidence === undefined) return ''
  
  if (confidence >= 0.9) return '' // High confidence - no special styling
  if (confidence >= 0.7) return 'text-amber-700 dark:text-amber-400' // Medium confidence
  return 'text-red-600 dark:text-red-400 underline decoration-dotted' // Low confidence
}
