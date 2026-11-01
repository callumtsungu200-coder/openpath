import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { SearchX, SlidersHorizontal, X } from 'lucide-react'
import { useMemo, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { CardGrid, OpportunityCard, OpportunityCardSkeleton } from '@/components/OpportunityCard'
import { SearchBox } from '@/components/SearchBox'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Checkbox } from '@/components/ui/checkbox'
import { Dialog, DialogTitle, DialogTrigger, SheetContent } from '@/components/ui/dialog'
import { Input, Label, Select } from '@/components/ui/input'
import { EmptyState, ErrorState } from '@/components/ui/states'
import { api } from '@/lib/api'
import { ARRANGEMENT, CATEGORY } from '@/lib/labels'
import type { Arrangement, Category, Facet, SearchFilters } from '@/lib/types'
import { formatCount } from '@/lib/utils'

const PAGE_SIZE = 24
const EARLY_CAREER: Category[] = ['apprenticeship', 'internship', 'work_experience', 'insight_programme', 'graduate_scheme', 'placement', 'entry_level_job']

function useFilters() {
  const [params, setParams] = useSearchParams()
  const filters = useMemo<SearchFilters & { page: number }>(() => {
    const categories = params.getAll('category') as Category[]
    const num = (key: string) => (params.get(key) ? Number(params.get(key)) : undefined)
    return {
      q: params.get('q') ?? undefined,
      categories: params.get('early') ? EARLY_CAREER : categories,
      industries: params.getAll('industry'),
      regions: params.getAll('region'),
      arrangements: params.getAll('arrangement') as Arrangement[],
      paid: params.get('paid') === null ? undefined : params.get('paid') === 'true',
      age: num('age'),
      deadline_within_days: num('within'),
      has_deadline: params.get('has_deadline') === 'true' ? true : undefined,
      sort: (params.get('sort') as SearchFilters['sort']) ?? undefined,
      page: num('page') ?? 0,
    }
  }, [params])

  const update = (change: (next: URLSearchParams) => void) => {
    const next = new URLSearchParams(params)
    next.delete('page')
    change(next)
    setParams(next)
  }
  const toggle = (key: string, value: string) => update((next) => {
    if (key === 'category') next.delete('early')
    const values = next.getAll(key)
    next.delete(key)
    for (const v of values) if (v !== value) next.append(key, v)
    if (!values.includes(value)) next.append(key, value)
  })
  const set = (key: string, value?: string) => update((next) => { value ? next.set(key, value) : next.delete(key) })
  const setPage = (page: number) => {
    const next = new URLSearchParams(params)
    next.set('page', String(page))
    setParams(next)
    window.scrollTo({ top: 0 })
  }
  const clear = () => setParams(params.get('q') ? { q: params.get('q')! } : {})
  return { filters, params, update, toggle, set, setPage, clear }
}

function CheckGroup({ title, options, selected, onToggle, labelFor }: { title: string; options: Facet[]; selected: string[]; onToggle: (v: string) => void; labelFor?: (v: string) => string }) {
  const [expanded, setExpanded] = useState(false)
  if (options.length === 0) return null
  const visible = expanded ? options : options.slice(0, 6)
  return (
    <fieldset>
      <legend className="mb-1.5 text-sm font-medium">{title}</legend>
      {visible.map((o) => (
        <label key={o.value} className="flex min-h-10 cursor-pointer items-center gap-3 text-sm text-muted-foreground transition-colors hover:text-foreground">
          <Checkbox checked={selected.includes(o.value)} onCheckedChange={() => onToggle(o.value)} />
          <span className="min-w-0 flex-1 truncate">{labelFor ? labelFor(o.value) : o.value}</span>
          {o.count > 0 && <span className="text-xs text-subtle">{formatCount(o.count)}</span>}
        </label>
      ))}
      {options.length > 6 && (
        <button type="button" onClick={() => setExpanded((e) => !e)} className="min-h-9 text-[13px] font-medium text-accent">
          {expanded ? 'Show fewer' : `Show ${options.length - 6} more`}
        </button>
      )}
    </fieldset>
  )
}

