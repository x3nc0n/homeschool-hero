import { createContext, useContext, useEffect, useMemo, useState } from 'react'
import type { AuthSession, RegisterPayload } from '@/types/api'
import { api, ApiError } from '@/lib/api'

type AuthContextValue = {
  isAuthenticated: boolean
  loading: boolean
  bootstrapRequired: boolean
  userName: string
  familyName: string
  login: (email: string, password: string) => Promise<void>
  register: (payload: RegisterPayload) => Promise<void>
  logout: () => Promise<void>
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined)

function getUserName(session: AuthSession | null) {
  return session?.user.display_name || 'Parent'
}

function getFamilyName(session: AuthSession | null) {
  return session?.family.name || ''
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [loading, setLoading] = useState(true)
  const [session, setSession] = useState<AuthSession | null>(null)
  const [bootstrapRequired, setBootstrapRequired] = useState(false)

  useEffect(() => {
    const bootstrap = async () => {
      try {
        const currentSession = await api.me()
        setSession(currentSession)
        setBootstrapRequired(false)
      } catch (error) {
        if (error instanceof ApiError && [401, 403].includes(error.status)) {
          try {
            const status = await api.getBootstrapStatus()
            setBootstrapRequired(Boolean(status.bootstrap_required))
          } catch (statusError) {
            console.error(statusError)
            setBootstrapRequired(false)
          }
        } else {
          console.error(error)
          setBootstrapRequired(false)
        }
        setSession(null)
      } finally {
        setLoading(false)
      }
    }

    void bootstrap()
  }, [])

  const value = useMemo(
    () => ({
      isAuthenticated: Boolean(session?.authenticated),
      loading,
      bootstrapRequired,
      userName: getUserName(session),
      familyName: getFamilyName(session),
      login: async (email: string, password: string) => {
        const nextSession = await api.login(email, password)
        setSession(nextSession)
        setBootstrapRequired(false)
      },
      register: async (payload: RegisterPayload) => {
        const nextSession = await api.register(payload)
        setSession(nextSession)
        setBootstrapRequired(false)
      },
      logout: async () => {
        await api.logout()
        setSession(null)
        setBootstrapRequired(false)
      },
    }),
    [bootstrapRequired, loading, session],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const context = useContext(AuthContext)
  if (!context) {
    throw new Error('useAuth must be used inside AuthProvider')
  }
  return context
}
