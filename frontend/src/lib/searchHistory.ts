const RECENT_SEARCHES_KEY = 'homeschool-hero.recent-searches'
const MAX_RECENT_SEARCHES = 8

export function getRecentSearches() {
  if (typeof window === 'undefined') return []
  try {
    const parsed = JSON.parse(window.localStorage.getItem(RECENT_SEARCHES_KEY) || '[]') as unknown
    return Array.isArray(parsed) ? parsed.filter((item): item is string => typeof item === 'string') : []
  } catch {
    return []
  }
}

export function storeRecentSearch(query: string) {
  const normalized = query.trim()
  if (!normalized || typeof window === 'undefined') return
  const existing = getRecentSearches().filter((item) => item.toLowerCase() !== normalized.toLowerCase())
  window.localStorage.setItem(RECENT_SEARCHES_KEY, JSON.stringify([normalized, ...existing].slice(0, MAX_RECENT_SEARCHES)))
}
