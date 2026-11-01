import { ChevronsUpDown } from 'lucide-react'
import { forwardRef, type InputHTMLAttributes, type SelectHTMLAttributes } from 'react'
import { cn } from '@/lib/utils'

const fieldClass =
  'h-12 w-full rounded-xl border border-input bg-surface-raised/50 px-4 text-[15px] text-foreground transition-colors placeholder:text-subtle hover:border-subtle/50 focus-visible:border-ring disabled:opacity-50 sm:text-sm'

export const Input = forwardRef<HTMLInputElement, InputHTMLAttributes<HTMLInputElement>>(({ className, ...props }, ref) => (
  <input ref={ref} className={cn(fieldClass, className)} {...props} />
))
Input.displayName = 'Input'

export const Select = forwardRef<HTMLSelectElement, SelectHTMLAttributes<HTMLSelectElement>>(({ className, children, ...props }, ref) => (
  <div className="relative">
    <select ref={ref} className={cn(fieldClass, 'cursor-pointer appearance-none pr-10', className)} {...props}>
      {children}
    </select>
    <ChevronsUpDown aria-hidden className="pointer-events-none absolute right-3.5 top-1/2 size-4 -translate-y-1/2 text-subtle" />
  </div>
))
Select.displayName = 'Select'

export function Label({ className, ...props }: React.LabelHTMLAttributes<HTMLLabelElement>) {
  return <label className={cn('mb-2 block text-sm font-medium text-foreground', className)} {...props} />
}