function FilterPanel({ ctx }: { ctx: ReturnType<typeof useFilters> }) {
  const { filters, params, toggle, set } = ctx
  const { data: facets } = useQuery({ queryKey: ['facets'], queryFn: api.facets })
  return (
    <div className="space-y-6">
      <CheckGroup title="Category" options={facets?.categories ?? []} selected={filters.categories ?? []} onToggle={(v) => toggle('category', v)} labelFor={(v) => CATEGORY[v as Category]?.plural ?? v} />
      <CheckGroup title="Working arrangement" options={Object.keys(ARRANGEMENT).map((value) => ({ value, count: 0 }))} selected={filters.arrangements ?? []} onToggle={(v) => toggle('arrangement', v)} labelFor={(v) => ARRANGEMENT[v as Arrangement]} />
      <CheckGroup title="Location" options={facets?.regions ?? []} selected={filters.regions ?? []} onToggle={(v) => toggle('region', v)} />
      <CheckGroup title="Industry" options={facets?.industries ?? []} selected={filters.industries ?? []} onToggle={(v) => toggle('industry', v)} />
      <div>
        <Label htmlFor="filter-paid">Pay</Label>
        <Select id="filter-paid" value={params.get('paid') ?? ''} onChange={(e) => set('paid', e.target.value || undefined)}>
          <option value="">Paid or unpaid</option>
          <option value="true">Paid only</option>
          <option value="false">Unpaid only</option>
        </Select>
      </div>
      <div>
        <Label htmlFor="filter-age">Your age</Label>
        <Input id="filter-age" type="number" inputMode="numeric" min={13} max={70} placeholder="e.g. 16" value={params.get('age') ?? ''} onChange={(e) => set('age', e.target.value || undefined)} />
        <p className="mt-1.5 text-xs text-subtle">Shows only listings that state an age range including yours. Most employers do not state one.</p>
      </div>
      <div>
        <Label htmlFor="filter-deadline">Deadline</Label>
        <Select id="filter-deadline" value={params.get('within') ?? (params.get('has_deadline') ? 'any' : '')}
          onChange={(e) => {
            const v = e.target.value
            ctx.update((next) => {
              next.delete('within')
              next.delete('has_deadline')
              if (v === 'any') next.set('has_deadline', 'true')
              else if (v) next.set('within', v)
            })
          }}>
          <option value="">Any, including none stated</option>
          <option value="any">Has a stated deadline</option>
          <option value="7">Closes within 7 days</option>
          <option value="30">Closes within 30 days</option>
          <option value="90">Closes within 3 months</option>
        </Select>
      </div>
    </div>
  )
}

