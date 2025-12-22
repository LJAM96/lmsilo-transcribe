interface ToggleProps {
  checked: boolean
  onChange: (checked: boolean) => void
  disabled?: boolean
  size?: 'sm' | 'md' | 'lg'
}

export default function Toggle({ 
  checked, 
  onChange, 
  disabled = false,
  size = 'md' 
}: ToggleProps) {
  const sizes = {
    sm: { track: 'w-8 h-4', thumb: 'w-3 h-3', translate: 'translate-x-4' },
    md: { track: 'w-11 h-6', thumb: 'w-5 h-5', translate: 'translate-x-5' },
    lg: { track: 'w-14 h-7', thumb: 'w-6 h-6', translate: 'translate-x-7' },
  }
  
  const s = sizes[size]
  
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      disabled={disabled}
      onClick={() => !disabled && onChange(!checked)}
      className={`
        relative inline-flex shrink-0 cursor-pointer rounded-full 
        border-2 border-transparent transition-colors duration-200 ease-in-out
        focus:outline-none focus:ring-2 focus:ring-olive-400 focus:ring-offset-2
        dark:focus:ring-offset-dark-300
        ${s.track}
        ${checked 
          ? 'bg-olive-600' 
          : 'bg-cream-300 dark:bg-dark-50'
        }
        ${disabled ? 'opacity-50 cursor-not-allowed' : ''}
      `}
    >
      <span className="sr-only">Toggle</span>
      <span
        className={`
          pointer-events-none inline-block rounded-full 
          bg-white shadow-lg ring-0 transition-transform duration-200 ease-in-out
          ${s.thumb}
          ${checked ? s.translate : 'translate-x-0'}
        `}
      />
    </button>
  )
}
