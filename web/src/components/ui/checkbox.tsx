import * as CheckboxPrimitive from '@radix-ui/react-checkbox'
import { Check } from 'lucide-react'
import type { ComponentPropsWithoutRef } from 'react'
import { cn } from '@/lib/utils'

export function Checkbox({ className, ...props }: ComponentPropsWithoutRef<typeof CheckboxPrimitive.Root>) {
  return (
    <CheckboxPrimitive.Root
      className={cn('grid size-5 shrink-0 place-items-center rounded-md border border-input bg-surface-raised/50 transition-colors data-[state=checked]:border-accent data-[state=checked]:bg-accent data-[state=checked]:text-accent-foreground', className)}
      {...props}
    >
      <CheckboxPrimitive.Indicator><Check className="size-3.5" strokeWidth={3} /></CheckboxPrimitive.Indicator>
    </CheckboxPrimitive.Root>
  )
}