export function SearchPage() {
  const ctx = useFilters()
  const { filters, params, set, setPage, clear, toggle } = ctx
  const { page, ...query } = filters
  const { data, isLoading, error, refetch, isFetching } = useQuery({
    queryKey: ['search', query, page],
    queryFn: () => api.search(query, page, PAGE_SIZE),
    placeholderData: keepPreviousData,
  })

  const activeChips: { key: string; value: string; label: string }[] = [
    ...params.getAll('category').map((v) => ({ key: 'category', value: v, label: CATEGORY[v as Category]?.plural ?? v })),
    ...params.getAll('arrangement').map((v) => ({ key: 'arrangement', value: v, label: ARRANGEMENT[v as Arrangement] })),
    ...params.getAll('region').map((v) => ({ key: 'region', value: v, label: v })),
    ...params.getAll('industry').map((v) => ({ key: 'industry', value: v, label: v })),
  ]
  const filterCount = activeChips.length + ['paid', 'age', 'within', 'has_deadline', 'early'].filter((k) => params.get(k)).length
  const total = data?.total ?? 0
  const pages = Math.ceil(total / PAGE_SIZE)

  return (
    <div>
      <h1 className="text-3xl font-light tracking-tight sm:text-4xl">Find opportunities</h1>
      <div className="mt-5 rounded-2xl border border-border bg-surface p-3 sm:p-5">
        <SearchBox large initial={filters.q ?? ''} onSearch={(q) => set('q', q || undefined)} />
      </div>

      <div className="mt-6 grid grid-cols-1 gap-6 lg:grid-cols-[17.5rem_minmax(0,1fr)]">
        <aside aria-label="Filters" className="hidden lg:block">
          <div className="rounded-2xl border border-border bg-surface p-5">
            <div className="mb-4 flex min-h-8 items-center justify-between">
              <h2 className="font-semibold">Filters</h2>
              {filterCount > 0 && <button onClick={clear} className="text-[13px] font-medium text-accent">Clear all</button>}
            </div>
            <FilterPanel ctx={ctx} />
          </div>
        </aside>

        <div className="min-w-0">
          <div className="mb-4 flex flex-wrap items-center gap-3">
            <p aria-live="polite" className="mr-auto text-sm text-muted-foreground">
              {data ? `${formatCount(total)} ${total === 1 ? 'opportunity' : 'opportunities'}` : 'Searching'}
            </p>
            <Dialog>
              <DialogTrigger asChild>
                <Button variant="secondary" size="sm" className="h-11 lg:hidden"><SlidersHorizontal />Filters{filterCount > 0 && ` (${filterCount})`}</Button>
              </DialogTrigger>
              <SheetContent aria-describedby={undefined}>
                <DialogTitle className="border-b border-border p-5 pr-16 font-semibold">Filters</DialogTitle>
                <div className="overflow-y-auto p-5"><FilterPanel ctx={ctx} /></div>
                {filterCount > 0 && <div className="border-t border-border p-4"><Button variant="secondary" className="w-full" onClick={clear}>Clear all filters</Button></div>}
              </SheetContent>
            </Dialog>
            <label className="flex items-center gap-2 text-sm text-muted-foreground">
              <span className="max-sm:sr-only">Sort by</span>
              <Select aria-label="Sort by" value={params.get('sort') ?? (filters.q ? 'relevance' : 'newest')} onChange={(e) => set('sort', e.target.value)} className="h-11 w-44">
                {filters.q && <option value="relevance">Best match</option>}
                <option value="newest">Newest first</option>
                <option value="deadline">Closing soonest</option>
                <option value="salary">Highest stated pay</option>
              </Select>
            </label>
          </div>

          {activeChips.length > 0 && (
            <div className="mb-4 flex flex-wrap gap-2">
              {activeChips.map((c) => (
                <button key={`${c.key}-${c.value}`} onClick={() => toggle(c.key, c.value)} aria-label={`Remove filter ${c.label}`}>
                  <Badge variant="accent" className="min-h-8 hover:brightness-110">{c.label}<X /></Badge>
                </button>
              ))}
            </div>
          )}

          {error && <ErrorState error={error} onRetry={() => refetch()} />}
          {isLoading && <CardGrid className="xl:grid-cols-2 2xl:grid-cols-3">{Array.from({ length: 6 }, (_, i) => <OpportunityCardSkeleton key={i} />)}</CardGrid>}
          {data && total === 0 && (
            <EmptyState icon={SearchX} title="No matching opportunities" action={filterCount > 0 ? <Button variant="secondary" size="sm" onClick={clear}>Clear filters</Button> : undefined}>
              {params.get('age') ? 'Most employers do not state an age range, so the age filter narrows results a lot. Try removing it.' : 'Try a broader search, or fewer filters.'}
            </EmptyState>
          )}
          {data && total > 0 && (
            <div className={isFetching ? 'opacity-70 transition-opacity' : 'transition-opacity'}>
              <CardGrid className="xl:grid-cols-2 2xl:grid-cols-3">{data.items.map((o) => <OpportunityCard key={o.id} opportunity={o} />)}</CardGrid>
              {pages > 1 && (
                <nav aria-label="Pages" className="mt-6 flex items-center justify-center gap-3">
                  <Button variant="secondary" size="sm" className="h-11" disabled={page === 0} onClick={() => setPage(page - 1)}>Previous</Button>
                  <span className="text-sm text-muted-foreground">Page {page + 1} of {pages}</span>
                  <Button variant="secondary" size="sm" className="h-11" disabled={page + 1 >= pages} onClick={() => setPage(page + 1)}>Next</Button>
                </nav>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
