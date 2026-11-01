import { useQuery } from '@tanstack/react-query'
import { Bookmark, LogIn } from 'lucide-react'
import { Link } from 'react-router-dom'
import { CardGrid, OpportunityCard, OpportunityCardSkeleton } from '@/components/OpportunityCard'
import { Button } from '@/components/ui/button'
import { EmptyState, ErrorState } from '@/components/ui/states'
import { api } from '@/lib/api'
import { useAuth } from '@/lib/auth'

export function SavedPage() {
  const { user, ready } = useAuth()
  const { data, isLoading, error, refetch } = useQuery({ queryKey: ['saved', user?.id], queryFn: api.saved, enabled: Boolean(user) })

  return (
    <div>
      <h1 className="mb-6 text-3xl font-light tracking-tight sm:text-4xl">Saved opportunities</h1>
      {ready && !user && (
        <EmptyState icon={LogIn} title="Sign in to see saved opportunities" action={<Button asChild size="sm"><Link to="/sign-in">Sign in</Link></Button>}>
          Saving keeps your shortlist in one place, on any device.
        </EmptyState>
      )}
      {error && <ErrorState error={error} onRetry={() => refetch()} />}
      {isLoading && <CardGrid>{Array.from({ length: 3 }, (_, i) => <OpportunityCardSkeleton key={i} />)}</CardGrid>}
      {data?.length === 0 && (
        <EmptyState icon={Bookmark} title="Nothing saved yet" action={<Button asChild variant="secondary" size="sm"><Link to="/search">Find opportunities</Link></Button>}>
          Select the bookmark on any opportunity to keep it here.
        </EmptyState>
      )}
      {data && data.length > 0 && <CardGrid>{data.map((o) => <OpportunityCard key={o.id} opportunity={o} />)}</CardGrid>}
    </div>
  )
}
