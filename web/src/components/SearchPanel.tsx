import { useQuery } from '@tanstack/react-query'
import { Search } from 'lucide-react'
import { useEffect, useState } from 'react'
import { api } from '@/lib/api'
import { ARRANGEMENT, CATEGORY } from '@/lib/labels'
import type { Arrangement, Category } from '@/lib/types'
import { isConfigured } from '@/lib/supabase'
import { SearchBox } from './SearchBox'
import { Button } from './ui/button'
import { Label, Select } from './ui/input'

export interface PanelValues { q: string; region: string; category: string; arrangement: string }

/** The labelled search bar from the design reference. Phones get the keyword field only, and filters live in a sheet. */
export function SearchPanel({ initial, onSubmit }: { initial?: Partial<PanelValues>; onSubmit: (values: PanelValues) => void }) {
  const from = (v?: Partial<PanelValues>): PanelValues => ({ q: v?.q ?? '', region: v?.region ?? '', category: v?.category ?? '', arrangement: v?.arrangement ?? '' })
  const [values, setValues] = useState(from(initial))
  const { data: facets } = useQuery({ queryKey: ['facets'], queryFn: api.facets, enabled: isConfigured })
  const key = JSON.stringify(from(initial))
  useEffect(() => setValues(JSON.parse(key)), [key])
  const set = (field: keyof PanelValues, value: string) => setValues((v) => ({ ...v, [field]: value }))

  return (
    <div className="grid grid-cols-1 items-end gap-3 rounded-3xl bg-surface p-3 shadow-card sm:grid-cols-2 sm:p-5 xl:grid-cols-[1.5fr_1fr_1fr_1fr_11rem]">
      <div className="sm:col-span-2 xl:col-span-1">
        <label className="mb-2 hidden text-sm font-medium sm:block" htmlFor="panel-q">Role, company or skill</label>
        <SearchBox id="panel-q" bare initial={values.q} onValueChange={(q) => set('q', q)} onSearch={(q) => onSubmit({ ...values, q })} placeholder="e.g. Software apprentice" />
      </div>
      <div className="hidden sm:block">
        <Label htmlFor="panel-region">Location</Label>
        <Select id="panel-region" value={values.region} onChange={(e) => set('region', e.target.value)}>
          <option value="">Anywhere in the UK</option>
          {facets?.regions.map((r) => <option key={r.value} value={r.value}>{r.value}</option>)}
        </Select>
      </div>
      <div className="hidden sm:block">
        <Label htmlFor="panel-category">Category</Label>
        <Select id="panel-category" value={values.category} onChange={(e) => set('category', e.target.value)}>
          <option value="">All categories</option>
          {facets?.categories.map((c) => <option key={c.value} value={c.value}>{CATEGORY[c.value as Category]?.plural ?? c.value}</option>)}
        </Select>
      </div>
      <div className="hidden sm:block">
        <Label htmlFor="panel-arrangement">Working pattern</Label>
        <Select id="panel-arrangement" value={values.arrangement} onChange={(e) => set('arrangement', e.target.value)}>
          <option value="">Any pattern</option>
          {(Object.keys(ARRANGEMENT) as Arrangement[]).map((a) => <option key={a} value={a}>{ARRANGEMENT[a]}</option>)}
        </Select>
      </div>
      <Button size="lg" className="w-full" onClick={() => onSubmit(values)}><Search />Search</Button>
    </div>
  )
}
