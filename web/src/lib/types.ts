export type Category =
  | 'apprenticeship' | 'internship' | 'work_experience' | 'insight_programme' | 'graduate_scheme'
  | 'placement' | 'entry_level_job' | 'job' | 'volunteering' | 'scholarship' | 'competition' | 'course' | 'other'
export type Arrangement = 'remote' | 'hybrid' | 'in_person'

export interface Opportunity {
  id: string
  title: string
  company_name: string
  company_logo_url: string | null
  company_url?: string | null
  company_description?: string | null
  category: Category
  industry: string | null
  location: string | null
  region: string | null
  arrangement: Arrangement | null
  employment_type: string | null
  salary_min: number | null
  salary_max: number | null
  salary_period: 'year' | 'month' | 'week' | 'day' | 'hour' | null
  salary_text: string | null
  is_paid: boolean | null
  min_age: number | null
  max_age: number | null
  age_text: string | null
  deadline: string | null
  duration: string | null
  description?: string | null
  responsibilities?: string[]
  eligibility?: string[]
  requirements?: string[]
  programme_info?: string[]
  source_url: string
  apply_url: string | null
  extraction_method: 'structured' | 'rules' | 'ai' | 'admin'
  field_provenance: Record<string, string>
  application_status: 'open' | 'closed' | null
  status: 'active' | 'expired' | 'removed' | 'duplicate' | 'rejected'
  verification: 'verified' | 'pending' | 'failed'
  discovered_at: string
  last_verified_at: string | null
  posted_at: string | null
}

export interface SourceInfo {
  name: string
  adapter: string
  company_url: string | null
  company_description: string | null
}

export interface HomeFeed {
  recent: Opportunity[]
  featured: Opportunity[]
  categories: { category: Category; count: number }[]
  industries: { industry: string; count: number }[]
  updates: { id: number; kind: string; detail: string | null; created_at: string; opportunity_id: string; title: string; company_name: string }[]
  stats: { active: number; companies: number; discovered_7d: number; sources_monitored: number; last_scan_at: string | null }
}

export interface SearchFilters {
  q?: string
  categories?: Category[]
  industries?: string[]
  regions?: string[]
  arrangements?: Arrangement[]
  paid?: boolean
  age?: number
  deadline_within_days?: number
  has_deadline?: boolean
  sort?: 'relevance' | 'newest' | 'deadline' | 'salary'
}

export interface Facet { value: string; count: number }
export interface Facets { industries: Facet[]; regions: Facet[]; categories: Facet[] }

export interface AdminOverview {
  counts: Record<'discovered' | 'active' | 'expired' | 'removed' | 'pending' | 'duplicates_open' | 'duplicates_merged' | 'failed_scans_24h' | 'scans_24h' | 'ai_calls_24h', number>
  daily: { day: string; success: number; failed: number; created: number }[]
  sources: { id: number; name: string; adapter: string; url: string; enabled: boolean; last_scan_at: string | null; last_status: ScanStatus | null; last_error: string | null; next_scan_at: string; consecutive_failures: number; active_count: number }[]
  scans: { id: number; source_name: string; status: ScanStatus; started_at: string; finished_at: string | null; items_found: number; items_outside_uk: number; items_created: number; items_updated: number; items_unchanged: number; items_removed: number; ai_calls: number; error: string | null }[]
  pending: { id: string; title: string; company_name: string; category: Category; confidence: number; extraction_method: string; source_url: string; discovered_at: string }[]
  duplicates: { id: number; score: number; a_id: string; a_title: string; a_url: string; b_id: string; b_title: string; b_url: string; company_name: string }[]
  expired: { id: string; title: string; company_name: string; status: string; deadline: string | null; last_seen_at: string }[]
  ai: { id: number; opportunity_url: string | null; model: string; purpose: string; status: string; input_tokens: number | null; output_tokens: number | null; error: string | null; created_at: string }[]
  health: { workers: { worker: string; last_seen_at: string; version: string | null; redis_ok: boolean | null; ai_enabled: boolean }[]; database_ok: boolean; checked_at: string }
}
export type ScanStatus = 'running' | 'success' | 'partial' | 'failed'
