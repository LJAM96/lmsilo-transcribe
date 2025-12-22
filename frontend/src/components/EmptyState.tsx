import { type ReactNode } from 'react'
import { FileAudio, Layers, Bell, Search, Upload, Inbox } from 'lucide-react'

interface EmptyStateProps {
  type?: 'jobs' | 'models' | 'transcript' | 'search' | 'upload' | 'generic'
  title?: string
  description?: string
  action?: ReactNode
  className?: string
}

const PRESETS = {
  jobs: {
    icon: FileAudio,
    title: 'No jobs yet',
    description: 'Upload an audio or video file to start transcribing',
  },
  models: {
    icon: Layers,
    title: 'No models registered',
    description: 'Add your first model to get started with transcription',
  },
  transcript: {
    icon: Bell,
    title: 'Transcript will appear here',
    description: 'Processing will start once your file is uploaded',
  },
  search: {
    icon: Search,
    title: 'No results found',
    description: 'Try adjusting your search terms',
  },
  upload: {
    icon: Upload,
    title: 'Ready to transcribe',
    description: 'Drag and drop your files here or click to browse',
  },
  generic: {
    icon: Inbox,
    title: 'Nothing here yet',
    description: 'This section is empty',
  },
}

export default function EmptyState({ 
  type = 'generic', 
  title, 
  description, 
  action,
  className = ''
}: EmptyStateProps) {
  const preset = PRESETS[type]
  const Icon = preset.icon
  
  return (
    <div className={`flex flex-col items-center justify-center py-12 px-4 text-center ${className}`}>
      {/* Icon container with subtle animation */}
      <div className="relative">
        <div className="absolute inset-0 bg-olive-200 dark:bg-olive-900/30 rounded-full blur-xl opacity-50" />
        <div className="relative w-20 h-20 bg-cream-200 dark:bg-dark-100 rounded-2xl flex items-center justify-center mb-6">
          <Icon className="w-10 h-10 text-surface-400" />
        </div>
      </div>
      
      {/* Text content */}
      <h3 className="text-lg font-medium text-surface-700 dark:text-surface-300">
        {title || preset.title}
      </h3>
      <p className="mt-2 text-sm text-surface-500 max-w-sm">
        {description || preset.description}
      </p>
      
      {/* Action button */}
      {action && (
        <div className="mt-6">
          {action}
        </div>
      )}
    </div>
  )
}

// Animated illustration for more visual interest
export function AnimatedEmptyState({ 
  type = 'jobs',
  title,
  description,
  action 
}: EmptyStateProps) {
  const preset = PRESETS[type]
  
  return (
    <div className="flex flex-col items-center justify-center py-16 px-4 text-center">
      {/* Floating animation */}
      <div className="relative animate-float">
        {/* Background circles */}
        <div className="absolute -inset-4 bg-olive-100 dark:bg-olive-900/20 rounded-full blur-2xl opacity-30" />
        <div className="absolute -inset-2 bg-cream-200 dark:bg-dark-100 rounded-full" />
        
        {/* Main icon */}
        <div className="relative w-24 h-24 bg-gradient-to-br from-cream-100 to-cream-200 dark:from-dark-100 dark:to-dark-50 rounded-2xl flex items-center justify-center shadow-lg">
          <preset.icon className="w-12 h-12 text-olive-500 dark:text-olive-400" />
        </div>
        
        {/* Decorative dots */}
        <div className="absolute -top-2 -right-2 w-4 h-4 bg-olive-300 dark:bg-olive-700 rounded-full animate-pulse" />
        <div className="absolute -bottom-1 -left-1 w-3 h-3 bg-cream-300 dark:bg-dark-50 rounded-full" />
      </div>
      
      {/* Text */}
      <h3 className="mt-8 text-xl font-serif text-surface-800 dark:text-surface-200">
        {title || preset.title}
      </h3>
      <p className="mt-2 text-surface-500 max-w-md">
        {description || preset.description}
      </p>
      
      {/* Action */}
      {action && (
        <div className="mt-8">
          {action}
        </div>
      )}
    </div>
  )
}
