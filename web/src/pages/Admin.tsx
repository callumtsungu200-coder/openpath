import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Activity, Bot, CheckCircle2, Copy, Database, ExternalLink, Hourglass, Inbox, Lock, Radar, RefreshCw, Server, TriangleAlert, XCircle } from 'lucide-react'
import { useState, type ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardTitle } from '@/components/ui/card'
import { EmptyState, ErrorState, Skeleton } from '@/components/ui/states'
import { Table, Td, Th } from '@/components/ui/table'
import { api } from '@/lib/api'
import { useAuth } from '@/lib/auth'
import { CATEGORY } from '@/lib/labels'
import type { AdminOverview, ScanStatus } from '@/lib/types'
import { cn, formatCount, formatDate, formatDateTime, timeAgo } from '@/lib/utils'

const TABS = ['Overview', 'Sources', 'Scans', 'Review', 'Duplicates', 'Closed', 'AI', 'Health'] as const
type Tab = (typeof TABS)[number]
const HEARTBEAT_STALE_MINUTES = 10

const STATUS: Record<ScanStatus, { variant: 'success' | 'warning' | 'danger' | 'accent'; label: string; icon: typeof CheckCircle2 }> = {
  success: { variant: 'success', label: 'Success', icon: CheckCircle2 },
  partial: { variant: 'warning', label: 'Partial', icon: TriangleAlert },
  failed: { variant: 'danger', label: 'Failed', icon: XCircle },
  running: { variant: 'accent', label: 'Running', icon: RefreshCw },
}

function StatusBadge({ status }: { status: ScanStatus | null }) {
  if (!status) return <Badge>Never scanned</Badge>
  const { variant, label, icon: Icon } = STATUS[status]
  return <Badge variant={variant}><Icon />{label}</Badge>
}

function Stat({ label, value, icon: Icon, tone, onClick }: { label: string; value: number; icon: typeof Radar; tone?: 'danger' | 'warning'; onClick?: () => void }) {
  const urgent = tone && value > 0
  return (
    <button onClick={onClick} className="rounded-2xl border border-border bg-surface p-5 text-left transition-colors hover:border-accent/50 hover:bg-surface-raised/60">
      <div className="flex items-center gap-2 text-[13px] text-muted-foreground">
        <Icon aria-hidden className={cn('size-4', urgent && (tone === 'danger' ? 'text-danger' : 'text-warning'))} />{label}
      </div>
      <div className="mt-2 text-3xl font-semibold tracking-tight">{formatCount(value)}</div>
    </button>
  )
}

const SERIES = { success: 'hsl(214 85% 72%)', failed: 'hsl(2 75% 70%)', created: 'hsl(214 85% 72%)' }

function ChartTooltip({ active, payload, label }: { active?: boolean; payload?: { name: string; value: number; color: string }[]; label?: string }) {
  if (!active || !payload?.length) return null
  return (
    <div className="rounded-lg border border-border bg-surface-raised p-3 text-xs shadow-pop">
      <div className="mb-1.5 font-medium">{label && formatDate(label)}</div>
      {payload.map((p) => (
        <div key={p.name} className="flex items-center gap-2 text-muted-foreground">
          <span aria-hidden className="size-2 rounded-full" style={{ background: p.color }} />{p.name}<span className="ml-auto pl-4 font-medium text-foreground">{formatCount(p.value)}</span>
        </div>
      ))}
    </div>
  )
}

function DailyChart({ title, data, series, legend }: { title: string; data: AdminOverview['daily']; series: { key: 'success' | 'failed' | 'created'; name: string }[]; legend?: boolean }) {
  return (
    <Card>
      <CardTitle className="mb-1 text-base">{title}</CardTitle>
      {legend ? (
        <div className="mb-3 flex gap-4 text-xs text-muted-foreground">
          {series.map((s) => <span key={s.key} className="flex items-center gap-1.5"><span aria-hidden className="size-2.5 rounded-sm" style={{ background: SERIES[s.key] }} />{s.name}</span>)}
        </div>
      ) : <p className="mb-3 text-xs text-muted-foreground">Last 14 days</p>}
      <div className="h-52">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} margin={{ left: -24, right: 4, top: 4, bottom: 0 }} barCategoryGap="28%">
            <CartesianGrid vertical={false} stroke="hsl(var(--border))" strokeOpacity={0.6} />
            <XAxis dataKey="day" tickFormatter={(d: string) => new Date(d).toLocaleDateString('en-GB', { day: 'numeric', month: 'short' })} tick={{ fill: 'hsl(var(--subtle-foreground))', fontSize: 11 }} axisLine={false} tickLine={false} minTickGap={24} />
            <YAxis allowDecimals={false} tick={{ fill: 'hsl(var(--subtle-foreground))', fontSize: 11 }} axisLine={false} tickLine={false} />
            <Tooltip content={<ChartTooltip />} cursor={{ fill: 'hsl(var(--surface-raised))', fillOpacity: 0.5 }} />
            {series.map((s, i) => (
              <Bar key={s.key} dataKey={s.key} name={s.name} stackId="a" fill={SERIES[s.key]} stroke="hsl(var(--surface))" strokeWidth={series.length > 1 ? 2 : 0} radius={i === series.length - 1 ? [4, 4, 0, 0] : 0} isAnimationActive={false} />
            ))}
          </BarChart>
        </ResponsiveContainer>
      </div>
    </Card>
  )
}

