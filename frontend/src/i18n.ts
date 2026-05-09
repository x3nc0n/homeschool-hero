import i18n from 'i18next'
import { initReactI18next } from 'react-i18next'
import authEn from '@/locales/en/auth.json'
import commonEn from '@/locales/en/common.json'
import dashboardEn from '@/locales/en/dashboard.json'
import settingsEn from '@/locales/en/settings.json'
import commonEs from '@/locales/es/common.json'
import { getInitialLanguage, persistLanguage, SUPPORTED_LANGUAGES } from '@/lib/locale'

export const resources = {
  en: {
    common: commonEn,
    dashboard: dashboardEn,
    auth: authEn,
    settings: settingsEn,
  },
  es: {
    common: commonEs,
  },
} as const

void i18n.use(initReactI18next)
void i18n.init({
  resources,
  lng: getInitialLanguage(),
  fallbackLng: 'en',
  supportedLngs: SUPPORTED_LANGUAGES,
  ns: ['common', 'dashboard', 'auth', 'settings'],
  defaultNS: 'common',
  fallbackNS: 'common',
  interpolation: { escapeValue: false },
  partialBundledLanguages: true,
  returnNull: false,
})

persistLanguage(i18n.resolvedLanguage || i18n.language)
i18n.on('languageChanged', (language) => {
  persistLanguage(language)
})

export default i18n
