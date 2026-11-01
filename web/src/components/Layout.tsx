import { Bookmark, Compass, Gauge, Home, LogIn, LogOut, Search, User } from 'lucide-react'
import { useEffect } from 'react'
import { Link, NavLink, Outlet, useLocation } from 'react-router-dom'
import { useAuth } from '@/lib/auth'
import { cn } from '@/lib/utils'
import { ErrorBoundary } from './ErrorBoundary'
import { Logo } from './Logo'
import { Button } from './ui/button'

const NAV = [
  { to: '/', label: 'Home', icon: Home, end: true },
  { to: '/search', label: 'Find opportunities', icon: Search },
  { to: '/saved', label: 'Saved', icon: Bookmark },
]

function TopNav() {
  const { isAdmin } = useAuth()
  return (
    <nav aria-label="Main" className="hidden items-center gap-1 lg:flex">
      {[...NAV, ...(isAdmin ? [{ to: '/admin', label: 'Admin', icon: Gauge }] : [])].map((item) => (
        <NavLink
          key={item.to}
          to={item.to}
          end={'end' in item}
          className={({ isActive }) => cn('rounded-full px-5 py-3 text-sm font-medium transition-colors', isActive ? 'bg-primary text-primary-foreground' : 'text-muted-foreground hover:text-foreground')}
        >
          {item.label}
        </NavLink>
      ))}
    </nav>
  )
}

function AccountButton() {
  const { user, signOut } = useAuth()
  if (!user) {
    return (
      <Button asChild variant="secondary" className="max-sm:size-11 max-sm:px-0">
        <Link to="/sign-in" aria-label="Sign in"><LogIn /><span className="max-sm:hidden">Sign in</span></Link>
      </Button>
    )
  }
  return (
    <div className="flex items-center gap-2">
      <span title={user.email} className="grid size-11 place-items-center rounded-full bg-surface-raised text-muted-foreground"><User className="size-4" /></span>
      <Button variant="ghost" size="icon" aria-label="Sign out" onClick={signOut}><LogOut /></Button>
    </div>
  )
}

function SideRail() {
  const { isAdmin } = useAuth()
  const items = [
    { to: '/search', label: 'Find opportunities', icon: Compass },
    { to: '/saved', label: 'Saved', icon: Bookmark },
    ...(isAdmin ? [{ to: '/admin', label: 'Admin', icon: Gauge }] : []),
  ]
  return (
    <nav aria-label="Shortcuts" className="fixed bottom-10 left-[max(1.25rem,calc((100vw-92rem)/2+1.25rem))] z-20 hidden flex-col gap-3 2xl:flex">
      {items.map((item) => (
        <NavLink key={item.to} to={item.to} aria-label={item.label} title={item.label}
          className={({ isActive }) => cn('grid size-12 place-items-center rounded-full border border-border transition-colors', isActive ? 'bg-primary text-primary-foreground' : 'bg-surface text-muted-foreground hover:text-foreground')}>
          <item.icon className="size-[18px]" />
        </NavLink>
      ))}
    </nav>
  )
}

function BottomNav() {
  const { isAdmin } = useAuth()
  return (
    <nav aria-label="Main" className="fixed inset-x-0 bottom-0 z-30 flex border-t border-border bg-shell/95 pb-[env(safe-area-inset-bottom)] backdrop-blur lg:hidden">
      {[...NAV, ...(isAdmin ? [{ to: '/admin', label: 'Admin', icon: Gauge }] : [])].map((item) => (
        <NavLink key={item.to} to={item.to} end={'end' in item}
          className={({ isActive }) => cn('flex min-h-14 flex-1 flex-col items-center justify-center gap-1 text-[11px] font-medium', isActive ? 'text-foreground' : 'text-subtle')}>
          <item.icon className="size-5" />
          {item.label === 'Find opportunities' ? 'Search' : item.label}
        </NavLink>
      ))}
    </nav>
  )
}

export function Layout() {
  const { pathname } = useLocation()
  useEffect(() => {
    window.scrollTo(0, 0)
  }, [pathname])
  return (
    <div className="min-h-dvh sm:p-4 lg:p-6">
      <div className="mx-auto min-h-[calc(100dvh-3rem)] max-w-shell rounded-none border-border bg-shell sm:rounded-3xl sm:border">
        <header className="flex items-center justify-between gap-4 px-4 py-4 sm:px-6 lg:px-10 lg:py-6">
          <Logo />
          <TopNav />
          <AccountButton />
        </header>
        <SideRail />
        <main className="px-4 pb-24 pt-2 sm:px-6 lg:px-10 lg:pb-12 2xl:pl-24">
          <ErrorBoundary key={pathname}>
            <Outlet />
          </ErrorBoundary>
        </main>
        <footer className="hidden px-10 pb-8 text-xs text-subtle lg:flex lg:justify-between 2xl:pl-24">
          <span>OpenPath finds opportunities on employers' own sites. Always confirm details with the employer before applying.</span>
          <Link to="/design-system" className="hover:text-foreground">Design system</Link>
        </footer>
      </div>
      <BottomNav />
    </div>
  )
}
