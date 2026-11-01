import { type ClassValue, clsx } from 'clsx'
import { twMerge } from 'tailwind-merge'

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

const dateFormat = new Intl.DateTimeFormat('en-GB', { day: 'numeric', month: 'short', year: 'numeric' })
const shortDate = new Intl.DateTimeFormat('en-GB', { day: 'numeric', month: 'short' })
const dateTime = new Intl.DateTimeFormat('en-GB', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' })

export const formatDate = (value: string) => dateFormat.format(new Date(value))
export const formatShortDate = (value: string) => shortDate.format(new Date(value))
export const formatDateTime = (value: string) => dateTime.format(new Date(value))

export function timeAgo(value: string) {
  const minutes = Math.round((Date.now() - new Date(value).getTime()) / 60000)
  if (minutes < 1) return 'just now'
  if (minutes < 60) return `${minutes} min ago`
  const hours = Math.round(minutes / 60)
  if (hours < 24) return `${hours} hr ago`
  const days = Math.round(hours / 24)
  return days === 1 ? 'yesterday' : `${days} days ago`
}

/** Links come from scanned pages, so only ever follow web addresses (never javascript: and the like). */
export function safeUrl(...candidates: (string | null | undefined)[]) {
  for (const candidate of candidates) {
    try {
      if (candidate && ['http:', 'https:'].includes(new URL(candidate).protocol)) return candidate
    } catch {
      // not a valid address, so try the next one
    }
  }
  return undefined
}

/** Names where a link really goes: many adverts apply through a recruiter rather than the employer. */
export function applyLabel(url: string | undefined) {
  if (!url) return 'Apply'
  const host = new URL(url).hostname.replace(/^www\./, '')
  return host.endsWith('service.gov.uk') ? 'Apply on GOV.UK' : `Apply on ${host}`
}

export const formatCount = (n: number) => new Intl.NumberFormat('en-GB').format(n)

export function daysUntil(value: string) {
  const end = new Date(`${value.slice(0, 10)}T23:59:59`)
  return Math.ceil((end.getTime() - Date.now()) / 86400000)
}
