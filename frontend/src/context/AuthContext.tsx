import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import type { AcceptInvitationPayload, AppRole, AuthSession, FamilyRole, RegisterPayload, UserUiPreferences } from '@/types/api'
import { api, ApiError, AUTH_EXPIRED_EVENT } from '@/lib/api'
import { DEFAULT_UI_PREFERENCES } from '@/lib/theme'

type AuthContextValue = {
  isAuthenticated: boolean
  loading: boolean
  bootstrapRequired: boolean
  userName: string
  familyName: string
  role: FamilyRole | null
  appRoles: AppRole[]
  effectiveCapabilities: string[]
  enabledFeatures: Record<string, boolean>
  isFeatureEnabled: (feature: string) => boolean
  hasCapability: (capability: string) => boolean
  hasRole: (role: string) => boolean
  studentId: number | null
  canEditStudents: boolean
  canManageCurriculum: boolean
  canManageGrading: boolean
  canManageInvitations: boolean
  canViewAuditLog: boolean
  canUploadSubmissions: boolean
  canReviewQueue: boolean
  uiPreferences: UserUiPreferences
  setUiPreferences: (preferences: UserUiPreferences) => void
  login: (email: string, password: string) => Promise<void>
  register: (payload: RegisterPayload) => Promise<void>
  acceptInvitation: (invitationId: number, payload: AcceptInvitationPayload) => Promise<void>
  logout: () => Promise<void>
  refreshSession: () => Promise<void>
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined)

const LEGACY_APP_ROLES: Record<FamilyRole, AppRole[]> = {
  parent: ['admin', 'teacher'],
  'co-parent': ['admin', 'teacher'],
  tutor: ['teacher'],
  student_viewer: ['student'],
}

const LEGACY_CAPABILITIES: Record<FamilyRole, string[]> = {
  parent: [
    'manage_family',
    'manage_household',
    'manage_platform',
    'manage_curriculum',
    'manage_submissions',
    'manage_grading',
    'manage_invitations',
    'manage_security',
    'read_students',
    'read_curriculum',
    'read_submissions',
    'read_grades',
  ],
  'co-parent': [
    'manage_family',
    'manage_household',
    'manage_platform',
    'manage_curriculum',
    'manage_submissions',
    'manage_grading',
    'manage_invitations',
    'read_students',
    'read_curriculum',
    'read_submissions',
    'read_grades',
  ],
  tutor: ['manage_curriculum', 'manage_submissions', 'manage_grading', 'read_students', 'read_curriculum', 'read_submissions', 'read_grades'],
  student_viewer: ['view_own_progress', 'read_students', 'read_curriculum', 'read_submissions', 'read_grades'],
}

const CAPABILITY_ALIASES: Record<string, string[]> = {
  manage_family: ['manage_family', 'manage_household', 'manage_platform'],
  manage_household: ['manage_household', 'manage_family'],
  manage_grading: ['manage_grading', 'grade_assignments'],
  view_own_progress: ['view_own_progress', 'read_grades', 'read_curriculum', 'read_submissions', 'read_students'],
}

function normalizeValues(values: string[] | undefined | null) {
  return Array.from(new Set((values ?? []).map((value) => value.trim().toLowerCase()).filter(Boolean)))
}

function getUserName(session: AuthSession | null) {
  return session?.user.display_name || 'Parent'
}

function getFamilyName(session: AuthSession | null) {
  return session?.family.name || ''
}

function getRole(session: AuthSession | null): FamilyRole | null {
  return session?.membership.role || null
}

function getAppRoles(session: AuthSession | null): AppRole[] {
  const configuredRoles = normalizeValues(session?.app_roles) as AppRole[]
  if (configuredRoles.length) {
    return configuredRoles
  }

  const familyRole = getRole(session)
  return familyRole ? LEGACY_APP_ROLES[familyRole] : []
}

function getEffectiveCapabilities(session: AuthSession | null): string[] {
  const configuredCapabilities = normalizeValues(session?.effective_capabilities)
  if (configuredCapabilities.length) {
    return configuredCapabilities
  }

  const familyRole = getRole(session)
  return familyRole ? LEGACY_CAPABILITIES[familyRole] : []
}

function getEnabledFeatures(session: AuthSession | null): Record<string, boolean> {
  return session?.family.enabled_features ?? {}
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [loading, setLoading] = useState(true)
  const [session, setSession] = useState<AuthSession | null>(null)
  const [bootstrapRequired, setBootstrapRequired] = useState(false)

  const handleSessionExpired = useCallback(() => {
    setSession(null)
    setBootstrapRequired(false)
    setLoading(false)
  }, [])

  const refreshSession = useCallback(async () => {
    const currentSession = await api.me()
    setSession(currentSession)
    setBootstrapRequired(false)
  }, [])

  useEffect(() => {
    const handleAuthExpired = () => {
      handleSessionExpired()
    }

    window.addEventListener(AUTH_EXPIRED_EVENT, handleAuthExpired)
    return () => window.removeEventListener(AUTH_EXPIRED_EVENT, handleAuthExpired)
  }, [handleSessionExpired])

  useEffect(() => {
    const bootstrap = async () => {
      try {
        await refreshSession()
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
  }, [refreshSession])

  const value = useMemo(() => {
    const role = getRole(session)
    const appRoles = getAppRoles(session)
    const effectiveCapabilities = getEffectiveCapabilities(session)
    const enabledFeatures = getEnabledFeatures(session)
    const capabilitySet = new Set(effectiveCapabilities)
    const roleSet = new Set(appRoles)
    const hasCapability = (capability: string) => {
      const candidates = CAPABILITY_ALIASES[capability] ?? [capability]
      return candidates.some((candidate) => capabilitySet.has(candidate))
    }
    const hasRole = (appRole: string) => roleSet.has(appRole.trim().toLowerCase() as AppRole)

    return {
      isAuthenticated: Boolean(session?.authenticated),
      loading,
      bootstrapRequired,
      userName: getUserName(session),
      familyName: getFamilyName(session),
      role,
      appRoles,
      effectiveCapabilities,
      enabledFeatures,
      isFeatureEnabled: (feature: string) => enabledFeatures[feature] !== false,
      hasCapability,
      hasRole,
      studentId: session?.membership.student_id ?? null,
      canEditStudents: hasCapability('manage_household'),
      canManageCurriculum: hasCapability('manage_curriculum'),
      canManageGrading: hasCapability('manage_grading'),
      canManageInvitations: hasCapability('manage_invitations'),
      canViewAuditLog: hasCapability('manage_platform') || hasCapability('manage_security'),
      canUploadSubmissions: hasCapability('manage_submissions'),
      canReviewQueue: hasCapability('manage_grading'),
      uiPreferences: session?.ui_preferences ?? DEFAULT_UI_PREFERENCES,
      setUiPreferences: (preferences: UserUiPreferences) => {
        setSession((current) => (current ? { ...current, ui_preferences: preferences } : current))
      },
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
      acceptInvitation: async (invitationId: number, payload: AcceptInvitationPayload) => {
        const nextSession = await api.acceptInvitation(invitationId, payload)
        setSession(nextSession)
        setBootstrapRequired(false)
      },
      logout: async () => {
        try {
          await api.logout()
        } finally {
          handleSessionExpired()
        }
      },
      refreshSession,
    }
  }, [bootstrapRequired, handleSessionExpired, loading, refreshSession, session])

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const context = useContext(AuthContext)
  if (!context) {
    throw new Error('useAuth must be used inside AuthProvider')
  }
  return context
}
