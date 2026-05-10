import { useEffect, useState } from 'react'
import { Navigate, Route, Routes } from 'react-router-dom'
import type { FamilyRole, MaintenanceStatus } from '@/types/api'
import { AccessibilityEnhancer } from '@/components/common/AccessibilityEnhancer'
import { AppShell } from '@/components/layout/AppShell'
import { AuthProvider, useAuth } from '@/context/AuthContext'
import { CapabilitiesProvider } from '@/context/CapabilitiesContext'
import { NotificationsProvider } from '@/context/NotificationsContext'
import { PwaProvider } from '@/context/PwaContext'
import { ThemeProvider } from '@/context/ThemeContext'
import { api, MAINTENANCE_EVENT } from '@/lib/api'
import { AppearanceSettingsPage } from '@/pages/AppearanceSettingsPage'
import AcademicRecordsPage from '@/pages/AcademicRecordsPage'
import { DashboardPage } from '@/pages/DashboardPage'
import CurriculumHubPage from '@/pages/CurriculumHubPage'
import DataManagementPage from '@/pages/DataManagementPage'
import { FamilySettingsPage } from '@/pages/FamilySettingsPage'
import GradebookPage from '@/pages/GradebookPage'
import { AcceptInvitationPage } from '@/pages/AcceptInvitationPage'
import { AssignmentsPage } from '@/pages/AssignmentsPage'
import { AttendancePage } from '@/pages/AttendancePage'
import { AuditLogPage } from '@/pages/AuditLogPage'
import { CalendarPage } from '@/pages/CalendarPage'
import { CompliancePage } from '@/pages/CompliancePage'
import { ComplianceReportsPage } from '@/pages/ComplianceReportsPage'
import { InvitationsPage } from '@/pages/InvitationsPage'
import { LoginPage } from '@/pages/LoginPage'
import { NotificationPreferencesPage } from '@/pages/NotificationPreferencesPage'
import { NotificationsPage } from '@/pages/NotificationsPage'
import { NotFoundPage } from '@/pages/NotFoundPage'
import { PlannerPage } from '@/pages/PlannerPage'
import { PortfolioPage } from '@/pages/PortfolioPage'
import { PortfolioSharePage } from '@/pages/PortfolioSharePage'
import { QuizzesPage } from '@/pages/QuizzesPage'
import { ReviewDetailPage } from '@/pages/ReviewDetailPage'
import { SearchPage } from '@/pages/SearchPage'
import { SetupPage } from '@/pages/SetupPage'
import { StudentsPage } from '@/pages/StudentsPage'
import { StudentDetailPage } from '@/pages/StudentDetailPage'
import { SubjectsPage } from '@/pages/SubjectsPage'
import { UploadPage } from '@/pages/UploadPage'
import { MaintenancePage } from '@/pages/MaintenancePage'
import { StatusPage } from '@/pages/StatusPage'

function LoadingScreen() {
  return (
    <main className="flex min-h-screen items-center justify-center text-muted-foreground">
      <div role="status" aria-live="polite">
        Loading session…
      </div>
    </main>
  )
}

function defaultRouteForRole() {
  return '/dashboard'
}

function RoleRoute({ allowedRoles, element, feature }: { allowedRoles: FamilyRole[]; element: JSX.Element; feature?: string }) {
  const { role, isFeatureEnabled } = useAuth()
  if (!role || !allowedRoles.includes(role)) {
    return <Navigate to={defaultRouteForRole()} replace />
  }
  if (feature && !isFeatureEnabled(feature)) {
    return <Navigate to={defaultRouteForRole()} replace />
  }
  return element
}