function useAdminAction<T>(fn: (arg: T) => Promise<void>) {
  const client = useQueryClient()
  return useMutation({ mutationFn: fn, onSuccess: () => client.invalidateQueries({ queryKey: ['admin'] }) })
}

function Panel({ title, note, children }: { title: string; note?: ReactNode; children: ReactNode }) {
  return <Card><CardTitle className="text-base">{title}</CardTitle>{note && <p className="mt-1 text-sm text-muted-foreground">{note}</p>}<div className="mt-5">{children}</div></Card>
}

function SourcesTable({ sources }: { sources: AdminOverview['sources'] }) {
  const setEnabled = useAdminAction(({ id, enable }: { id: number; enable: boolean }) => api.admin.setSourceEnabled(id, enable))
  const requestScan = useAdminAction((id: number) => api.admin.requestScan(id))
  if (!sources.length) return <EmptyState icon={Radar} title="No sources yet">Add sources to worker/sources.yaml, then run: openpath sources sync</EmptyState>
  return (
    <Table>
      <thead><tr><Th>Source</Th><Th>Status</Th><Th>Last scan</Th><Th>Next scan</Th><Th className="text-right">Live</Th><Th className="text-right">Actions</Th></tr></thead>
      <tbody>
        {sources.map((s) => (
          <tr key={s.id} className={cn(!s.enabled && 'opacity-60')}>
            <Td><a href={s.url} target="_blank" rel="noopener noreferrer" className="font-medium hover:text-accent">{s.name}</a><div className="text-xs text-subtle">{s.adapter}</div></Td>
            <Td><StatusBadge status={s.last_status} />{s.last_error && <div className="mt-1.5 max-w-xs text-xs text-danger">{s.last_error}</div>}</Td>
            <Td className="whitespace-nowrap text-muted-foreground">{s.last_scan_at ? timeAgo(s.last_scan_at) : 'Never'}</Td>
            <Td className="whitespace-nowrap text-muted-foreground">{s.enabled ? formatDateTime(s.next_scan_at) : 'Paused'}</Td>
            <Td className="text-right">{formatCount(s.active_count)}</Td>
            <Td className="whitespace-nowrap text-right">
              <Button variant="ghost" size="sm" disabled={!s.enabled} onClick={() => requestScan.mutate(s.id)}>Scan next</Button>
              <Button variant="ghost" size="sm" onClick={() => setEnabled.mutate({ id: s.id, enable: !s.enabled })}>{s.enabled ? 'Pause' : 'Resume'}</Button>
            </Td>
          </tr>
        ))}
      </tbody>
    </Table>
  )
}

function ScansTable({ scans, failedOnly }: { scans: AdminOverview['scans']; failedOnly?: boolean }) {
  const rows = failedOnly ? scans.filter((s) => s.status === 'failed') : scans
  if (!rows.length) return <EmptyState icon={Activity} title={failedOnly ? 'No failed scans' : 'No scans yet'}>{failedOnly ? 'None of the recent scans failed.' : 'Scanner activity appears here once the worker has run.'}</EmptyState>
  return (
    <Table>
      <thead><tr><Th>Source</Th><Th>Status</Th><Th>Started</Th><Th className="text-right">Found</Th><Th className="text-right">Outside UK</Th><Th className="text-right">New</Th><Th className="text-right">Changed</Th><Th className="text-right">Removed</Th><Th className="text-right">AI</Th></tr></thead>
      <tbody>
        {rows.map((s) => (
          <tr key={s.id}>
            <Td className="font-medium">{s.source_name}{s.error && <div className="mt-1 max-w-sm text-xs font-normal text-danger">{s.error}</div>}</Td>
            <Td><StatusBadge status={s.status} /></Td>
            <Td className="whitespace-nowrap text-muted-foreground">{formatDateTime(s.started_at)}</Td>
            <Td className="text-right">{s.items_found}</Td><Td className="text-right text-muted-foreground">{s.items_outside_uk}</Td>
            <Td className="text-right">{s.items_created}</Td><Td className="text-right">{s.items_updated}</Td><Td className="text-right">{s.items_removed}</Td><Td className="text-right">{s.ai_calls}</Td>
          </tr>
        ))}
      </tbody>
    </Table>
  )
}

