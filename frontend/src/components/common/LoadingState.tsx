import { useTranslation } from 'react-i18next'

export function LoadingState({ message = 'Loading…' }: { message?: string }) {
  const { t } = useTranslation('common')
  return (
    <div role="status" aria-live="polite" className="rounded-lg border bg-card p-8 text-center text-sm text-muted-foreground">
      {message || t('loadingSession')}
    </div>
  )
}
