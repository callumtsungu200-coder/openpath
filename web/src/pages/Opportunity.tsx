import { useQuery } from '@tanstack/react-query'
import { AlertTriangle, ArrowLeft, BadgeCheck, ExternalLink, FileQuestion, ShieldQuestion } from 'lucide-react'
import type { ReactNode } from 'react'
import { Link, useParams } from 'react-router-dom'
import { CompanyLogo, SaveButton } from '@/components/OpportunityCard'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardTitle } from '@/components/ui/card'
import { EmptyState, ErrorState, Skeleton } from '@/components/ui/states'
import { api } from '@/lib/api'
import { ARRANGEMENT, CATEGORY, formatAge, formatSalary } from '@/lib/labels'
import { applyLabel, formatDate, formatDateTime, safeUrl } from '@/lib/utils'

const ADAPTER_LABEL: Record<string, string> = {
  greenhouse: "the employer's public Greenhouse job board",
  lever: "the employer's public Lever job board",
  ashby: "the employer's public Ashby job board",
  jsonld_crawl: "job data published on the employer's website",
  rendered: "job data published on the employer's website",
  gov_apprenticeships: "GOV.UK's official Find an apprenticeship service",
}

function Fact({ label, value, note }: { label: string; value: ReactNode | null | undefined; note?: string }) {
  return (
    <div className="flex items-baseline justify-between gap-4 border-b border-border/60 py-3 last:border-0">
      <dt className="shrink-0 text-sm text-muted-foreground">{label}</dt>
      <dd className="text-right text-sm">
        {value ?? <span className="text-subtle">Not stated</span>}
        {value && note && <span className="mt-0.5 block text-xs text-subtle">{note}</span>}
      </dd>
    </div>
  )
}

function Section({ title, items }: { title: string; items?: string[] }) {
  if (!items?.length) return null
  return (
    <section>
      <h2 className="mb-3 text-lg font-semibold tracking-tight">{title}</h2>
      <ul className="space-y-2 text-[15px] leading-relaxed text-muted-foreground">
        {items.map((item) => (
          <li key={item} className="flex gap-3"><span aria-hidden className="mt-2.5 size-1.5 shrink-0 rounded-full bg-accent" />{item}</li>
        ))}
      </ul>
    </section>
  )
}

