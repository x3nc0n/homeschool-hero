import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { cn } from '@/lib/utils'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'

const STORAGE_KEY = 'homeschool-hero.language'
const languageOptions = [
  { value: 'en', label: 'English' },
  { value: 'es', label: 'Español' },
]

export function LanguageSelector({ className }: { className?: string }) {
  const { t, i18n } = useTranslation('settings')
  const [language, setLanguage] = useState(i18n.resolvedLanguage || i18n.language || 'en')

  useEffect(() => {
    const stored = window.localStorage.getItem(STORAGE_KEY)
    if (!stored) return
    setLanguage(stored)
    if (stored !== i18n.resolvedLanguage && stored !== i18n.language) {
      void i18n.changeLanguage(stored)
    }
  }, [i18n])

  const handleLanguageChange = async (nextLanguage: string) => {
    setLanguage(nextLanguage)
    window.localStorage.setItem(STORAGE_KEY, nextLanguage)
    await i18n.changeLanguage(nextLanguage)
  }

  return (
    <div className={cn('space-y-2', className)}>
      <Label htmlFor="language-selector">{t('settings:language.label', 'Display language')}</Label>
      <Select value={language} onValueChange={(value) => void handleLanguageChange(value)}>
        <SelectTrigger id="language-selector" aria-describedby="language-selector-help">
          <SelectValue placeholder={t('settings:language.placeholder', 'Choose a language')} />
        </SelectTrigger>
        <SelectContent>
          {languageOptions.map((option) => (
            <SelectItem key={option.value} value={option.value}>
              {option.label}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
      <p id="language-selector-help" className="text-xs text-muted-foreground">
        {t('settings:language.help', 'Language changes apply immediately for translated text that is available.')}
      </p>
    </div>
  )
}
