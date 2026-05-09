import type { ThemePreference, UserUiPreferences } from '@/types/api'

export type ResolvedTheme = 'light' | 'dark' | 'high-contrast'
type SystemTheme = 'light' | 'dark'

export const UI_PREFERENCES_STORAGE_KEY = 'homeschool-ui-preferences'

export const DEFAULT_UI_PREFERENCES: UserUiPreferences = {
  theme: 'system',
  accent_color: '#2563eb',
  font_size: 'medium',
  density: 'comfortable',
  sidebar_position: 'left',
}

export function normalizeHexColor(value?: string | null) {
  const normalized = value?.trim().toLowerCase() || DEFAULT_UI_PREFERENCES.accent_color
  if (/^#[0-9a-f]{3}$/i.test(normalized)) {
    return `#${normalized
      .slice(1)
      .split('')
      .map((character) => `${character}${character}`)
      .join('')}`
  }
  if (/^#[0-9a-f]{6}$/i.test(normalized)) {
    return normalized
  }
  return DEFAULT_UI_PREFERENCES.accent_color
}

export function normalizeUserUiPreferences(value?: Partial<UserUiPreferences> | null): UserUiPreferences {
  return {
    theme: ['light', 'dark', 'high-contrast', 'system'].includes(value?.theme || '') ? (value?.theme as ThemePreference) : DEFAULT_UI_PREFERENCES.theme,
    accent_color: normalizeHexColor(value?.accent_color),
    font_size: ['small', 'medium', 'large'].includes(value?.font_size || '') ? value!.font_size! : DEFAULT_UI_PREFERENCES.font_size,
    density: ['compact', 'comfortable'].includes(value?.density || '') ? value!.density! : DEFAULT_UI_PREFERENCES.density,
    sidebar_position: ['left', 'right', 'collapsed'].includes(value?.sidebar_position || '')
      ? value!.sidebar_position!
      : DEFAULT_UI_PREFERENCES.sidebar_position,
  }
}

export function loadStoredUiPreferences() {
  if (typeof window === 'undefined') return DEFAULT_UI_PREFERENCES
  try {
    return normalizeUserUiPreferences(JSON.parse(window.localStorage.getItem(UI_PREFERENCES_STORAGE_KEY) || 'null') as Partial<UserUiPreferences> | null)
  } catch {
    return DEFAULT_UI_PREFERENCES
  }
}

export function getSystemTheme(): SystemTheme {
  if (typeof window === 'undefined') return 'light'
  return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
}

export function resolveTheme(theme: ThemePreference, systemTheme: SystemTheme): ResolvedTheme {
  if (theme === 'system') {
    return systemTheme
  }
  return theme
}

function hexToRgb(color: string) {
  const normalized = normalizeHexColor(color)
  return {
    r: Number.parseInt(normalized.slice(1, 3), 16),
    g: Number.parseInt(normalized.slice(3, 5), 16),
    b: Number.parseInt(normalized.slice(5, 7), 16),
  }
}

function rgbToHsl({ r, g, b }: { r: number; g: number; b: number }) {
  const red = r / 255
  const green = g / 255
  const blue = b / 255
  const max = Math.max(red, green, blue)
  const min = Math.min(red, green, blue)
  const lightness = (max + min) / 2
  const delta = max - min

  if (delta === 0) {
    return { h: 0, s: 0, l: +(lightness * 100).toFixed(1) }
  }

  const saturation = lightness > 0.5 ? delta / (2 - max - min) : delta / (max + min)
  let hue: number

  switch (max) {
    case red:
      hue = (green - blue) / delta + (green < blue ? 6 : 0)
      break
    case green:
      hue = (blue - red) / delta + 2
      break
    default:
      hue = (red - green) / delta + 4
      break
  }

  return {
    h: +(hue * 60).toFixed(1),
    s: +(saturation * 100).toFixed(1),
    l: +(lightness * 100).toFixed(1),
  }
}

function relativeLuminance({ r, g, b }: { r: number; g: number; b: number }) {
  const convert = (value: number) => {
    const normalized = value / 255
    return normalized <= 0.03928 ? normalized / 12.92 : ((normalized + 0.055) / 1.055) ** 2.4
  }

  return 0.2126 * convert(r) + 0.7152 * convert(g) + 0.0722 * convert(b)
}

export function getAccentTokens(accentColor: string) {
  const hsl = rgbToHsl(hexToRgb(accentColor))
  const foreground = relativeLuminance(hexToRgb(accentColor)) > 0.45 ? '222.2 47.4% 11.2%' : '210 40% 98%'

  return {
    primary: `${hsl.h} ${Math.max(hsl.s, 55)}% ${Math.min(Math.max(hsl.l, 35), 58)}%`,
    ring: `${hsl.h} ${Math.max(hsl.s, 55)}% ${Math.min(Math.max(hsl.l, 40), 60)}%`,
    primaryForeground: foreground,
  }
}
