import { Compass } from 'lucide-react'
import { Link } from 'react-router-dom'
import { Button } from '@/components/ui/button'
import { EmptyState } from '@/components/ui/states'

export function NotFoundPage() {
  return (
    <EmptyState icon={Compass} title="Page not found" action={<Button asChild size="sm"><Link to="/">Go home</Link></Button>}>
      That address does not match anything on OpenPath.
    </EmptyState>
  )
}
