import { createContext, useContext, useEffect, useMemo, useState } from 'react'
import type { UserUiPreferences } from '@/types/api'
import { useAuth } from '@/context/AuthContext'
import { api } from '@/lib/api'
import {
  DEFAULT_UI_PREFERENCES,
  getAccentTokens,
  getSystemTheme,
  loadStoredUiPreferences,
  normalizeUserUiPreferences,
  resolveTheme,
  UI_PREFERENCES_STORAGE_KEY,
  type ResolvedTheme,
} from '@/lib/theme'

type ThemeContextValue = {
  preferences: UserUiPreferences
  resolvedTheme: ResolvedTheme
  systemTheme: 'light' | 'dark'
  setPreference: <K extends keyof UserUiPreferences>(key: K, value: UserUiPreferences[K]) => void
  setPreferences: (value: Partial<UserUiPreferences>) => void
  resetPreferences: () => UserUiPreferences
  savePreferences: (nextPreferences?: UserUiPreferences) => Promise<UserUiPreferences>
}

const ThemeContext = createContext<ThemeContextValue | undefined>(undefined)

const fontSizeMap: Record<UserUiPreferences['font_size'], string> = {
  small: '15px',
  medium: '16px',
  large: '18px',
}

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, uiPreferences, setUiPreferences } = useAuth()
  const [preferences, setPreferencesState] = useState<UserUiPreferences>(() => loadStoredUiPreferences())
  const [systemTheme, setSystemTheme] = useState<'light' | 'dark'>(() => getSystemTheme())

  const resolvedTheme = useMemo(() => resolveTheme(preferences.theme, systemTheme), [preferences.theme, systemTheme])

  useEffect(() => {
    const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)')
    const update = () => setSystemTheme(mediaQuery.matches ? 'dark' : 'light')
    update()
    mediaQuery.addEventListener('change', update)
    return () => mediaQuery.removeEventListener('change', update)
  }, [])

  useEffect(() => {
    if (!isAuthenticated || !uiPreferences) return
    setPreferencesState(normalizeUserUiPreferences(uiPreferences))
  }, [isAuthenticated, uiPreferences])

  useEffect(() => {
    window.localStorage.setItem(UI_PREFERENCES_STORAGE_KEY, JSON.stringify(preferences))
  }, [preferences])

  useEffect(() => {
    const root = document.documentElement
    const accentTokens = getAccentTokens(preferences.accent_color)
    root.classList.toggle('dark', resolvedTheme !== 'light')
    root.classList.toggle('theme-high-contrast', resolvedTheme === 'high-contrast')
    root.dataset.theme = resolvedTheme
    root.dataset.density = preferences.density
    root.dataset.sidebarPosition = preferences.sidebar_position
    root.style.setProperty('--font-size-base', fontSizeMap[preferences.font_size])
    root.style.setProperty('--primary', accentTokens.primary)
    root.style.setProperty('--ring', accentTokens.ring)
    root.style.setProperty('--primary-foreground', accentTokens.primaryForeground)
  }, [preferences, resolvedTheme])

  const value = useMemo<ThemeContextValue>(
    () => ({
      preferences,
      resolvedTheme,
      systemTheme,
      setPreference: (key, value) => {
        setPreferencesState((current) => normalizeUserUiPreferences({ ...current, [key]: value }))
      },
      setPreferences: (value) => {
        setPreferencesState((current) => normalizeUserUiPreferences({ ...current, ...value }))
      },
      resetPreferences: () => {
        setPreferencesState(DEFAULT_UI_PREFERENCES)
        return DEFAULT_UI_PREFERENCES
      },
      savePreferences: async (nextPreferences) => {
        const normalized = normalizeUserUiPreferences(nextPreferences ?? preferences)
        setPreferencesState(normalized)
        if (!isAuthenticated) {
          return normalized
        }
        const saved = normalizeUserUiPreferences(await api.updateUserPreferences(normalized))
        setPreferencesState(saved)
        setUiPreferences(saved)
        return saved
      },
    }),
    [isAuthenticated, preferences, resolvedTheme, setUiPreferences, systemTheme],
  )

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>
}

export function useTheme() {
  const context = useContext(ThemeContext)
  if (!context) {
    throw new Error('useTheme must be used within ThemeProvider')
  }
  return context
}
