import { cn } from '@/lib/utils'

/** iOS-style segmented control. */
export function Segmented({ label, options, value, onChange, className }: { label: string; options: { value: string; label: string }[]; value: string; onChange: (value: string) => void; className?: string }) {
  return (
    <div role="radiogroup" aria-label={label} className={cn('flex rounded-xl bg-surface-raised p-0.5', className)}>
      {options.map((o) => (
        <button
          key={o.value}
          type="button"
          role="radio"
          aria-checked={o.value === value}
          onClick={() => onChange(o.value)}
          className={cn('min-h-10 flex-1 rounded-[0.65rem] px-2 text-[13px] font-medium transition-all duration-200 ease-ios', o.value === value ? 'bg-surface text-foreground shadow-card' : 'text-muted-foreground')}
        >
          {o.label}
        </button>
      ))}
    </div>
  )
}
