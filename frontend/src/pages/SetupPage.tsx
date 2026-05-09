import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useAuth } from '@/context/AuthContext'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'

export function SetupPage() {
  const { t } = useTranslation('auth')
  const { register } = useAuth()
  const [familyName, setFamilyName] = useState('My Family')
  const [displayName, setDisplayName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [error, setError] = useState('')

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault()
    setError('')

    if (password !== confirmPassword) {
      setError(t('setup.passwordMismatch'))
      return
    }

    setIsSubmitting(true)
    try {
      await register({
        family_name: familyName,
        display_name: displayName,
        email,
        password,
        timezone: 'UTC',
        grading_scale: 'letter',
      })
    } catch (registerError) {
      setError(registerError instanceof Error ? registerError.message : t('setup.error'))
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-muted/30 px-4">
      <Card className="w-full max-w-lg shadow-lg">
        <CardHeader>
          <CardTitle className="text-2xl">{t('setup.title')}</CardTitle>
          <CardDescription>{t('setup.description')}</CardDescription>
        </CardHeader>
        <CardContent>
          <form className="space-y-4" onSubmit={(event) => void handleSubmit(event)}>
            <div className="space-y-2">
              <Label htmlFor="familyName">{t('setup.familyName')}</Label>
              <Input id="familyName" value={familyName} onChange={(event) => setFamilyName(event.target.value)} required />
            </div>
            <div className="space-y-2">
              <Label htmlFor="displayName">{t('setup.yourName')}</Label>
              <Input id="displayName" value={displayName} onChange={(event) => setDisplayName(event.target.value)} required />
            </div>
            <div className="space-y-2">
              <Label htmlFor="email">{t('setup.email')}</Label>
              <Input id="email" type="email" value={email} onChange={(event) => setEmail(event.target.value)} required />
            </div>
            <div className="space-y-2">
              <Label htmlFor="password">{t('setup.password')}</Label>
              <Input
                id="password"
                type="password"
                autoComplete="new-password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                minLength={8}
                required
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="confirmPassword">{t('setup.confirmPassword')}</Label>
              <Input
                id="confirmPassword"
                type="password"
                autoComplete="new-password"
                value={confirmPassword}
                onChange={(event) => setConfirmPassword(event.target.value)}
                minLength={8}
                required
              />
            </div>
            {error ? <p className="text-sm text-destructive">{error}</p> : null}
            <Button className="w-full" type="submit" disabled={isSubmitting}>
              {isSubmitting ? t('setup.submitting') : t('setup.submit')}
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  )
}
