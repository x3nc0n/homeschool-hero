import { createContext, useContext, useEffect, useMemo, useState } from 'react'
import { api, ApiError } from '@/lib/api'

type AuthContextValue = {
  isAuthenticated: boolean
  loading: boolean
  userName: string
  login: (password: string) => Promise<void>
  logout: () => Promise<void>
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined)

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [loading, setLoading] = useState(true)
  const [isAuthenticated, setIsAuthenticated] = useState(false)
  const [userName, setUserName] = useState('Parent')

  useEffect(() => {
    const bootstrap = async () => {
      try {
        const session = await api.me()
        setIsAuthenticated(Boolean(session.authenticated))
        if (session.user?.name) {
          setUserName(session.user.name)
        }
      } catch (error) {
        if (!(error instanceof ApiError && [401, 403].includes(error.status))) {
          console.error(error)
        }
        setIsAuthenticated(false)
      } finally {
        setLoading(false)
      }
    }

    void bootstrap()
  }, [])

  const value = useMemo(
    () => ({
      isAuthenticated,
      loading,
      userName,
      login: async (password: string) => {
        const session = await api.login(password)
        setIsAuthenticated(Boolean(session.authenticated))
        if (session.user?.name) {
          setUserName(session.user.name)
        }
      },
      logout: async () => {
        await api.logout()
        setIsAuthenticated(false)
      },
    }),
    [isAuthenticated, loading, userName],
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