function ReviewTable({ pending }: { pending: AdminOverview['pending'] }) {
  const review = useAdminAction(({ id, approve }: { id: string; approve: boolean }) => api.admin.review(id, approve))
  if (!pending.length) return <EmptyState icon={CheckCircle2} title="Review queue is empty">Listings the system is unsure about wait here and stay hidden from the public.</EmptyState>
  return (
    <Table>
      <thead><tr><Th>Opportunity</Th><Th>Category</Th><Th>Confidence</Th><Th>Method</Th><Th className="text-right">Decision</Th></tr></thead>
      <tbody>
        {pending.map((p) => (
          <tr key={p.id}>
            <Td><a href={p.source_url} target="_blank" rel="noopener noreferrer" className="font-medium hover:text-accent">{p.title}<ExternalLink className="ml-1.5 inline size-3" /></a><div className="text-xs text-subtle">{p.company_name}</div></Td>
            <Td className="text-muted-foreground">{CATEGORY[p.category].label}</Td>
            <Td>{Math.round(p.confidence * 100)}%</Td>
            <Td className="text-muted-foreground">{p.extraction_method}</Td>
            <Td className="whitespace-nowrap text-right">
              <Button variant="secondary" size="sm" onClick={() => review.mutate({ id: p.id, approve: true })}>Approve</Button>{' '}
              <Button variant="ghost" size="sm" onClick={() => review.mutate({ id: p.id, approve: false })}>Reject</Button>
            </Td>
          </tr>
        ))}
      </tbody>
    </Table>
  )
}

function DuplicatesTable({ duplicates }: { duplicates: AdminOverview['duplicates'] }) {
  const resolve = useAdminAction(({ id, same }: { id: number; same: boolean }) => api.admin.resolveDuplicate(id, same))
  if (!duplicates.length) return <EmptyState icon={Copy} title="No possible duplicates to review">Exact matches across sources merge automatically. Close matches wait here.</EmptyState>
  return (
    <Table>
      <thead><tr><Th>Listing A</Th><Th>Listing B</Th><Th>Similarity</Th><Th className="text-right">Decision</Th></tr></thead>
      <tbody>
        {duplicates.map((d) => (
          <tr key={d.id}>
            <Td><a href={d.a_url} target="_blank" rel="noopener noreferrer" className="font-medium hover:text-accent">{d.a_title}</a><div className="text-xs text-subtle">{d.company_name}</div></Td>
            <Td><a href={d.b_url} target="_blank" rel="noopener noreferrer" className="font-medium hover:text-accent">{d.b_title}</a></Td>
            <Td>{Math.round(d.score * 100)}%</Td>
            <Td className="whitespace-nowrap text-right">
              <Button variant="secondary" size="sm" onClick={() => resolve.mutate({ id: d.id, same: true })}>Merge</Button>{' '}
              <Button variant="ghost" size="sm" onClick={() => resolve.mutate({ id: d.id, same: false })}>Keep both</Button>
            </Td>
          </tr>
        ))}
      </tbody>
    </Table>
  )
}

function AiPanel({ ai, workers }: { ai: AdminOverview['ai']; workers: AdminOverview['health']['workers'] }) {
  const enabled = workers.some((w) => w.ai_enabled)
  if (!ai.length) {
    return (
      <EmptyState icon={Bot} title="No AI processing yet">
        {enabled ? 'Claude runs only when rules leave a listing uncertain.' : 'The worker has no ANTHROPIC_API_KEY set, so AI is off. Uncertain listings go to the review queue instead.'}
      </EmptyState>
    )
  }
  return (
    <Table>
      <thead><tr><Th>When</Th><Th>Status</Th><Th>Model</Th><Th className="text-right">Tokens in</Th><Th className="text-right">Tokens out</Th><Th>Listing</Th></tr></thead>
      <tbody>
        {ai.map((a) => (
          <tr key={a.id}>
            <Td className="whitespace-nowrap text-muted-foreground">{formatDateTime(a.created_at)}</Td>
            <Td><Badge variant={a.status === 'success' ? 'success' : a.status === 'error' ? 'danger' : 'warning'}>{a.status}</Badge>{a.error && <div className="mt-1 max-w-xs text-xs text-danger">{a.error}</div>}</Td>
            <Td className="text-muted-foreground">{a.model}</Td>
            <Td className="text-right">{a.input_tokens ?? 'n/a'}</Td><Td className="text-right">{a.output_tokens ?? 'n/a'}</Td>
            <Td className="max-w-xs truncate text-muted-foreground">{a.opportunity_url}</Td>
          </tr>
        ))}
      </tbody>
    </Table>
  )
}

