import { useQuery } from '@tanstack/react-query'
import { ArrowRight, Radar, Sparkles } from 'lucide-react'
import { Link, useNavigate } from 'react-router-dom'
import { CardGrid, OpportunityCard, OpportunityCardSkeleton } from '@/components/OpportunityCard'
import { SearchPanel, type PanelValues } from '@/components/SearchPanel'
import { Card, CardTitle } from '@/components/ui/card'
import { EmptyState, ErrorState, Skeleton } from '@/components/ui/states'
import { api } from '@/lib/api'
import { CATEGORY, SHORTCUT_CATEGORIES } from '@/lib/labels'
import { isConfigured } from '@/lib/supabase'
import { formatCount, timeAgo } from '@/lib/utils'

const SUGGESTED_SEARCHES = ['Software apprenticeship', 'Summer internship', 'Graduate scheme London', 'Virtual work experience', 'Year 10 work experience']

function SectionHeading({ title, to, action }: { title: string; to?: string; action?: string }) {
  return (
    <div className="mb-4 flex items-center justify-between gap-4">
      <h2 className="text-xl font-semibold tracking-tight sm:text-2xl">{title}</h2>
      {to && <Link to={to} className="inline-flex min-h-11 items-center gap-1.5 text-sm font-medium transition-colors hover:text-accent">{action}<ArrowRight className="size-4" /></Link>}
    </div>
  )
}

export function HomePage() {
  const navigate = useNavigate()
  const { data, isLoading, error, refetch } = useQuery({ queryKey: ['home'], queryFn: api.home, enabled: isConfigured })
  const go = (v: Partial<PanelValues>) => {
    const params = new URLSearchParams(Object.entries(v).filter(([, value]) => value) as [string, string][])
    navigate(`/search${params.size ? `?${params}` : ''}`)
  }
  const counts = new Map(data?.categories.map((c) => [c.category, c.count]))

  return (
    <div className="space-y-10 lg:space-y-14">
      <section>
        <h1 className="max-w-4xl text-4xl font-light leading-[1.1] tracking-tight sm:text-5xl lg:text-6xl">
          Every UK opportunity, found at the source.
        </h1>
        {data && (
          <p className="mt-4 flex flex-wrap gap-x-6 gap-y-1 text-sm text-muted-foreground sm:text-base">
            <span>{formatCount(data.stats.active)} live opportunities</span>
            <span>{formatCount(data.stats.companies)} employers</span>
            {data.stats.last_scan_at && <span>Last scan {timeAgo(data.stats.last_scan_at)}</span>}
          </p>
        )}
        <div className="mt-7">
          <SearchPanel onSubmit={go} />
          <div className="mt-3 flex gap-2 overflow-x-auto pb-1 [scrollbar-width:none] sm:flex-wrap">
            {SUGGESTED_SEARCHES.map((s) => (
              <button key={s} onClick={() => go({ q: s })} className="min-h-9 shrink-0 rounded-full bg-white/60 px-3.5 text-[13px] font-medium transition-all duration-200 ease-ios active:scale-95 hover:bg-white">
                {s}
              </button>
            ))}
          </div>
        </div>
      </section>

      <section aria-label="Browse by category">
        <div className="-mx-4 grid auto-cols-[9.5rem] grid-flow-col gap-3 overflow-x-auto px-4 pb-1 [scrollbar-width:none] sm:mx-0 sm:auto-cols-auto sm:grid-flow-row sm:grid-cols-4 sm:px-0 xl:grid-cols-8">
          {SHORTCUT_CATEGORIES.map((c) => {
            const { plural, icon: Icon } = CATEGORY[c]
            return (
              <Link key={c} to={`/search?category=${c}`} className="rounded-2xl bg-surface p-4 shadow-card transition-all duration-200 ease-ios active:scale-[0.97] hover:bg-primary hover:text-primary-foreground">
                <Icon aria-hidden className="size-5" />
                <div className="mt-3 text-sm font-medium leading-tight">{plural}</div>
                <div className="mt-1 text-xs opacity-70">{data ? formatCount(counts.get(c) ?? 0) : ' '}</div>
              </Link>
            )
          })}
        </div>
      </section>

      {!isConfigured && (
        <EmptyState icon={Radar} title="No database connected">
          Set VITE_SUPABASE_URL and VITE_SUPABASE_ANON_KEY to connect OpenPath to its database. Nothing is shown until real scans have run.
        </EmptyState>
      )}
      {error && <ErrorState error={error} onRetry={() => refetch()} />}

      {isLoading && (
        <section>
          <Skeleton className="mb-4 h-8 w-64" />
          <CardGrid>{Array.from({ length: 3 }, (_, i) => <OpportunityCardSkeleton key={i} />)}</CardGrid>
        </section>
      )}

      {data && data.stats.active === 0 && (
        <EmptyState icon={Radar} title="No opportunities yet">
          {data.stats.sources_monitored > 0
            ? `${data.stats.sources_monitored} sites are set up for monitoring. Opportunities appear here once a scan has found them.`
            : 'No sites have been added for monitoring yet.'}
        </EmptyState>
      )}

      {data && data.stats.active > 0 && (
        <>
          {data.featured.length > 0 && (
            <section>
              <SectionHeading title="Featured early-career opportunities" to="/search?early=1" action="See all" />
              <CardGrid>{data.featured.map((o) => <OpportunityCard key={o.id} opportunity={o} />)}</CardGrid>
            </section>
          )}
          <section>
            <SectionHeading title="Recently discovered" to="/search?sort=newest" action="See all" />
            <CardGrid>{data.recent.map((o) => <OpportunityCard key={o.id} opportunity={o} />)}</CardGrid>
          </section>
          <section className="grid gap-5 lg:grid-cols-2">
            <Card>
              <CardTitle className="mb-4">Popular industries</CardTitle>
              <ul className="-my-1">
                {data.industries.map((i) => (
                  <li key={i.industry}>
                    <Link to={`/search?industry=${encodeURIComponent(i.industry)}`} className="flex min-h-11 items-center justify-between gap-4 border-b border-border/60 text-sm transition-colors last:border-0 hover:text-accent">
                      {i.industry}<span className="text-muted-foreground">{formatCount(i.count)}</span>
                    </Link>
                  </li>
                ))}
              </ul>
            </Card>
            <Card>
              <CardTitle className="mb-4">Latest updates</CardTitle>
              <ul className="space-y-1">
                {data.updates.map((u) => (
                  <li key={u.id}>
                    <Link to={`/opportunities/${u.opportunity_id}`} className="flex gap-3 rounded-lg py-2 text-sm transition-colors hover:text-accent">
                      <Sparkles aria-hidden className="mt-0.5 size-4 shrink-0 text-subtle" />
                      <span className="min-w-0 flex-1">
                        <span className="font-medium">{u.title}</span>
                        <span className="text-muted-foreground"> at {u.company_name}. {u.kind === 'discovered' ? 'Newly found' : u.detail ?? 'Updated'}, {timeAgo(u.created_at)}.</span>
                      </span>
                    </Link>
                  </li>
                ))}
              </ul>
            </Card>
          </section>
        </>
      )}
    </div>
  )
}
