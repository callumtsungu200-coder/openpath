import { useQuery } from '@tanstack/react-query'
import { Building2, Search as SearchIcon } from 'lucide-react'
import { useEffect, useId, useRef, useState } from 'react'
import { api } from '@/lib/api'
import { cn } from '@/lib/utils'
import { Button } from './ui/button'

function useDebounced<T>(value: T, ms: number) {
  const [debounced, setDebounced] = useState(value)
  useEffect(() => {
    const timer = setTimeout(() => setDebounced(value), ms)
    return () => clearTimeout(timer)
  }, [value, ms])
  return debounced
}

export function SearchBox({ initial = '', onSearch, placeholder, large }: { initial?: string; onSearch: (q: string) => void; placeholder?: string; large?: boolean }) {
  const [value, setValue] = useState(initial)
  const [open, setOpen] = useState(false)
  const [active, setActive] = useState(-1)
  const listId = useId()
  const wrapper = useRef<HTMLFormElement>(null)
  const term = useDebounced(value.trim(), 200)
  const { data: suggestions = [] } = useQuery({
    queryKey: ['suggest', term],
    queryFn: () => api.suggestions(term),
    enabled: term.length >= 2,
  })
  const shown = open && term.length >= 2 ? suggestions : []

  useEffect(() => setValue(initial), [initial])
  useEffect(() => {
    const close = (e: MouseEvent) => { if (!wrapper.current?.contains(e.target as Node)) setOpen(false) }
    document.addEventListener('mousedown', close)
    return () => document.removeEventListener('mousedown', close)
  }, [])

  const submit = (q: string) => {
    setValue(q)
    setOpen(false)
    setActive(-1)
    onSearch(q.trim())
  }

  return (
    <form ref={wrapper} role="search" className="relative" onSubmit={(e) => { e.preventDefault(); submit(active >= 0 && shown[active] ? shown[active].label : value) }}>
      <SearchIcon aria-hidden className={cn('absolute left-4 top-1/2 size-5 -translate-y-1/2 text-subtle', large && 'sm:left-5')} />
      <input
        role="combobox"
        aria-expanded={shown.length > 0}
        aria-controls={listId}
        aria-autocomplete="list"
        aria-label="Search opportunities"
        autoComplete="off"
        enterKeyHint="search"
        value={value}
        placeholder={placeholder ?? 'Search by role, company or skill'}
        onChange={(e) => { setValue(e.target.value); setOpen(true); setActive(-1) }}
        onFocus={() => setOpen(true)}
        onKeyDown={(e) => {
          if (e.key === 'ArrowDown') { e.preventDefault(); setActive((i) => Math.min(i + 1, shown.length - 1)) }
          if (e.key === 'ArrowUp') { e.preventDefault(); setActive((i) => Math.max(i - 1, -1)) }
          if (e.key === 'Escape') setOpen(false)
        }}
        className={cn(
          'w-full rounded-xl border border-input bg-surface-raised/50 pl-12 pr-[6.75rem] text-base text-foreground transition-colors placeholder:text-subtle hover:border-subtle/50 focus-visible:border-ring',
          large ? 'h-14 sm:h-16 sm:pl-14 sm:pr-36 sm:text-lg' : 'h-13 h-[3.25rem]',
        )}
      />
      <Button type="submit" className={cn('absolute right-1.5 top-1.5 rounded-lg', large ? 'h-11 px-4 sm:h-[3.25rem] sm:px-8' : 'h-10 px-4')}>Search</Button>
      {shown.length > 0 && (
        <ul id={listId} role="listbox" className="absolute inset-x-0 top-full z-40 mt-2 overflow-hidden rounded-xl border border-border bg-surface-raised p-1.5 shadow-pop">
          {shown.map((s, i) => (
            <li key={`${s.kind}-${s.label}`} role="option" aria-selected={i === active}>
              <button type="button" onClick={() => submit(s.label)}
                className={cn('flex min-h-11 w-full items-center gap-3 rounded-lg px-3 py-2 text-left text-sm hover:bg-input', i === active && 'bg-input')}>
                {s.kind === 'company' ? <Building2 className="size-4 shrink-0 text-subtle" /> : <SearchIcon className="size-4 shrink-0 text-subtle" />}
                <span className="truncate">{s.label}</span>
                {s.kind === 'company' && <span className="ml-auto text-xs text-subtle">Company</span>}
              </button>
            </li>
          ))}
        </ul>
      )}
    </form>
  )
}
