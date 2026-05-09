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
import { DashboardPage } from '@/pages/DashboardPage'
import { BackupsPage } from '@/pages/BackupsPage'
import { ExportsPage } from '@/pages/ExportsPage'
import { FamilySettingsPage } from '@/pages/FamilySettingsPage'
import { AcceptInvitationPage } from '@/pages/AcceptInvitationPage'
import { AssignmentsPage } from '@/pages/AssignmentsPage'
import { AttendancePage } from '@/pages/AttendancePage'
import { AuditLogPage } from '@/pages/AuditLogPage'
import { CalendarPage } from '@/pages/CalendarPage'
import { CompliancePage } from '@/pages/CompliancePage'
import { ComplianceReportsPage } from '@/pages/ComplianceReportsPage'
import { CurriculumPage } from '@/pages/CurriculumPage'
import { GradesPage } from '@/pages/GradesPage'
import { InvitationsPage } from '@/pages/InvitationsPage'
import { ImportsPage } from '@/pages/ImportsPage'
import { LessonPlansPage } from '@/pages/LessonPlansPage'
import { LoginPage } from '@/pages/LoginPage'
import { NotificationPreferencesPage } from '@/pages/NotificationPreferencesPage'
import { NotificationsPage } from '@/pages/NotificationsPage'
import { NotFoundPage } from '@/pages/NotFoundPage'
import { PlannerPage } from '@/pages/PlannerPage'
import { PortfolioPage } from '@/pages/PortfolioPage'
import { PortfolioSharePage } from '@/pages/PortfolioSharePage'
import { QuizzesPage } from '@/pages/QuizzesPage'
import { ReportCardsPage } from '@/pages/ReportCardsPage'
import { RestorePage } from '@/pages/RestorePage'
import { ReviewQueuePage } from '@/pages/ReviewQueuePage'
import { ReviewDetailPage } from '@/pages/ReviewDetailPage'
import { ResourceLibraryPage } from '@/pages/ResourceLibraryPage'
import { SearchPage } from '@/pages/SearchPage'
import { SetupPage } from '@/pages/SetupPage'
import { StudentsPage } from '@/pages/StudentsPage'
import { StudentDetailPage } from '@/pages/StudentDetailPage'
import { SubjectsPage } from '@/pages/SubjectsPage'
import { TranscriptsPage } from '@/pages/TranscriptsPage'
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
  return '/'
}

function RoleRoute({ allowedRoles, element }: { allowedRoles: FamilyRole[]; element: JSX.Element }) {
  const { role } = useAuth()
  if (!role || !allowedRoles.includes(role)) {
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
        <Route path="/" element={<DashboardPage />} />
        <Route path="/dashboard" element={<Navigate to="/" replace />} />
        <Route path="/students" element={<RoleRoute allowedRoles={['parent', 'co-parent', 'tutor']} element={<StudentsPage />} />} />
        <Route
          path="/students/:studentId"
          element={<RoleRoute allowedRoles={['parent', 'co-parent', 'tutor', 'student_viewer']} element={<StudentDetailPage />} />}
        />
        <Route path="/subjects" element={<RoleRoute allowedRoles={['parent', 'co-parent', 'tutor']} element={<SubjectsPage />} />} />
        <Route path="/calendar" element={<RoleRoute allowedRoles={['parent', 'co-parent', 'tutor']} element={<CalendarPage />} />} />
        <Route path="/attendance" element={<RoleRoute allowedRoles={['parent', 'co-parent', 'tutor']} element={<AttendancePage />} />} />
        <Route path="/compliance" element={<RoleRoute allowedRoles={['parent', 'co-parent', 'tutor', 'student_viewer']} element={<CompliancePage />} />} />
        <Route path="/compliance-reports" element={<RoleRoute allowedRoles={['parent', 'co-parent', 'tutor', 'student_viewer']} element={<ComplianceReportsPage />} />} />
        <Route path="/planner" element={<RoleRoute allowedRoles={['parent', 'co-parent', 'tutor', 'student_viewer']} element={<PlannerPage />} />} />
        <Route path="/lesson-plans" element={<RoleRoute allowedRoles={['parent', 'co-parent', 'tutor', 'student_viewer']} element={<LessonPlansPage />} />} />
        <Route path="/curriculum" element={<RoleRoute allowedRoles={['parent', 'co-parent', 'tutor']} element={<CurriculumPage />} />} />
        <Route path="/exports" element={<RoleRoute allowedRoles={['parent', 'co-parent']} element={<ExportsPage />} />} />
        <Route path="/settings/backups" element={<RoleRoute allowedRoles={['parent', 'co-parent']} element={<BackupsPage />} />} />

        <Route path="/settings/restore" element={<RoleRoute allowedRoles={['parent', 'co-parent']} element={<RestorePage />} />} />

        <Route path="/imports" element={<RoleRoute allowedRoles={['parent', 'co-parent', 'tutor']} element={<ImportsPage />} />} />
        <Route path="/resources" element={<RoleRoute allowedRoles={['parent', 'co-parent', 'tutor']} element={<ResourceLibraryPage />} />} />
        <Route path="/portfolio" element={<RoleRoute allowedRoles={['parent', 'co-parent', 'tutor', 'student_viewer']} element={<PortfolioPage />} />} />
        <Route path="/search" element={<RoleRoute allowedRoles={['parent', 'co-parent', 'tutor', 'student_viewer']} element={<SearchPage />} />} />
        <Route path="/assignments" element={<RoleRoute allowedRoles={['parent', 'co-parent', 'tutor', 'student_viewer']} element={<AssignmentsPage />} />} />
        <Route path="/upload" element={<RoleRoute allowedRoles={['parent', 'co-parent', 'tutor']} element={<UploadPage />} />} />
        <Route path="/grades" element={<RoleRoute allowedRoles={['parent', 'co-parent', 'tutor', 'student_viewer']} element={<GradesPage />} />} />
        <Route path="/report-cards" element={<RoleRoute allowedRoles={['parent', 'co-parent', 'tutor', 'student_viewer']} element={<ReportCardsPage />} />} />
        <Route path="/transcripts" element={<RoleRoute allowedRoles={['parent', 'co-parent', 'tutor', 'student_viewer']} element={<TranscriptsPage />} />} />
        <Route path="/quizzes" element={<RoleRoute allowedRoles={['parent', 'co-parent', 'tutor']} element={<QuizzesPage />} />} />
        <Route path="/review" element={<RoleRoute allowedRoles={['parent', 'co-parent', 'tutor']} element={<ReviewQueuePage />} />} />
        <Route path="/review/:reviewId" element={<RoleRoute allowedRoles={['parent', 'co-parent', 'tutor']} element={<ReviewDetailPage />} />} />
        <Route path="/invitations" element={<RoleRoute allowedRoles={['parent', 'co-parent']} element={<InvitationsPage />} />} />
        <Route path="/audit" element={<RoleRoute allowedRoles={['parent', 'co-parent']} element={<AuditLogPage />} />} />
        <Route path="/notifications" element={<NotificationsPage />} />
        <Route path="/settings/family" element={<RoleRoute allowedRoles={['parent', 'co-parent']} element={<FamilySettingsPage />} />} />
        <Route path="/settings/appearance" element={<AppearanceSettingsPage />} />
        <Route path="/settings/notifications" element={<NotificationPreferencesPage />} />
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
