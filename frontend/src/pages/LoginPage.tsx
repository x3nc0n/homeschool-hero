import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useSearchParams } from 'react-router-dom'
import { ArrowRightCircle, Lock } from 'lucide-react'
import { useAuth } from '@/context/AuthContext'
import { useCapabilities } from '@/context/CapabilitiesContext'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { api } from '@/lib/api'

export function LoginPage() {
  const { t } = useTranslation('auth')
  const { login, bootstrapRequired } = useAuth()
  const { auth } = useCapabilities()
  const [searchParams] = useSearchParams()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [error, setError] = useState('')
  const providerError = searchParams.get('error') || ''
  const showLocalLogin = auth.local_enabled
  const showOidc = auth.oidc_enabled
  const showSaml = auth.saml_enabled

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault()
    setError('')
    setIsSubmitting(true)

    try {
      await login(email, password)
    } catch (loginError) {
      setError(loginError instanceof Error ? loginError.message : t('login.error'))
    } finally {
      setIsSubmitting(false)
    }
  }

  const handleExternalLogin = (provider: 'oidc' | 'saml') => {
    window.location.href = api.getExternalAuthUrl(provider)
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-muted/30 px-4">
      <Card className="w-full max-w-md shadow-lg">
        <CardHeader>
          <CardTitle className="text-2xl">{t('login.title')}</CardTitle>
          <CardDescription>
            {showOidc || showSaml ? t('login.descriptionProviders') : t('login.descriptionDefault')}
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            {showOidc ? (
              <Button className="w-full" type="button" variant="outline" onClick={() => handleExternalLogin('oidc')}>
                <ArrowRightCircle className="mr-2 h-4 w-4" />
                {t('login.oidc')}
              </Button>
            ) : null}
            {showSaml ? (
              <Button className="w-full" type="button" variant="outline" onClick={() => handleExternalLogin('saml')}>
                <ArrowRightCircle className="mr-2 h-4 w-4" />
                {t('login.saml')}
              </Button>
            ) : null}
            {showLocalLogin && (showOidc || showSaml) ? (
              <p className="text-center text-xs uppercase tracking-wide text-muted-foreground">{t('login.orLocal')}</p>
            ) : null}
            {showLocalLogin ? (
              <form className="space-y-4" onSubmit={(event) => void handleSubmit(event)}>
                <div className="space-y-2">
                  <Label htmlFor="email">{t('login.email')}</Label>
                  <Input
                    id="email"
                    type="email"
                    autoComplete="email"
                    value={email}
                    onChange={(event) => setEmail(event.target.value)}
                    placeholder={t('login.emailPlaceholder')}
                    required
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="password">{t('login.password')}</Label>
                  <Input
                    id="password"
                    type="password"
                    autoComplete="current-password"
                    value={password}
                    onChange={(event) => setPassword(event.target.value)}
                    placeholder={t('login.passwordPlaceholder')}
                    required
                  />
                </div>
                {error ? <p className="text-sm text-destructive">{error}</p> : null}
                <Button className="w-full" type="submit" disabled={isSubmitting}>
                  <Lock className="mr-2 h-4 w-4" />
                  {isSubmitting ? t('login.submitting') : t('login.submit')}
                </Button>
              </form>
            ) : null}
            {providerError ? <p className="text-sm text-destructive">{providerError}</p> : null}
            {bootstrapRequired ? (
              <p className="text-sm text-muted-foreground">
                {t('login.bootstrapPrompt')}{' '}
                <Link className="font-medium text-primary underline-offset-4 hover:underline" to="/setup">
                  {t('login.bootstrapLink')}
                </Link>
              </p>
            ) : null}
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