function ProtectedRoutes() {
  const { loading, isAuthenticated, bootstrapRequired } = useAuth()

  if (loading) {
    return <LoadingScreen />
  }

  if (!isAuthenticated) {
    return <Navigate to={bootstrapRequired ? '/setup' : '/login'} replace />
  }

  return (
    <AppShell>
      <Routes>
        <Route path="/" element={<Navigate to="/dashboard" replace />} />
        <Route path="/dashboard" element={<DashboardPage />} />
        <Route path="/students" element={<RoleRoute allowedRoles={['parent', 'co-parent', 'tutor']} element={<StudentsPage />} />} />
        <Route
          path="/students/:studentId"
          element={<RoleRoute allowedRoles={['parent', 'co-parent', 'tutor', 'student_viewer']} element={<StudentDetailPage />} />}
        />
        <Route path="/subjects" element={<RoleRoute allowedRoles={['parent', 'co-parent', 'tutor']} element={<SubjectsPage />} />} />
        <Route path="/calendar" element={<RoleRoute allowedRoles={['parent', 'co-parent', 'tutor']} element={<CalendarPage />} />} />
        <Route
          path="/attendance"
          element={<RoleRoute allowedRoles={['parent', 'co-parent', 'tutor']} feature="attendance" element={<AttendancePage />} />}
        />
        <Route
          path="/compliance"
          element={<RoleRoute allowedRoles={['parent', 'co-parent', 'tutor', 'student_viewer']} feature="compliance" element={<CompliancePage />} />}
        />
        <Route
          path="/compliance-reports"
          element={<RoleRoute allowedRoles={['parent', 'co-parent', 'tutor', 'student_viewer']} feature="compliance" element={<ComplianceReportsPage />} />}
        />
        <Route
          path="/planner"
          element={<RoleRoute allowedRoles={['parent', 'co-parent', 'tutor', 'student_viewer']} feature="planner" element={<PlannerPage />} />}
        />
        <Route path="/curriculum" element={<RoleRoute allowedRoles={['parent', 'co-parent', 'tutor', 'student_viewer']} element={<CurriculumHubPage />} />} />
        <Route
          path="/lesson-plans"
          element={<RoleRoute allowedRoles={['parent', 'co-parent', 'tutor', 'student_viewer']} element={<Navigate to="/curriculum?tab=lesson-plans" replace />} />}
        />
        <Route
          path="/resources"
          element={<RoleRoute allowedRoles={['parent', 'co-parent', 'tutor']} element={<Navigate to="/curriculum?tab=resources" replace />} />}
        />
        <Route
          path="/imports"
          element={<RoleRoute allowedRoles={['parent', 'co-parent', 'tutor']} element={<Navigate to="/data?tab=imports" replace />} />}
        />
        <Route
          path="/exports"
          element={<RoleRoute allowedRoles={['parent', 'co-parent']} element={<Navigate to="/data?tab=exports" replace />} />}
        />
        <Route
          path="/settings/backups"
          element={<RoleRoute allowedRoles={['parent', 'co-parent']} element={<Navigate to="/data?tab=backups" replace />} />}
        />
        <Route
          path="/settings/restore"
          element={<RoleRoute allowedRoles={['parent', 'co-parent']} element={<Navigate to="/data?tab=restore" replace />} />}
        />
        <Route path="/data" element={<RoleRoute allowedRoles={['parent', 'co-parent', 'tutor']} element={<DataManagementPage />} />} />
        <Route
          path="/portfolio"
          element={<RoleRoute allowedRoles={['parent', 'co-parent', 'tutor', 'student_viewer']} feature="portfolio" element={<PortfolioPage />} />}
        />
        <Route path="/search" element={<RoleRoute allowedRoles={['parent', 'co-parent', 'tutor', 'student_viewer']} element={<SearchPage />} />} />
        <Route path="/assignments" element={<RoleRoute allowedRoles={['parent', 'co-parent', 'tutor', 'student_viewer']} element={<AssignmentsPage />} />} />
        <Route path="/upload" element={<RoleRoute allowedRoles={['parent', 'co-parent', 'tutor']} element={<UploadPage />} />} />
        <Route path="/grades" element={<RoleRoute allowedRoles={['parent', 'co-parent', 'tutor', 'student_viewer']} element={<GradebookPage />} />} />
        <Route path="/review" element={<RoleRoute allowedRoles={['parent', 'co-parent', 'tutor']} element={<Navigate to="/grades?tab=review" replace />} />} />
        <Route path="/quizzes" element={<RoleRoute allowedRoles={['parent', 'co-parent', 'tutor']} feature="quizzes" element={<QuizzesPage />} />} />
        <Route path="/review/:reviewId" element={<RoleRoute allowedRoles={['parent', 'co-parent', 'tutor']} element={<ReviewDetailPage />} />} />
        <Route
          path="/academic-records"
          element={<RoleRoute allowedRoles={['parent', 'co-parent', 'tutor', 'student_viewer']} element={<AcademicRecordsPage />} />}
        />
        <Route
          path="/report-cards"
          element={<RoleRoute allowedRoles={['parent', 'co-parent', 'tutor', 'student_viewer']} element={<Navigate to="/academic-records" replace />} />}
        />
        <Route
          path="/transcripts"
          element={<RoleRoute allowedRoles={['parent', 'co-parent', 'tutor', 'student_viewer']} element={<Navigate to="/academic-records?tab=transcripts" replace />} />}
        />
        <Route path="/invitations" element={<RoleRoute allowedRoles={['parent', 'co-parent']} element={<InvitationsPage />} />} />
        <Route path="/audit" element={<RoleRoute allowedRoles={['parent', 'co-parent']} element={<AuditLogPage />} />} />
        <Route path="/notifications" element={<NotificationsPage />} />
        <Route path="/settings/family" element={<RoleRoute allowedRoles={['parent', 'co-parent']} element={<FamilySettingsPage />} />} />
        <Route path="/settings/appearance" element={<AppearanceSettingsPage />} />
        <Route path="/notifications/preferences" element={<NotificationPreferencesPage />} />
        <Route path="/settings/notifications" element={<Navigate to="/notifications/preferences" replace />} />
        <Route path="/settings/status" element={<RoleRoute allowedRoles={['parent', 'co-parent']} element={<StatusPage />} />} />
        <Route path="*" element={<NotFoundPage />} />
      </Routes>
    </AppShell>
  )
}

