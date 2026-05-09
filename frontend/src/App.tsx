import { Navigate, Route, Routes } from 'react-router-dom'
import type { FamilyRole } from '@/types/api'
import { AppShell } from '@/components/layout/AppShell'
import { AuthProvider, useAuth } from '@/context/AuthContext'
import { CapabilitiesProvider } from '@/context/CapabilitiesContext'
import { NotificationsProvider } from '@/context/NotificationsContext'
import { DashboardPage } from '@/pages/DashboardPage'
import { AcceptInvitationPage } from '@/pages/AcceptInvitationPage'
import { AssignmentsPage } from '@/pages/AssignmentsPage'
import { AttendancePage } from '@/pages/AttendancePage'
import { AuditLogPage } from '@/pages/AuditLogPage'
import { CalendarPage } from '@/pages/CalendarPage'
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
import { ReviewQueuePage } from '@/pages/ReviewQueuePage'
import { ResourceLibraryPage } from '@/pages/ResourceLibraryPage'
import { SearchPage } from '@/pages/SearchPage'
import { SetupPage } from '@/pages/SetupPage'
import { StudentsPage } from '@/pages/StudentsPage'
import { SubjectsPage } from '@/pages/SubjectsPage'
import { UploadPage } from '@/pages/UploadPage'

function LoadingScreen() {
  return <div className="flex min-h-screen items-center justify-center text-muted-foreground">Loading session…</div>
}

function defaultRouteForRole(role: FamilyRole | null) {
  if (role === 'student_viewer') {
    return '/planner'
  }
  return '/dashboard'
}

function RoleRoute({ allowedRoles, element }: { allowedRoles: FamilyRole[]; element: JSX.Element }) {
  const { role } = useAuth()
  if (!role || !allowedRoles.includes(role)) {
    return <Navigate to={defaultRouteForRole(role)} replace />
  }
  return element
}

function ProtectedRoutes() {
  const { loading, isAuthenticated, bootstrapRequired, role } = useAuth()

  if (loading) {
    return <LoadingScreen />
  }

  if (!isAuthenticated) {
    return <Navigate to={bootstrapRequired ? '/setup' : '/login'} replace />
  }

  return (
    <AppShell>
      <Routes>
        <Route path="/" element={<Navigate to={defaultRouteForRole(role)} replace />} />
        <Route path="/dashboard" element={<DashboardPage />} />
        <Route path="/students" element={<RoleRoute allowedRoles={['parent', 'co-parent', 'tutor']} element={<StudentsPage />} />} />
        <Route path="/subjects" element={<RoleRoute allowedRoles={['parent', 'co-parent', 'tutor']} element={<SubjectsPage />} />} />
        <Route path="/calendar" element={<RoleRoute allowedRoles={['parent', 'co-parent', 'tutor']} element={<CalendarPage />} />} />
        <Route path="/attendance" element={<RoleRoute allowedRoles={['parent', 'co-parent', 'tutor']} element={<AttendancePage />} />} />
        <Route path="/planner" element={<RoleRoute allowedRoles={['parent', 'co-parent', 'tutor', 'student_viewer']} element={<PlannerPage />} />} />
        <Route path="/lesson-plans" element={<RoleRoute allowedRoles={['parent', 'co-parent', 'tutor', 'student_viewer']} element={<LessonPlansPage />} />} />
        <Route path="/curriculum" element={<RoleRoute allowedRoles={['parent', 'co-parent', 'tutor']} element={<CurriculumPage />} />} />
        <Route path="/imports" element={<RoleRoute allowedRoles={['parent', 'co-parent', 'tutor']} element={<ImportsPage />} />} />
        <Route path="/resources" element={<RoleRoute allowedRoles={['parent', 'co-parent', 'tutor']} element={<ResourceLibraryPage />} />} />
        <Route path="/portfolio" element={<RoleRoute allowedRoles={['parent', 'co-parent', 'tutor', 'student_viewer']} element={<PortfolioPage />} />} />
        <Route path="/search" element={<RoleRoute allowedRoles={['parent', 'co-parent', 'tutor', 'student_viewer']} element={<SearchPage />} />} />
        <Route path="/assignments" element={<RoleRoute allowedRoles={['parent', 'co-parent', 'tutor', 'student_viewer']} element={<AssignmentsPage />} />} />
        <Route path="/upload" element={<RoleRoute allowedRoles={['parent', 'co-parent', 'tutor']} element={<UploadPage />} />} />
        <Route path="/grades" element={<RoleRoute allowedRoles={['parent', 'co-parent', 'tutor', 'student_viewer']} element={<GradesPage />} />} />
        <Route path="/quizzes" element={<RoleRoute allowedRoles={['parent', 'co-parent', 'tutor']} element={<QuizzesPage />} />} />
        <Route path="/review" element={<RoleRoute allowedRoles={['parent', 'co-parent', 'tutor']} element={<ReviewQueuePage />} />} />
        <Route path="/invitations" element={<RoleRoute allowedRoles={['parent', 'co-parent']} element={<InvitationsPage />} />} />
        <Route path="/audit" element={<RoleRoute allowedRoles={['parent', 'co-parent']} element={<AuditLogPage />} />} />
        <Route path="/notifications" element={<NotificationsPage />} />
        <Route path="/settings/notifications" element={<NotificationPreferencesPage />} />
        <Route path="*" element={<NotFoundPage />} />
      </Routes>
    </AppShell>
  )
}

function LoginRoute() {
  const { isAuthenticated, loading, bootstrapRequired, role } = useAuth()

  if (loading) {
    return <LoadingScreen />
  }

  if (isAuthenticated) {
    return <Navigate to={defaultRouteForRole(role)} replace />
  }

  if (bootstrapRequired) {
    return <Navigate to="/setup" replace />
  }

  return <LoginPage />
}

function SetupRoute() {
  const { isAuthenticated, loading, bootstrapRequired, role } = useAuth()

  if (loading) {
    return <LoadingScreen />
  }

  if (isAuthenticated) {
    return <Navigate to={defaultRouteForRole(role)} replace />
  }

  if (!bootstrapRequired) {
    return <Navigate to="/login" replace />
  }

  return <SetupPage />
}

function AcceptInvitationRoute() {
  const { isAuthenticated, loading, role } = useAuth()

  if (loading) {
    return <LoadingScreen />
  }

  if (isAuthenticated) {
    return <Navigate to={defaultRouteForRole(role)} replace />
  }

  return <AcceptInvitationPage />
}

export default function App() {
  return (
    <AuthProvider>
      <CapabilitiesProvider>
        <NotificationsProvider>
          <Routes>
            <Route path="/login" element={<LoginRoute />} />
            <Route path="/setup" element={<SetupRoute />} />
            <Route path="/accept-invite/:invitationId" element={<AcceptInvitationRoute />} />
            <Route path="/portfolio/share/:shareToken" element={<PortfolioSharePage />} />
            <Route path="*" element={<ProtectedRoutes />} />
          </Routes>
        </NotificationsProvider>
      </CapabilitiesProvider>
    </AuthProvider>
  )
}