function HealthRow({ icon: Icon, name, state, detail }: { icon: typeof Server; name: string; state: 'ok' | 'bad' | 'unknown'; detail: string }) {
  return (
    <li className="flex items-center gap-4 border-b border-border/60 py-3.5 last:border-0">
      <Icon aria-hidden className="size-5 shrink-0 text-subtle" />
      <div className="min-w-0 flex-1"><div className="text-sm font-medium">{name}</div><div className="text-xs text-muted-foreground">{detail}</div></div>
      <Badge variant={state === 'ok' ? 'success' : state === 'bad' ? 'danger' : 'neutral'}>{state === 'ok' ? 'Healthy' : state === 'bad' ? 'Problem' : 'Not reporting'}</Badge>
    </li>
  )
}

function HealthPanel({ health }: { health: AdminOverview['health'] }) {
  const celery = health.workers.find((w) => w.worker.startsWith('celery@'))
  const latest = health.workers[0]
  const fresh = (iso: string) => Date.now() - new Date(iso).getTime() < HEARTBEAT_STALE_MINUTES * 60000
  return (
    <ul>
      <HealthRow icon={Database} name="Database" state="ok" detail={`Answered at ${formatDateTime(health.checked_at)}`} />
      <HealthRow icon={Server} name="Scheduled worker (Celery)" state={!celery ? 'unknown' : fresh(celery.last_seen_at) ? 'ok' : 'bad'} detail={celery ? `Last heartbeat ${timeAgo(celery.last_seen_at)}` : 'No Celery worker has reported in. Scans will not run on a schedule until one does.'} />
      <HealthRow icon={Activity} name="Queue (Redis)" state={celery?.redis_ok == null ? 'unknown' : celery.redis_ok ? 'ok' : 'bad'} detail={celery?.redis_ok == null ? 'Reported by the Celery worker' : celery.redis_ok ? 'Reachable from the worker' : 'The worker cannot reach Redis'} />
      <HealthRow icon={Radar} name="Scanner" state={latest ? 'ok' : 'unknown'} detail={latest ? `Last ran ${timeAgo(latest.last_seen_at)}, version ${latest.version ?? 'unknown'}` : 'No scan has run yet'} />
      <HealthRow icon={Bot} name="AI extraction" state={health.workers.some((w) => w.ai_enabled) ? 'ok' : 'unknown'} detail={health.workers.some((w) => w.ai_enabled) ? 'API key configured' : 'Off: no API key on the worker'} />
    </ul>
  )
}

