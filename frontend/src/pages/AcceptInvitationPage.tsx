import { useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { useAuth } from '@/context/AuthContext'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'

export function AcceptInvitationPage() {
  const { t } = useTranslation('auth')
  const navigate = useNavigate()
  const { invitationId } = useParams()
  const [searchParams] = useSearchParams()
  const { acceptInvitation } = useAuth()
  const [email, setEmail] = useState('')
  const [displayName, setDisplayName] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [submitting, setSubmitting] = useState(false)

  const token = useMemo(() => searchParams.get('token') || '', [searchParams])

  const handleSubmit = async () => {
    if (!invitationId || !token) {
      setError(t('invite.missingLink'))
      return
    }

    setSubmitting(true)
    setError('')
    try {
      await acceptInvitation(Number(invitationId), {
        token,
        email,
        display_name: displayName,
        password,
      })
      navigate('/dashboard', { replace: true })
    } catch (acceptError) {
      setError(acceptError instanceof Error ? acceptError.message : t('invite.error'))
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-muted/20 px-4">
      <Card className="w-full max-w-lg">
        <CardHeader>
          <CardTitle>{t('invite.title')}</CardTitle>
          <CardDescription>{t('invite.description')}</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <Label>{t('invite.email')}</Label>
            <Input value={email} onChange={(event) => setEmail(event.target.value)} />
          </div>
          <div className="space-y-2">
            <Label>{t('invite.displayName')}</Label>
            <Input value={displayName} onChange={(event) => setDisplayName(event.target.value)} />
          </div>
          <div className="space-y-2">
            <Label>{t('invite.password')}</Label>
            <Input type="password" value={password} onChange={(event) => setPassword(event.target.value)} />
          </div>
          {error ? <p className="text-sm text-destructive">{error}</p> : null}
          <Button className="w-full" disabled={submitting} onClick={() => void handleSubmit()}>
            {t('invite.submit')}
          </Button>
        </CardContent>
      </Card>
    </div>
  )
}
