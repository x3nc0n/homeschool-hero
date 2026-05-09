import { useCallback, useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import type { NotificationPreference, NotificationType } from '@/types/api'
import { ErrorState } from '@/components/common/ErrorState'
import { LoadingState } from '@/components/common/LoadingState'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { useCapabilities } from '@/context/CapabilitiesContext'
import { api } from '@/lib/api'

const notificationTypes: NotificationType[] = [
  'due_date',
  'grading_complete',
  'backup_status',
  'security_alert',
  'invitation',
  'compliance_reminder',
]

export function NotificationPreferencesPage() {
  const { t } = useTranslation(['common', 'settings'])
  const { capabilities } = useCapabilities()
  const [preferences, setPreferences] = useState<NotificationPreference[]>([])
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')

  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      setPreferences(await api.getNotificationPreferences())
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : t('settings:notifications.errors.load'))
    } finally {
      setLoading(false)
    }
  }, [t])

  useEffect(() => {
    void load()
  }, [load])

  const save = async () => {
    setSaving(true)
    setError('')
    setSuccess('')
    try {
      const updated = await api.updateNotificationPreferences(preferences)
      setPreferences(updated)
      setSuccess(t('settings:notifications.messages.saved'))
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : t('settings:notifications.errors.save'))
    } finally {
      setSaving(false)
    }
  }

  if (loading) return <LoadingState message={t('settings:notifications.loading')} />
  if (error && !preferences.length) return <ErrorState message={error} onRetry={() => void load()} />

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <CardTitle>{t('settings:notifications.title')}</CardTitle>
          <CardDescription>
            {t('settings:notifications.description')}
            {!capabilities.email.enabled ? ` ${t('settings:notifications.emailInactive')}` : ''}
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {(preferences.length ? preferences : notificationTypes.map((notificationType) => ({ notification_type: notificationType, in_app_enabled: false, email_enabled: false }))).map(
            (preference) => (
              <div key={preference.notification_type} className="rounded-xl border p-4">
                <div className="mb-3">
                  <p className="font-medium">{t(`settings:notifications.types.${preference.notification_type}.title`)}</p>
                  <p className="text-sm text-muted-foreground">{t(`settings:notifications.types.${preference.notification_type}.description`)}</p>
                </div>
                <div className="grid gap-3 md:grid-cols-2">
                  <label
                    aria-label={`${t(`settings:notifications.types.${preference.notification_type}.title`)} ${t('settings:notifications.channels.inAppTitle')}`}
                    className="flex items-center gap-3 rounded-lg border p-3"
                  >
                    <input
                      type="checkbox"
                      checked={preference.in_app_enabled}
                      onChange={(event) =>
                        setPreferences((current) =>
                          current.map((item) =>
                            item.notification_type === preference.notification_type ? { ...item, in_app_enabled: event.target.checked } : item,
                          ),
                        )
                      }
                    />
                    <div>
                      <p className="font-medium">{t('settings:notifications.channels.inAppTitle')}</p>
                      <p className="text-sm text-muted-foreground">{t('settings:notifications.channels.inAppDescription')}</p>
                    </div>
                  </label>
                  <label
                    aria-label={`${t(`settings:notifications.types.${preference.notification_type}.title`)} ${t('settings:notifications.channels.emailTitle')}`}
                    className="flex items-center gap-3 rounded-lg border p-3"
                  >
                    <input
                      type="checkbox"
                      checked={preference.email_enabled}
                      onChange={(event) =>
                        setPreferences((current) =>
                          current.map((item) =>
                            item.notification_type === preference.notification_type ? { ...item, email_enabled: event.target.checked } : item,
                          ),
                        )
                      }
                    />
                    <div>
                      <p className="font-medium">{t('settings:notifications.channels.emailTitle')}</p>
                      <p className="text-sm text-muted-foreground">{t('settings:notifications.channels.emailDescription')}</p>
                    </div>
                  </label>
                </div>
              </div>
            ),
          )}
          {error ? <p className="text-sm text-destructive">{error}</p> : null}
          {success ? <p className="text-sm text-primary">{success}</p> : null}
          <div className="flex gap-2">
            <Button onClick={() => void save()} disabled={saving}>
              {saving ? t('common:buttons.save') : t('settings:notifications.actions.save')}
            </Button>
            <Button variant="outline" onClick={() => void load()} disabled={saving}>
              {t('settings:notifications.actions.reset')}
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