export function OpportunityPage() {
  const { id = '' } = useParams()
  const { data: o, isLoading, error, refetch } = useQuery({ queryKey: ['opportunity', id], queryFn: () => api.opportunity(id) })
  const { data: source } = useQuery({ queryKey: ['opportunity-source', id], queryFn: () => api.source(id), enabled: Boolean(o) })

  if (isLoading) return <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_23rem]"><Skeleton className="h-96 rounded-2xl" /><Skeleton className="h-96 rounded-2xl" /></div>
  if (error) return <ErrorState error={error} onRetry={() => refetch()} />
  if (!o) {
    return (
      <EmptyState icon={FileQuestion} title="This opportunity is not available" action={<Button asChild variant="secondary" size="sm"><Link to="/search">Find others</Link></Button>}>
        It may have closed or been removed by the employer.
      </EmptyState>
    )
  }

  const provenance = o.field_provenance ?? {}
  const verified = o.verification === 'verified'
  const closed = o.status !== 'active'
  const applyUrl = safeUrl(o.apply_url, o.source_url)
  const originalUrl = safeUrl(o.source_url)
  const companyUrl = safeUrl(o.company_url, source?.company_url)
  const companyDescription = o.company_description ?? source?.company_description
  const hasSections = [o.responsibilities, o.eligibility, o.requirements, o.programme_info].some((s) => s?.length)

  return (
    <div>
      <Link to="/search" className="mb-3 inline-flex min-h-11 items-center gap-2 text-sm text-muted-foreground transition-colors hover:text-foreground"><ArrowLeft className="size-4" />All opportunities</Link>
      {closed && (
        <div role="status" className="mb-5 flex items-center gap-3 rounded-xl bg-warning-soft p-4 text-sm text-warning">
          <AlertTriangle className="size-4 shrink-0" />
          {o.status === 'expired' ? 'The application deadline has passed.' : 'The employer no longer lists this opportunity.'}
        </div>
      )}
      <div className="grid grid-cols-1 items-start gap-6 lg:grid-cols-[minmax(0,1fr)_23rem]">
        <div className="min-w-0 space-y-8 rounded-2xl border border-border bg-surface p-5 sm:p-8">
          <header>
            <div className="flex items-start gap-4">
              <CompanyLogo size="lg" name={o.company_name} src={o.company_logo_url} />
              <div className="min-w-0 flex-1">
                <p className="font-medium text-muted-foreground">{o.company_name}</p>
                <h1 className="mt-1 text-2xl font-semibold leading-tight tracking-tight sm:text-3xl">{o.title}</h1>
              </div>
            </div>
            <div className="mt-5 flex flex-wrap gap-2">
              <Badge variant="accent">{CATEGORY[o.category].label}</Badge>
              {o.industry && <Badge>{o.industry}</Badge>}
              {o.employment_type && <Badge>{o.employment_type.replace(/([a-z])([A-Z])/g, '$1 $2').replace(/_/g, ' ')}</Badge>}
            </div>
          </header>

          <Section title="Responsibilities" items={o.responsibilities} />
          <Section title="Eligibility" items={o.eligibility} />
          <Section title="Requirements" items={o.requirements} />
          {o.duration && (
            <section>
              <h2 className="mb-2 text-lg font-semibold tracking-tight">Duration</h2>
              <p className="text-[15px] text-muted-foreground">{o.duration}</p>
            </section>
          )}
          <Section title="Programme information" items={o.programme_info} />

          <section>
            <h2 className="mb-3 text-lg font-semibold tracking-tight">{hasSections ? 'Full description' : 'Description'}</h2>
            {o.description ? (
              <div className="space-y-3 whitespace-pre-line break-words text-[15px] leading-relaxed text-muted-foreground">{o.description}</div>
            ) : (
              <p className="text-sm text-subtle">The source did not provide a description.</p>
            )}
          </section>
        </div>

        <aside className="space-y-4 lg:sticky lg:top-6">
          <Card className="p-5">
            <div className="flex gap-2">
              <Button asChild className="flex-1">
                <a href={applyUrl} target="_blank" rel="noopener noreferrer nofollow" className="min-w-0"><span className="truncate">{applyLabel(applyUrl)}</span><ExternalLink /></a>
              </Button>
              <SaveButton id={o.id} />
            </div>
            <dl className="mt-3">
              <Fact label="Location" value={o.location} />
              <Fact label="Working pattern" value={o.arrangement && ARRANGEMENT[o.arrangement]} note={provenance.arrangement} />
              <Fact label="Salary" value={formatSalary(o)} note={provenance.salary} />
              <Fact label="Paid" value={o.is_paid == null ? null : o.is_paid ? 'Yes' : 'No'} note={provenance.paid} />
              <Fact label="Deadline" value={o.deadline && formatDate(o.deadline)} note={provenance.deadline} />
              <Fact label="Age eligibility" value={formatAge(o)} note={o.age_text ? `"${o.age_text}"` : provenance.age} />
              {o.duration && <Fact label="Duration" value={o.duration} note={provenance.duration} />}
            </dl>
          </Card>
          <Card className="p-5">
            <CardTitle className="text-base">{o.company_name}</CardTitle>
            {companyDescription && <p className="mt-2 whitespace-pre-line text-sm text-muted-foreground">{companyDescription}</p>}
            {companyUrl && <a href={companyUrl} target="_blank" rel="noopener noreferrer" className="mt-2 inline-flex min-h-9 items-center gap-1.5 text-sm font-medium text-accent">Company website<ExternalLink className="size-3.5" /></a>}
          </Card>
          <Card className="p-5">
            <div className="flex items-center gap-2">
              {verified ? <BadgeCheck className="size-5 text-success" /> : <ShieldQuestion className="size-5 text-warning" />}
              <CardTitle className="text-base">{verified ? 'Verified at source' : 'Awaiting verification'}</CardTitle>
            </div>
            <p className="mt-2 text-sm text-muted-foreground">
              {verified
                ? `Found through ${source ? ADAPTER_LABEL[source.adapter] ?? 'the employer' : 'the employer'}. Anything marked "Not stated" was not in the source, so check with the employer.`
                : 'An administrator has not yet reviewed this listing.'}
            </p>
            <dl className="mt-2">
              <Fact label="Last verified" value={o.last_verified_at && formatDateTime(o.last_verified_at)} />
              <Fact label="First found" value={formatDate(o.discovered_at)} />
            </dl>
            <a href={originalUrl} target="_blank" rel="noopener noreferrer nofollow" className="mt-1 inline-flex min-h-9 items-center gap-1.5 text-sm font-medium text-accent">View original listing<ExternalLink className="size-3.5" /></a>
          </Card>
        </aside>
      </div>
    </div>
  )
}
