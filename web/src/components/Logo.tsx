import { Link } from 'react-router-dom'

export function Logo() {
  return (
    <Link to="/" aria-label="OpenPath home" className="group inline-flex items-center rounded-full text-lg font-semibold tracking-tight">
      <span className="flex h-11 items-center rounded-full bg-primary pl-4 pr-2 text-primary-foreground">Open</span>
      <span className="pl-2">Path</span>
    </Link>
  )
}
