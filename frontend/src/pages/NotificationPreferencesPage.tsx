import { useCallback, useEffect, useState } from 'react'
import type { NotificationPreference, NotificationType } from '@/types/api'
import { api } from '@/lib/api'
import { useCapabilities } from '@/context/CapabilitiesContext'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { LoadingState } from '@/components/common/LoadingState'
import { ErrorState } from '@/components/common/ErrorState'

const labels: Record<NotificationType, { title: string; description: string }> = {
  due_date: { title: 'Due dates', description: 'Upcoming assignment due dates and reminders.' },
  grading_complete: { title: 'Grading updates', description: 'Completed grades and review-ready grading items.' },
  backup_status: { title: 'Backup status', description: 'Missing or stale backups that need attention.' },
  security_alert: { title: 'Security alerts', description: 'Important sign-in and account lockout notifications.' },
  invitation: { title: 'Invitations', description: 'Family invitation creation and acceptance updates.' },
  compliance_reminder: { title: 'Compliance reminders', description: 'Operational reminders that need follow-up.' },
}

export function NotificationPreferencesPage() {
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
      setError(loadError instanceof Error ? loadError.message : 'Unable to load notification preferences')
    } finally {
      setLoading(false)
    }
  }, [])

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
      setSuccess('Notification preferences saved.')
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : 'Unable to save notification preferences')
    } finally {
      setSaving(false)
    }
  }

  if (loading) return <LoadingState message="Loading notification preferences…" />
  if (error && !preferences.length) return <ErrorState message={error} onRetry={() => void load()} />

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <CardTitle>Notification preferences</CardTitle>
          <CardDescription>
            Choose which updates stay in-app and which can also be sent by email.
            {!capabilities.email.enabled ? ' Email delivery will stay inactive until SMTP is configured.' : ''}
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {preferences.map((preference) => (
            <div key={preference.notification_type} className="rounded-xl border p-4">
              <div className="mb-3">
                <p className="font-medium">{labels[preference.notification_type].title}</p>
                <p className="text-sm text-muted-foreground">{labels[preference.notification_type].description}</p>
              </div>
              <div className="grid gap-3 md:grid-cols-2">
                <label className="flex items-center gap-3 rounded-lg border p-3">
                  <input
                    type="checkbox"
                    checked={preference.in_app_enabled}
                    onChange={(event) =>
                      setPreferences((current) =>
                        current.map((item) =>
                          item.notification_type === preference.notification_type
                            ? { ...item, in_app_enabled: event.target.checked }
                            : item,
                        ),
                      )
                    }
                  />
                  <div>
                    <p className="font-medium">In-app</p>
                    <p className="text-sm text-muted-foreground">Show this notification in the app.</p>
                  </div>
                </label>
                <label className="flex items-center gap-3 rounded-lg border p-3">
                  <input
                    type="checkbox"
                    checked={preference.email_enabled}
                    onChange={(event) =>
                      setPreferences((current) =>
                        current.map((item) =>
                          item.notification_type === preference.notification_type
                            ? { ...item, email_enabled: event.target.checked }
                            : item,
                        ),
                      )
                    }
                  />
                  <div>
                    <p className="font-medium">Email</p>
                    <p className="text-sm text-muted-foreground">Send an email when this notification type fires.</p>
                  </div>
                </label>
              </div>
            </div>
          ))}
          {error ? <p className="text-sm text-destructive">{error}</p> : null}
          {success ? <p className="text-sm text-primary">{success}</p> : null}
          <div className="flex gap-2">
            <Button onClick={() => void save()} disabled={saving}>
              {saving ? 'Saving…' : 'Save preferences'}
            </Button>
            <Button variant="outline" onClick={() => void load()} disabled={saving}>
              Reset
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
