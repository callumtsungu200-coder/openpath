import { AlertTriangle, type LucideIcon } from 'lucide-react'
import type { ReactNode } from 'react'
import { cn } from '@/lib/utils'
import { Button } from './button'

export function Skeleton({ className }: { className?: string }) {
  return <div aria-hidden className={cn('animate-pulse rounded-lg bg-surface-raised/70', className)} />
}

export function EmptyState({ icon: Icon, title, children, action, className }: { icon: LucideIcon; title: string; children?: ReactNode; action?: ReactNode; className?: string }) {
  return (
    <div className={cn('flex flex-col items-center rounded-3xl bg-surface px-6 py-14 shadow-card text-center', className)}>
      <div className="mb-4 grid size-12 place-items-center rounded-xl bg-surface-raised text-muted-foreground"><Icon className="size-5" /></div>
      <h3 className="font-semibold">{title}</h3>
      {children && <p className="mt-1.5 max-w-md text-sm text-muted-foreground">{children}</p>}
      {action && <div className="mt-5">{action}</div>}
    </div>
  )
}

export function ErrorState({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  return (
    <EmptyState
      icon={AlertTriangle}
      title="Something went wrong"
      action={onRetry && <Button variant="secondary" size="sm" onClick={onRetry}>Try again</Button>}
    >
      {error instanceof Error ? error.message : 'The request could not be completed.'}
    </EmptyState>
  )
}
