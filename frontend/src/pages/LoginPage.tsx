import { useState } from 'react'
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
      setError(loginError instanceof Error ? loginError.message : 'Unable to sign in')
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
          <CardTitle className="text-2xl">Welcome back</CardTitle>
          <CardDescription>
            {showOidc || showSaml ? 'Choose your sign-in method.' : 'Sign in with your email address and password.'}
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            {showOidc ? (
              <Button className="w-full" type="button" variant="outline" onClick={() => handleExternalLogin('oidc')}>
                <ArrowRightCircle className="mr-2 h-4 w-4" />
                Continue with OIDC
              </Button>
            ) : null}
            {showSaml ? (
              <Button className="w-full" type="button" variant="outline" onClick={() => handleExternalLogin('saml')}>
                <ArrowRightCircle className="mr-2 h-4 w-4" />
                Continue with SAML
              </Button>
            ) : null}
            {showLocalLogin && (showOidc || showSaml) ? (
              <p className="text-center text-xs uppercase tracking-wide text-muted-foreground">or use local sign-in</p>
            ) : null}
            {showLocalLogin ? (
              <form className="space-y-4" onSubmit={(event) => void handleSubmit(event)}>
                <div className="space-y-2">
                  <Label htmlFor="email">Email</Label>
                  <Input
                    id="email"
                    type="email"
                    autoComplete="email"
                    value={email}
                    onChange={(event) => setEmail(event.target.value)}
                    placeholder="parent@example.com"
                    required
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="password">Password</Label>
                  <Input
                    id="password"
                    type="password"
                    autoComplete="current-password"
                    value={password}
                    onChange={(event) => setPassword(event.target.value)}
                    placeholder="••••••••"
                    required
                  />
                </div>
                {error ? <p className="text-sm text-destructive">{error}</p> : null}
                <Button className="w-full" type="submit" disabled={isSubmitting}>
                  <Lock className="mr-2 h-4 w-4" />
                  {isSubmitting ? 'Signing in…' : 'Sign in'}
                </Button>
              </form>
            ) : null}
            {providerError ? <p className="text-sm text-destructive">{providerError}</p> : null}
            {bootstrapRequired ? (
              <p className="text-sm text-muted-foreground">
                Need to create the first family owner?{' '}
                <Link className="font-medium text-primary underline-offset-4 hover:underline" to="/setup">
                  Start setup
                </Link>
              </p>
            ) : null}
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
