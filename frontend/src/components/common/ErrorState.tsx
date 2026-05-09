import { useTranslation } from 'react-i18next'
import { Button } from '@/components/ui/button'

export function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  const { t } = useTranslation('common')
  return (
    <div role="alert" aria-live="assertive" className="rounded-lg border border-destructive/30 bg-destructive/5 p-5">
      <p className="text-sm text-destructive">{message}</p>
      {onRetry ? (
        <Button className="mt-3" size="sm" variant="outline" onClick={onRetry}>
          {t('buttons.tryAgain')}
        </Button>
      ) : null}
    </div>
  )
}
