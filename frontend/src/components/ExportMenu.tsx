import { useState, useRef, useEffect } from 'react'
import { Download, FileText, FileJson, FileType, ChevronDown } from 'lucide-react'
import toast from 'react-hot-toast'

interface ExportMenuProps {
  jobId: string
  filename: string
}

type ExportFormat = 'json' | 'srt' | 'vtt' | 'txt' | 'docx' | 'pdf'

const EXPORT_OPTIONS: { format: ExportFormat; label: string; icon: typeof FileText }[] = [
  { format: 'json', label: 'JSON (with metadata)', icon: FileJson },
  { format: 'srt', label: 'SRT Subtitles', icon: FileText },
  { format: 'vtt', label: 'VTT Subtitles', icon: FileText },
  { format: 'txt', label: 'Plain Text', icon: FileType },
]

export default function ExportMenu({ jobId, filename }: ExportMenuProps) {
  const [isOpen, setIsOpen] = useState(false)
  const [exporting, setExporting] = useState<ExportFormat | null>(null)
  const menuRef = useRef<HTMLDivElement>(null)
  
  // Close menu on click outside
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setIsOpen(false)
      }
    }
    
    if (isOpen) {
      document.addEventListener('mousedown', handleClickOutside)
      return () => document.removeEventListener('mousedown', handleClickOutside)
    }
  }, [isOpen])
  
  const handleExport = async (format: ExportFormat) => {
    setExporting(format)
    
    try {
      let url: string
      let downloadFilename: string
      
      switch (format) {
        case 'json':
          url = `/api/jobs/${jobId}/transcript?format=json`
          downloadFilename = `${filename}.json`
          break
        case 'srt':
          url = `/api/files/${jobId}/subtitles?format=srt`
          downloadFilename = `${filename}.srt`
          break
        case 'vtt':
          url = `/api/files/${jobId}/subtitles?format=vtt`
          downloadFilename = `${filename}.vtt`
          break
        case 'txt':
          url = `/api/jobs/${jobId}/transcript?format=text`
          downloadFilename = `${filename}.txt`
          break
        default:
          throw new Error(`Unsupported format: ${format}`)
      }
      
      const response = await fetch(url)
      if (!response.ok) throw new Error('Export failed')
      
      const blob = await response.blob()
      const downloadUrl = URL.createObjectURL(blob)
      
      const a = document.createElement('a')
      a.href = downloadUrl
      a.download = downloadFilename
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      URL.revokeObjectURL(downloadUrl)
      
      toast.success(`Exported as ${format.toUpperCase()}`)
      setIsOpen(false)
    } catch (error) {
      toast.error('Export failed')
      console.error('Export error:', error)
    } finally {
      setExporting(null)
    }
  }
  
  return (
    <div className="relative" ref={menuRef}>
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="px-4 py-2 bg-olive-600 hover:bg-olive-700 text-white font-medium rounded-lg transition-colors flex items-center gap-2"
      >
        <Download className="w-4 h-4" />
        Export
        <ChevronDown className={`w-4 h-4 transition-transform ${isOpen ? 'rotate-180' : ''}`} />
      </button>
      
      {isOpen && (
        <div className="absolute right-0 mt-2 w-56 bg-white dark:bg-dark-200 rounded-xl shadow-lg border border-cream-200 dark:border-dark-50 overflow-hidden z-50 animate-fade-in">
          <div className="py-1">
            {EXPORT_OPTIONS.map(({ format, label, icon: Icon }) => (
              <button
                key={format}
                onClick={() => handleExport(format)}
                disabled={exporting !== null}
                className="w-full px-4 py-2.5 text-left hover:bg-cream-100 dark:hover:bg-dark-100 transition-colors flex items-center gap-3 disabled:opacity-50"
              >
                <Icon className="w-4 h-4 text-surface-500" />
                <span className="text-surface-800 dark:text-surface-200">{label}</span>
                {exporting === format && (
                  <span className="ml-auto text-xs text-olive-600">Exporting...</span>
                )}
              </button>
            ))}
          </div>
          
          <div className="border-t border-cream-200 dark:border-dark-50 py-1">
            <div className="px-4 py-2 text-xs text-surface-500">
              PDF and DOCX exports coming soon
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
