import { supabase } from './supabase'
import type { AdminOverview, Facets, HomeFeed, Opportunity, SearchFilters, SourceInfo } from './types'

async function rpc<T>(fn: string, params: Record<string, unknown> = {}): Promise<T> {
  const { data, error } = await supabase.rpc(fn, params)
  if (error) throw new Error(error.message)
  return data as T
}

const emptyToNull = <T,>(list?: T[]) => (list && list.length ? list : undefined)

export const api = {
  home: () => rpc<HomeFeed>('home_feed'),
  facets: () => rpc<Facets>('search_facets'),
  suggestions: (q: string) => rpc<{ label: string; kind: 'title' | 'company' }[]>('search_suggestions', { q }),
  search: (filters: SearchFilters, page: number, pageSize = 24) =>
    rpc<{ total: number; items: Opportunity[] }>('search_opportunities', {
      q: filters.q || undefined,
      categories: emptyToNull(filters.categories),
      industries: emptyToNull(filters.industries),
      regions: emptyToNull(filters.regions),
      arrangements: emptyToNull(filters.arrangements),
      paid: filters.paid,
      age: filters.age,
      deadline_within_days: filters.deadline_within_days,
      has_deadline: filters.has_deadline,
      sort: filters.sort === 'newest' ? 'newest' : filters.sort ?? (filters.q ? 'relevance' : 'newest'),
      page_size: pageSize,
      page_offset: page * pageSize,
    }),
  opportunity: (id: string) => rpc<Opportunity | null>('get_opportunity', { opportunity: id }),
  source: (id: string) => rpc<SourceInfo | null>('get_opportunity_source', { opportunity: id }),
  toggleSaved: (id: string) => rpc<boolean>('toggle_saved', { opportunity: id }),
  saved: () => rpc<Opportunity[]>('my_saved'),
  savedIds: () => rpc<string[]>('my_saved_ids'),
  profile: () => rpc<{ is_admin: boolean } | null>('my_profile'),
  admin: {
    overview: () => rpc<AdminOverview>('admin_overview'),
    review: (id: string, approve: boolean) => rpc<void>('admin_review_opportunity', { opportunity: id, approve }),
    resolveDuplicate: (id: number, isDuplicate: boolean) => rpc<void>('admin_resolve_duplicate', { candidate: id, is_duplicate: isDuplicate }),
    setSourceEnabled: (id: number, enable: boolean) => rpc<void>('admin_set_source_enabled', { source: id, enable }),
    requestScan: (id: number) => rpc<void>('admin_request_scan', { source: id }),
  },
}
