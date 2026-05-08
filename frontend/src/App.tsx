import { Navigate, Route, Routes } from 'react-router-dom'
import { AppShell } from '@/components/layout/AppShell'
import { AuthProvider, useAuth } from '@/context/AuthContext'
import { DashboardPage } from '@/pages/DashboardPage'
import { AssignmentsPage } from '@/pages/AssignmentsPage'
import { GradesPage } from '@/pages/GradesPage'
import { LoginPage } from '@/pages/LoginPage'
import { NotFoundPage } from '@/pages/NotFoundPage'
import { QuizzesPage } from '@/pages/QuizzesPage'
import { ReviewQueuePage } from '@/pages/ReviewQueuePage'
import { StudentsPage } from '@/pages/StudentsPage'
import { SubjectsPage } from '@/pages/SubjectsPage'
import { UploadPage } from '@/pages/UploadPage'

function ProtectedRoutes() {
  const { loading, isAuthenticated } = useAuth()

  if (loading) {
    return <div className="flex min-h-screen items-center justify-center text-muted-foreground">Loading session…</div>
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />
  }

  return (
    <AppShell>
      <Routes>
        <Route path="/" element={<Navigate to="/dashboard" replace />} />
        <Route path="/dashboard" element={<DashboardPage />} />
        <Route path="/students" element={<StudentsPage />} />
        <Route path="/subjects" element={<SubjectsPage />} />
        <Route path="/assignments" element={<AssignmentsPage />} />
        <Route path="/upload" element={<UploadPage />} />
        <Route path="/grades" element={<GradesPage />} />
        <Route path="/quizzes" element={<QuizzesPage />} />
        <Route path="/review" element={<ReviewQueuePage />} />
        <Route path="*" element={<NotFoundPage />} />
      </Routes>
    </AppShell>
  )
}

function LoginRoute() {
  const { isAuthenticated, loading } = useAuth()

  if (loading) {
    return <div className="flex min-h-screen items-center justify-center text-muted-foreground">Loading session…</div>
  }

  if (isAuthenticated) {
    return <Navigate to="/dashboard" replace />
  }

  return <LoginPage />
}

export default function App() {
  return (
    <AuthProvider>
      <Routes>
        <Route path="/login" element={<LoginRoute />} />
        <Route path="*" element={<ProtectedRoutes />} />
      </Routes>
    </AuthProvider>
  )
}
