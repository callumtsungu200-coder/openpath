import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { BadgeCheck, Bookmark, CalendarClock, Clock, ExternalLink, MapPin, UserRound } from 'lucide-react'
import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { api } from '@/lib/api'
import { useAuth } from '@/lib/auth'
import { ARRANGEMENT, CATEGORY, formatAge, formatSalary } from '@/lib/labels'
import type { Opportunity } from '@/lib/types'
import { applyLabel, cn, daysUntil, formatDate, formatShortDate, safeUrl } from '@/lib/utils'
import { Badge } from './ui/badge'
import { Button } from './ui/button'
import { Skeleton } from './ui/states'

export function CompanyLogo({ name, src, size = 'md' }: { name: string; src?: string | null; size?: 'md' | 'lg' }) {
  const [failed, setFailed] = useState(false)
  const classes = cn('grid shrink-0 place-items-center overflow-hidden rounded-full border border-border bg-surface-raised font-semibold text-foreground', size === 'lg' ? 'size-16 text-xl' : 'size-12 text-sm')
  if (src && !failed) {
    return <span className={cn(classes, 'bg-white')}><img src={src} alt="" loading="lazy" className="size-full object-contain p-1.5" onError={() => setFailed(true)} /></span>
  }
  const initials = name.split(/\s+/).slice(0, 2).map((w) => w[0]).join('').toUpperCase()
  return <span aria-hidden className={classes}>{initials}</span>
}

export function useSaved() {
  const { user } = useAuth()
  const client = useQueryClient()
  const navigate = useNavigate()
  const ids = useQuery({ queryKey: ['saved-ids', user?.id], queryFn: api.savedIds, enabled: Boolean(user) })
  const mutation = useMutation({
    mutationFn: api.toggleSaved,
    onSuccess: () => {
      client.invalidateQueries({ queryKey: ['saved-ids'] })
      client.invalidateQueries({ queryKey: ['saved'] })
    },
  })
  return {
    isSaved: (id: string) => Boolean(ids.data?.includes(id)),
    toggle: (id: string) => (user ? mutation.mutate(id) : navigate('/sign-in', { state: { message: 'Sign in to save opportunities.' } })),
  }
}

export function SaveButton({ id, className }: { id: string; className?: string }) {
  const { isSaved, toggle } = useSaved()
  const saved = isSaved(id)
  return (
    <Button
      variant="outline"
      size="icon"
      aria-pressed={saved}
      aria-label={saved ? 'Remove from saved' : 'Save opportunity'}
      className={cn(saved && 'border-primary bg-primary text-primary-foreground hover:bg-primary/85', className)}
      onClick={(e) => { e.preventDefault(); toggle(id) }}
    >
      <Bookmark className={cn(saved && 'fill-current')} />
    </Button>
  )
}

export function VerifiedMark({ verified }: { verified: boolean }) {
  if (!verified) return null
  return <span title="Checked against the employer's own listing"><BadgeCheck aria-label="Verified" className="size-[18px] shrink-0 text-success" /></span>
}

function deadlineLabel(deadline: string | null) {
  if (!deadline) return { text: 'No deadline stated', urgent: false }
  const days = daysUntil(deadline)
  if (days >= 0 && days <= 7) return { text: days === 0 ? 'Closes today' : `Closes in ${days} day${days === 1 ? '' : 's'}`, urgent: true }
  return { text: `Closes ${formatDate(deadline)}`, urgent: false }
}

export function OpportunityCard({ opportunity: o }: { opportunity: Opportunity }) {
  const facts = [CATEGORY[o.category].label, o.arrangement && ARRANGEMENT[o.arrangement], o.industry].filter(Boolean)
  const deadline = deadlineLabel(o.deadline)
  const salary = formatSalary(o)
  const age = formatAge(o)
  const applyUrl = safeUrl(o.apply_url, o.source_url)
  return (
    <article className="group relative flex h-full flex-col rounded-2xl border border-border bg-surface p-5 shadow-card transition-colors duration-150 hover:border-accent/50 hover:bg-surface-raised/60 sm:p-6">
      <div className="flex items-center gap-3">
        <CompanyLogo name={o.company_name} src={o.company_logo_url} />
        <Badge title="Date OpenPath first found this">Found {formatShortDate(o.discovered_at)}</Badge>
        <SaveButton id={o.id} className="relative z-10 ml-auto" />
      </div>
      <div className="mt-5 flex items-center gap-2 text-[15px] font-medium">
        <span className="truncate">{o.company_name}</span>
        <VerifiedMark verified={o.verification === 'verified'} />
      </div>
      <h3 className="mt-1.5 text-xl font-semibold leading-snug tracking-tight">
        <Link to={`/opportunities/${o.id}`} className="after:absolute after:inset-0 after:rounded-2xl focus-visible:after:ring-2 focus-visible:after:ring-ring">{o.title}</Link>
      </h3>
      <p className="mt-3 text-sm text-muted-foreground">{facts.join('  ·  ')}</p>
      <p className={cn('mt-1.5 text-sm', salary ? 'text-foreground' : 'text-subtle')}>{salary ?? 'Pay not stated'}</p>
      <div className="mt-auto flex items-end gap-3 pt-5">
        <dl className="min-w-0 flex-1 space-y-1.5 text-[13px] text-muted-foreground">
          <div className="flex min-w-0 items-center gap-1.5"><dt className="sr-only">Location</dt><MapPin aria-hidden className="size-3.5 shrink-0" /><dd className="truncate">{o.location ?? 'UK'}</dd></div>
          <div className={cn('flex items-center gap-1.5', deadline.urgent && 'text-warning')}><dt className="sr-only">Deadline</dt>{deadline.urgent ? <CalendarClock aria-hidden className="size-3.5 shrink-0" /> : <Clock aria-hidden className="size-3.5 shrink-0" />}<dd>{deadline.text}</dd></div>
          {age && <div className="flex items-center gap-1.5"><dt className="sr-only">Age eligibility</dt><UserRound aria-hidden className="size-3.5 shrink-0" /><dd>{age}</dd></div>}
        </dl>
        <div className="flex shrink-0 items-center gap-2">
          {applyUrl && (
            <a href={applyUrl} target="_blank" rel="noopener noreferrer nofollow" aria-label={`${applyLabel(applyUrl)}: ${o.title}, opens in a new tab`} title={applyLabel(applyUrl)}
              className="relative z-10 grid size-11 place-items-center rounded-full border border-input text-foreground transition-colors hover:bg-surface-raised">
              <ExternalLink className="size-4" />
            </a>
          )}
          <span aria-hidden className="inline-flex h-11 items-center rounded-full bg-primary px-4 text-[13px] font-medium text-primary-foreground transition-colors group-hover:bg-primary/85">Details</span>
        </div>
      </div>
    </article>
  )
}

export function OpportunityCardSkeleton() {
  return (
    <div aria-hidden className="rounded-2xl border border-border bg-surface p-6">
      <div className="flex items-center gap-3"><Skeleton className="size-12 rounded-full" /><Skeleton className="h-7 w-28 rounded-full" /></div>
      <Skeleton className="mt-6 h-4 w-24" />
      <Skeleton className="mt-3 h-6 w-4/5" />
      <Skeleton className="mt-4 h-4 w-3/5" />
      <Skeleton className="mt-8 h-4 w-full" />
    </div>
  )
}

export function CardGrid({ children, className }: { children: React.ReactNode; className?: string }) {
  return <div className={cn('grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3 lg:gap-5', className)}>{children}</div>
}
