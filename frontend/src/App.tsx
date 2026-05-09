import { Navigate, Route, Routes } from 'react-router-dom'
import type { FamilyRole } from '@/types/api'
import { AppShell } from '@/components/layout/AppShell'
import { AuthProvider, useAuth } from '@/context/AuthContext'
import { CapabilitiesProvider } from '@/context/CapabilitiesContext'
import { DashboardPage } from '@/pages/DashboardPage'
import { AcceptInvitationPage } from '@/pages/AcceptInvitationPage'
import { AssignmentsPage } from '@/pages/AssignmentsPage'
import { AuditLogPage } from '@/pages/AuditLogPage'
import { CalendarPage } from '@/pages/CalendarPage'
import { GradesPage } from '@/pages/GradesPage'
import { InvitationsPage } from '@/pages/InvitationsPage'
import { LoginPage } from '@/pages/LoginPage'
import { NotFoundPage } from '@/pages/NotFoundPage'
import { QuizzesPage } from '@/pages/QuizzesPage'
import { ReviewQueuePage } from '@/pages/ReviewQueuePage'
import { SetupPage } from '@/pages/SetupPage'
import { StudentsPage } from '@/pages/StudentsPage'
import { SubjectsPage } from '@/pages/SubjectsPage'
import { UploadPage } from '@/pages/UploadPage'

function LoadingScreen() {
  return <div className="flex min-h-screen items-center justify-center text-muted-foreground">Loading session…</div>
}

function defaultRouteForRole(role: FamilyRole | null) {
  if (role === 'student_viewer') {
    return '/assignments'
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
        <Route path="/subjects" element={<RoleRoute allowedRoles={['parent', 'co-parent', 'tutor']} element={<SubjectsPage />} />} />
        <Route path="/calendar" element={<RoleRoute allowedRoles={['parent', 'co-parent', 'tutor']} element={<CalendarPage />} />} />
        <Route path="/assignments" element={<RoleRoute allowedRoles={['parent', 'co-parent', 'tutor', 'student_viewer']} element={<AssignmentsPage />} />} />
        <Route path="/upload" element={<RoleRoute allowedRoles={['parent', 'co-parent', 'tutor']} element={<UploadPage />} />} />
        <Route path="/grades" element={<RoleRoute allowedRoles={['parent', 'co-parent', 'tutor', 'student_viewer']} element={<GradesPage />} />} />
        <Route path="/quizzes" element={<RoleRoute allowedRoles={['parent', 'co-parent', 'tutor']} element={<QuizzesPage />} />} />
        <Route path="/review" element={<RoleRoute allowedRoles={['parent', 'co-parent', 'tutor']} element={<ReviewQueuePage />} />} />
        <Route path="/invitations" element={<RoleRoute allowedRoles={['parent', 'co-parent']} element={<InvitationsPage />} />} />
        <Route path="/audit" element={<RoleRoute allowedRoles={['parent', 'co-parent']} element={<AuditLogPage />} />} />
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
        <Routes>
          <Route path="/login" element={<LoginRoute />} />
          <Route path="/setup" element={<SetupRoute />} />
          <Route path="/accept-invite/:invitationId" element={<AcceptInvitationRoute />} />
          <Route path="*" element={<ProtectedRoutes />} />
        </Routes>
      </CapabilitiesProvider>
    </AuthProvider>
  )
}