function LoginRoute() {
  const { isAuthenticated, loading, bootstrapRequired } = useAuth()

  if (loading) {
    return <LoadingScreen />
  }

  if (isAuthenticated) {
    return <Navigate to={defaultRouteForRole()} replace />
  }

  if (bootstrapRequired) {
    return <Navigate to="/setup" replace />
  }

  return <LoginPage />
}

function SetupRoute() {
  const { isAuthenticated, loading, bootstrapRequired } = useAuth()

  if (loading) {
    return <LoadingScreen />
  }

  if (isAuthenticated) {
    return <Navigate to={defaultRouteForRole()} replace />
  }

  if (!bootstrapRequired) {
    return <Navigate to="/login" replace />
  }

  return <SetupPage />
}

function AcceptInvitationRoute() {
  const { isAuthenticated, loading } = useAuth()

  if (loading) {
    return <LoadingScreen />
  }

  if (isAuthenticated) {
    return <Navigate to={defaultRouteForRole()} replace />
  }

  return <AcceptInvitationPage />
}

function AppRoutes() {
  const { role } = useAuth()
  const [maintenance, setMaintenance] = useState<MaintenanceStatus | null>(null)

  useEffect(() => {
    const loadHealth = async () => {
      try {
        const health = await api.getHealth()
        setMaintenance(health.maintenance.active ? health.maintenance : null)
      } catch {
        // Ignore health bootstrap issues here; individual pages already handle fetch failures.
      }
    }

    const handleMaintenance = (event: Event) => {
      const detail = (event as CustomEvent<MaintenanceStatus>).detail
      if (!detail) return
      setMaintenance({
        enabled: Boolean(detail.enabled),
        env_enabled: Boolean(detail.env_enabled),
        active: true,
        scheduled: Boolean(detail.scheduled),
        schedule_active: Boolean(detail.schedule_active),
        message: detail.message || 'Homeschool Hero is temporarily unavailable.',
        source: detail.source || 'server',
        start_at: detail.start_at,
        end_at: detail.end_at,
        updated_at: detail.updated_at,
        updated_by_user_id: detail.updated_by_user_id,
        bypass_roles: detail.bypass_roles || ['parent', 'co-parent'],
      })
    }

    void loadHealth()
    window.addEventListener(MAINTENANCE_EVENT, handleMaintenance as EventListener)
    return () => window.removeEventListener(MAINTENANCE_EVENT, handleMaintenance as EventListener)
  }, [])

  const isAdmin = role === 'parent' || role === 'co-parent'

  if (maintenance?.active && !isAdmin) {
    return (
      <MaintenancePage
        maintenance={maintenance}
        onRetry={() => {
          void api.getHealth().then((health) => {
            if (!health.maintenance.active) {
              window.location.reload()
              return
            }
            setMaintenance(health.maintenance)
          })
        }}
      />
    )
  }

  return (
    <Routes>
      <Route path="/login" element={<LoginRoute />} />
      <Route path="/setup" element={<SetupRoute />} />
      <Route path="/accept-invite/:invitationId" element={<AcceptInvitationRoute />} />
      <Route path="/portfolio/share/:shareToken" element={<PortfolioSharePage />} />
      <Route path="*" element={<ProtectedRoutes />} />
    </Routes>
  )
}

export default function App() {
  return (
    <AuthProvider>
      <ThemeProvider>
        <CapabilitiesProvider>
          <PwaProvider>
            <NotificationsProvider>
              <AccessibilityEnhancer />
              <AppRoutes />
            </NotificationsProvider>
          </PwaProvider>
        </CapabilitiesProvider>
      </ThemeProvider>
    </AuthProvider>
  )
}