export default function AdminPage() {
  const { user, ready, isAdmin } = useAuth()
  const [tab, setTab] = useState<Tab>('Overview')
  const { data, isLoading, error, refetch, isFetching } = useQuery({ queryKey: ['admin'], queryFn: api.admin.overview, enabled: isAdmin, refetchInterval: 60000 })

  if (ready && !user) return <EmptyState icon={Lock} title="Administrators only" action={<Button asChild size="sm"><Link to="/sign-in">Sign in</Link></Button>}>Sign in with an administrator account.</EmptyState>
  if (ready && user && !isAdmin) return <EmptyState icon={Lock} title="Administrators only">This account does not have administrator access.</EmptyState>

  return (
    <div>
      <div className="mb-5 flex items-center justify-between gap-4">
        <h1 className="text-3xl font-light tracking-tight sm:text-4xl">Admin</h1>
        <Button variant="secondary" size="sm" className="h-11" onClick={() => refetch()} disabled={isFetching}><RefreshCw className={cn(isFetching && 'animate-spin')} />Refresh</Button>
      </div>
      <div role="tablist" className="-mx-4 mb-6 flex gap-1 overflow-x-auto px-4 pb-1 [scrollbar-width:none] sm:mx-0 sm:px-0">
        {TABS.map((t) => (
          <button key={t} role="tab" aria-selected={tab === t} onClick={() => setTab(t)}
            className={cn('min-h-11 shrink-0 rounded-full px-4 text-sm font-medium transition-colors', tab === t ? 'bg-primary text-primary-foreground' : 'text-muted-foreground hover:text-foreground')}>
            {t}
            {t === 'Review' && data && data.counts.pending > 0 && ` (${data.counts.pending})`}
            {t === 'Duplicates' && data && data.counts.duplicates_open > 0 && ` (${data.counts.duplicates_open})`}
          </button>
        ))}
      </div>

      {error && <ErrorState error={error} onRetry={() => refetch()} />}
      {(isLoading || !ready) && <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">{Array.from({ length: 8 }, (_, i) => <Skeleton key={i} className="h-28 rounded-2xl" />)}</div>}

      {data && tab === 'Overview' && (
        <div className="space-y-5">
          <div className="grid grid-cols-2 gap-3 lg:grid-cols-4 lg:gap-4">
            <Stat label="Discovered" value={data.counts.discovered} icon={Radar} onClick={() => setTab('Scans')} />
            <Stat label="Active" value={data.counts.active} icon={CheckCircle2} onClick={() => setTab('Sources')} />
            <Stat label="Pending verification" value={data.counts.pending} icon={Hourglass} tone="warning" onClick={() => setTab('Review')} />
            <Stat label="Failed scans, 24 hours" value={data.counts.failed_scans_24h} icon={XCircle} tone="danger" onClick={() => setTab('Scans')} />
            <Stat label="Expired" value={data.counts.expired} icon={Inbox} onClick={() => setTab('Closed')} />
            <Stat label="Removed by source" value={data.counts.removed} icon={Inbox} onClick={() => setTab('Closed')} />
            <Stat label="Possible duplicates" value={data.counts.duplicates_open} icon={Copy} tone="warning" onClick={() => setTab('Duplicates')} />
            <Stat label="AI calls, 24 hours" value={data.counts.ai_calls_24h} icon={Bot} onClick={() => setTab('AI')} />
          </div>
          <div className="grid gap-5 lg:grid-cols-2">
            <DailyChart title="Scans per day" data={data.daily} legend series={[{ key: 'success', name: 'Completed' }, { key: 'failed', name: 'Failed' }]} />
            <DailyChart title="New opportunities per day" data={data.daily} series={[{ key: 'created', name: 'New' }]} />
          </div>
          <Panel title="System health"><HealthPanel health={data.health} /></Panel>
        </div>
      )}
      {data && tab === 'Sources' && <Panel title="Source monitoring" note="Failing sources back off automatically so they get less traffic."><SourcesTable sources={data.sources} /></Panel>}
      {data && tab === 'Scans' && <div className="space-y-5"><Panel title="Failed scans"><ScansTable scans={data.scans} failedOnly /></Panel><Panel title="Scanner activity" note="The 25 most recent scans."><ScansTable scans={data.scans} /></Panel></div>}
      {data && tab === 'Review' && <Panel title="Pending verification" note="Hidden from the public until approved."><ReviewTable pending={data.pending} /></Panel>}
      {data && tab === 'Duplicates' && <Panel title="Duplicate detection" note={`${formatCount(data.counts.duplicates_merged)} merged so far.`}><DuplicatesTable duplicates={data.duplicates} /></Panel>}
      {data && tab === 'Closed' && (
        <Panel title="Expired and removed opportunities">
          {data.expired.length === 0 ? <EmptyState icon={Inbox} title="Nothing has closed yet" /> : (
            <Table>
              <thead><tr><Th>Opportunity</Th><Th>Reason</Th><Th>Deadline</Th><Th>Last seen</Th></tr></thead>
              <tbody>{data.expired.map((e) => (
                <tr key={e.id}>
                  <Td><Link to={`/opportunities/${e.id}`} className="font-medium hover:text-accent">{e.title}</Link><div className="text-xs text-subtle">{e.company_name}</div></Td>
                  <Td><Badge>{e.status === 'expired' ? 'Deadline passed' : 'No longer listed'}</Badge></Td>
                  <Td className="text-muted-foreground">{e.deadline ? formatDate(e.deadline) : 'Not stated'}</Td>
                  <Td className="text-muted-foreground">{timeAgo(e.last_seen_at)}</Td>
                </tr>
              ))}</tbody>
            </Table>
          )}
        </Panel>
      )}
      {data && tab === 'AI' && <Panel title="AI processing activity" note="Claude is only used when rules leave a listing uncertain, and every value must quote the source."><AiPanel ai={data.ai} workers={data.health.workers} /></Panel>}
      {data && tab === 'Health' && <Panel title="System health"><HealthPanel health={data.health} /></Panel>}
    </div>
  )
}
