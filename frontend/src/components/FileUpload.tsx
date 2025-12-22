import { useCallback, useState } from 'react'
import { useDropzone } from 'react-dropzone'
import { Upload, FileAudio, FileVideo, X, Loader2, CheckCircle2, AlertCircle, Play } from 'lucide-react'
import { useMutation } from '@tanstack/react-query'
import toast from 'react-hot-toast'
import { api } from '../lib/api'
import type { TranscriptionOptions } from '../pages/Dashboard'

interface FileUploadProps {
  options: TranscriptionOptions
  onUploadComplete: () => void
}

interface UploadFile {
  id: string
  file: File
  progress: number
  status: 'pending' | 'uploading' | 'complete' | 'error'
  error?: string
}

export default function FileUpload({ options, onUploadComplete }: FileUploadProps) {
  const [files, setFiles] = useState<UploadFile[]>([])
  const [isUploading, setIsUploading] = useState(false)
  const [batchMode, setBatchMode] = useState(true) // Default to batch for many files
  const [batchName, setBatchName] = useState('')
  
  const uploadMutation = useMutation({
    mutationFn: async (file: File) => {
      const formData = new FormData()
      formData.append('file', file)
      formData.append('language', options.language)
      formData.append('enable_diarization', String(options.enableDiarization))
      formData.append('enable_tts', String(options.enableTts))
      formData.append('sync_tts_timing', String(options.syncTtsTiming))
      formData.append('output_formats', options.outputFormats.join(','))
      formData.append('priority', String(options.priority))
      
      if (options.modelId) {
        formData.append('model_id', options.modelId)
      }
      if (options.diarizationModelId) {
        formData.append('diarization_model_id', options.diarizationModelId)
      }
      if (options.ttsModelId) {
        formData.append('tts_model_id', options.ttsModelId)
      }
      
      return api.createJob(formData)
    },
  })
  
  const uploadAsBatch = useCallback(async () => {
    const pendingFiles = files.filter(f => f.status === 'pending')
    if (pendingFiles.length < 2) return
    
    setIsUploading(true)
    
    try {
      const formData = new FormData()
      for (const uploadFile of pendingFiles) {
        formData.append('files', uploadFile.file)
      }
      if (batchName) {
        formData.append('batch_name', batchName)
      }
      formData.append('language', options.language)
      formData.append('enable_diarization', String(options.enableDiarization))
      formData.append('enable_tts', String(options.enableTts))
      
      const response = await fetch('/api/batches', {
        method: 'POST',
        body: formData,
      })
      
      if (!response.ok) {
        throw new Error('Batch upload failed')
      }
      
      const result = await response.json()
      
      // Mark all files as complete
      setFiles(prev => prev.map(f => 
        f.status === 'pending' ? { ...f, status: 'complete' as const, progress: 100 } : f
      ))
      
      toast.success(`Batch "${result.name}" created with ${result.total_files} files`)
      onUploadComplete()
      setBatchName('')
    } catch (error) {
      toast.error(`Batch upload failed: ${error}`)
    }
    
    setIsUploading(false)
  }, [files, batchName, options, onUploadComplete])
  
  const uploadAll = useCallback(async () => {
    const pendingFiles = files.filter(f => f.status === 'pending')
    if (pendingFiles.length === 0) return
    
    setIsUploading(true)
    
    for (const uploadFile of pendingFiles) {
      // Update status to uploading
      setFiles(prev => prev.map(f => 
        f.id === uploadFile.id ? { ...f, status: 'uploading' as const } : f
      ))
      
      try {
        await uploadMutation.mutateAsync(uploadFile.file)
        
        // Update status to complete
        setFiles(prev => prev.map(f =>
          f.id === uploadFile.id ? { ...f, status: 'complete' as const, progress: 100 } : f
        ))
        
        toast.success(`${uploadFile.file.name} added to queue`)
        onUploadComplete()
      } catch (error) {
        // Update status to error
        setFiles(prev => prev.map(f =>
          f.id === uploadFile.id ? { ...f, status: 'error' as const, error: String(error) } : f
        ))
        toast.error(`Failed to upload ${uploadFile.file.name}`)
      }
    }
    
    setIsUploading(false)
  }, [files, uploadMutation, onUploadComplete])
  
  const onDrop = useCallback((acceptedFiles: File[]) => {
    const newFiles: UploadFile[] = acceptedFiles.map(file => ({
      id: `${file.name}-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
      file,
      progress: 0,
      status: 'pending' as const,
    }))
    
    setFiles(prev => [...prev, ...newFiles])
  }, [])
  
  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'audio/*': ['.mp3', '.wav', '.ogg', '.flac', '.m4a', '.aac', '.oga'],
      'video/*': ['.mp4', '.webm', '.mkv', '.mov', '.avi'],
    },
    maxSize: 500 * 1024 * 1024, // 500MB
    multiple: true,
  })
  
  const removeFile = (id: string) => {
    setFiles(prev => prev.filter(f => f.id !== id))
  }
  
  const clearCompleted = () => {
    setFiles(prev => prev.filter(f => f.status !== 'complete'))
  }
  
  const pendingFiles = files.filter(f => f.status === 'pending')
  const uploadingFiles = files.filter(f => f.status === 'uploading')
  const completedFiles = files.filter(f => f.status === 'complete')
  const errorFiles = files.filter(f => f.status === 'error')
  
  const totalSize = files.reduce((acc, f) => acc + f.file.size, 0)
  const pendingSize = pendingFiles.reduce((acc, f) => acc + f.file.size, 0)
  
  return (
    <div className="space-y-4">
      {/* Dropzone */}
      <div
        {...getRootProps()}
        className={`upload-zone ${isDragActive ? 'active' : ''}`}
      >
        <input {...getInputProps()} />
        <div className="w-16 h-16 bg-olive-100 dark:bg-olive-900/30 rounded-2xl flex items-center justify-center">
          <Upload className="w-8 h-8 text-olive-600 dark:text-olive-400" />
        </div>
        <div className="text-center">
          <p className="text-surface-700 dark:text-surface-300 font-medium">
            {isDragActive ? 'Drop files here' : 'Drag & drop media files'}
          </p>
          <p className="text-sm text-surface-500 mt-1">
            or click to browse • MP3, WAV, MP4, MKV up to 500MB each
          </p>
        </div>
      </div>
      
      {/* Batch Summary & Upload Button */}
      {pendingFiles.length > 0 && (
        <div className="space-y-3 p-4 bg-olive-50 dark:bg-olive-900/20 rounded-xl border border-olive-200 dark:border-olive-800">
          <div className="flex items-center justify-between">
            <div>
              <p className="font-medium text-olive-800 dark:text-olive-300">
                {pendingFiles.length} file{pendingFiles.length !== 1 ? 's' : ''} ready to upload
              </p>
              <p className="text-sm text-olive-600 dark:text-olive-400">
                Total: {formatFileSize(pendingSize)}
              </p>
            </div>
            
            {/* Batch Mode Toggle - show when 5+ files */}
            {pendingFiles.length >= 5 && (
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={batchMode}
                  onChange={(e) => setBatchMode(e.target.checked)}
                  className="w-4 h-4 rounded border-olive-300 text-olive-600 focus:ring-olive-500"
                />
                <span className="text-sm font-medium text-olive-700 dark:text-olive-300">
                  Create as batch
                </span>
              </label>
            )}
          </div>
          
          {/* Batch Name Input */}
          {batchMode && pendingFiles.length >= 5 && (
            <input
              type="text"
              value={batchName}
              onChange={(e) => setBatchName(e.target.value)}
              placeholder="Batch name (optional)"
              className="w-full px-3 py-2 rounded-lg bg-white dark:bg-dark-100 border border-olive-200 dark:border-olive-700 text-sm"
            />
          )}
          
          <div className="flex justify-end">
            <button
              onClick={batchMode && pendingFiles.length >= 5 ? uploadAsBatch : uploadAll}
              disabled={isUploading}
              className="btn-primary flex items-center gap-2"
            >
              {isUploading ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  Uploading...
                </>
              ) : (
                <>
                  <Play className="w-4 h-4" />
                  {batchMode && pendingFiles.length >= 5 ? 'Upload as Batch' : 'Upload All'}
                </>
              )}
            </button>
          </div>
        </div>
      )}
      
      {/* File List */}
      {files.length > 0 && (
        <div className="space-y-2">
          {/* Completed files header */}
          {completedFiles.length > 0 && (
            <div className="flex items-center justify-between text-sm text-surface-500 py-1">
              <span>{completedFiles.length} completed</span>
              <button
                onClick={clearCompleted}
                className="text-olive-600 hover:text-olive-700 dark:text-olive-400"
              >
                Clear completed
              </button>
            </div>
          )}
          
          {files.map((f) => (
            <div
              key={f.id}
              className={`flex items-center gap-3 p-3 rounded-xl transition-colors ${
                f.status === 'complete' 
                  ? 'bg-olive-50 dark:bg-olive-900/20' 
                  : f.status === 'error'
                  ? 'bg-red-50 dark:bg-red-900/20'
                  : 'bg-cream-50 dark:bg-dark-100'
              }`}
            >
              {/* Icon */}
              <div className={`w-10 h-10 rounded-lg flex items-center justify-center flex-shrink-0 ${
                f.status === 'complete' 
                  ? 'bg-olive-100 dark:bg-olive-900/30' 
                  : f.status === 'error'
                  ? 'bg-red-100 dark:bg-red-900/30'
                  : 'bg-cream-200 dark:bg-dark-50'
              }`}>
                {f.status === 'complete' ? (
                  <CheckCircle2 className="w-5 h-5 text-olive-600 dark:text-olive-400" />
                ) : f.status === 'error' ? (
                  <AlertCircle className="w-5 h-5 text-red-600 dark:text-red-400" />
                ) : f.file.type.startsWith('video/') ? (
                  <FileVideo className="w-5 h-5 text-surface-600" />
                ) : (
                  <FileAudio className="w-5 h-5 text-surface-600" />
                )}
              </div>
              
              {/* Info */}
              <div className="flex-1 min-w-0">
                <p className={`text-sm font-medium truncate ${
                  f.status === 'error' ? 'text-red-800 dark:text-red-300' : 'text-surface-800 dark:text-surface-200'
                }`}>
                  {f.file.name}
                </p>
                <p className="text-xs text-surface-500">
                  {formatFileSize(f.file.size)}
                  {f.status === 'error' && f.error && (
                    <span className="text-red-600 dark:text-red-400 ml-2">{f.error}</span>
                  )}
                </p>
                
                {/* Progress bar for uploading */}
                {f.status === 'uploading' && (
                  <div className="progress mt-2">
                    <div className="progress-bar animate-pulse" style={{ width: '60%' }} />
                  </div>
                )}
              </div>
              
              {/* Status */}
              <div className="flex-shrink-0">
                {f.status === 'uploading' && (
                  <Loader2 className="w-5 h-5 text-olive-600 dark:text-olive-400 animate-spin" />
                )}
                {f.status === 'complete' && (
                  <span className="text-xs font-medium text-olive-600 dark:text-olive-400">Queued</span>
                )}
                {(f.status === 'pending' || f.status === 'error') && (
                  <button
                    onClick={(e) => {
                      e.stopPropagation()
                      removeFile(f.id)
                    }}
                    className="p-1.5 hover:bg-cream-200 dark:hover:bg-dark-50 rounded-lg transition-colors"
                  >
                    <X className="w-4 h-4 text-surface-500" />
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}
