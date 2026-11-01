import { BookOpen, Briefcase, Building2, Eye, GraduationCap, HandHeart, Hammer, Medal, Rocket, Sparkles, Trophy, UserRound, type LucideIcon } from 'lucide-react'
import type { Arrangement, Category, Opportunity } from './types'

export const CATEGORY: Record<Category, { label: string; plural: string; icon: LucideIcon }> = {
  apprenticeship: { label: 'Apprenticeship', plural: 'Apprenticeships', icon: Hammer },
  internship: { label: 'Internship', plural: 'Internships', icon: Rocket },
  work_experience: { label: 'Work experience', plural: 'Work experience', icon: UserRound },
  insight_programme: { label: 'Insight programme', plural: 'Insight programmes', icon: Eye },
  graduate_scheme: { label: 'Graduate scheme', plural: 'Graduate schemes', icon: GraduationCap },
  placement: { label: 'Placement', plural: 'Placements', icon: Building2 },
  entry_level_job: { label: 'Entry-level job', plural: 'Entry-level jobs', icon: Sparkles },
  job: { label: 'Job', plural: 'Jobs', icon: Briefcase },
  volunteering: { label: 'Volunteering', plural: 'Volunteering', icon: HandHeart },
  scholarship: { label: 'Scholarship', plural: 'Scholarships', icon: Medal },
  competition: { label: 'Competition', plural: 'Competitions', icon: Trophy },
  course: { label: 'Course', plural: 'Courses', icon: BookOpen },
  other: { label: 'Other', plural: 'Other', icon: Sparkles },
}
export const SHORTCUT_CATEGORIES: Category[] = ['apprenticeship', 'internship', 'graduate_scheme', 'placement', 'insight_programme', 'work_experience', 'entry_level_job', 'job']

export const ARRANGEMENT: Record<Arrangement, string> = { remote: 'Remote', hybrid: 'Hybrid', in_person: 'In person' }

const money = (n: number) =>
  new Intl.NumberFormat('en-GB', { style: 'currency', currency: 'GBP', maximumFractionDigits: n < 1000 && n % 1 ? 2 : 0 }).format(n)
const PERIOD = { year: 'a year', month: 'a month', week: 'a week', day: 'a day', hour: 'an hour' }

export function formatSalary(o: Pick<Opportunity, 'salary_min' | 'salary_max' | 'salary_period' | 'salary_text'>) {
  if (o.salary_min != null) {
    const range = o.salary_max && o.salary_max !== o.salary_min ? `${money(o.salary_min)} to ${money(o.salary_max)}` : money(o.salary_min)
    return o.salary_period ? `${range} ${PERIOD[o.salary_period]}` : range
  }
  return o.salary_text
}

export function formatAge(o: Pick<Opportunity, 'min_age' | 'max_age'>) {
  if (o.min_age != null && o.max_age != null) return `Age ${o.min_age} to ${o.max_age}`
  if (o.min_age != null) return `Age ${o.min_age}+`
  if (o.max_age != null) return `Age ${o.max_age} or under`
  return null
}
