export const LANGUAGE_STORAGE_KEY = 'homeschool-language'

export type AppLanguage = 'en' | 'es'

export const SUPPORTED_LANGUAGES: AppLanguage[] = ['en', 'es']
export const DEFAULT_LANGUAGE: AppLanguage = 'en'

export function normalizeLanguage(value?: string | null): AppLanguage {
  const primary = value?.trim().toLowerCase().split('-')[0]
  return primary === 'es' ? 'es' : DEFAULT_LANGUAGE
}

export function persistLanguage(value: string) {
  const language = normalizeLanguage(value)
  if (typeof window !== 'undefined') {
    window.localStorage.setItem(LANGUAGE_STORAGE_KEY, language)
  }
  if (typeof document !== 'undefined') {
    document.documentElement.lang = language
  }
  return language
}

export function getInitialLanguage(): AppLanguage {
  if (typeof window === 'undefined') {
    return DEFAULT_LANGUAGE
  }

  const stored = window.localStorage.getItem(LANGUAGE_STORAGE_KEY)
  if (stored) {
    return normalizeLanguage(stored)
  }

  return normalizeLanguage(window.navigator.language)
}

export function getCurrentLanguage(): AppLanguage {
  if (typeof document !== 'undefined' && document.documentElement.lang) {
    return normalizeLanguage(document.documentElement.lang)
  }
  return getInitialLanguage()
}

export function formatDate(value: string | number | Date | null | undefined, locale = DEFAULT_LANGUAGE, options: Intl.DateTimeFormatOptions = { dateStyle: 'medium' }) {
  if (!value) return '—'
  const date = value instanceof Date ? value : new Date(value)
  return Number.isNaN(date.getTime()) ? '—' : new Intl.DateTimeFormat(normalizeLanguage(locale), options).format(date)
}

export function formatDateTime(
  value: string | number | Date | null | undefined,
  locale = DEFAULT_LANGUAGE,
  options: Intl.DateTimeFormatOptions = { dateStyle: 'medium', timeStyle: 'short' },
) {
  if (!value) return '—'
  const date = value instanceof Date ? value : new Date(value)
  return Number.isNaN(date.getTime()) ? '—' : new Intl.DateTimeFormat(normalizeLanguage(locale), options).format(date)
}

export function formatTimeOfDay(value: string | null | undefined, locale = DEFAULT_LANGUAGE) {
  if (!value) return '—'
  const [hours, minutes] = value.split(':').map(Number)
  if (Number.isNaN(hours) || Number.isNaN(minutes)) return value
  return new Intl.DateTimeFormat(normalizeLanguage(locale), { hour: 'numeric', minute: '2-digit' }).format(new Date(2000, 0, 1, hours, minutes))
}
