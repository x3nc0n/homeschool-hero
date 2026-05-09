import { BookMarked, CalendarDays, ClipboardCheck, FileUp, GraduationCap, LayoutDashboard, LogOut, MailPlus, ScrollText, Users } from 'lucide-react'
import { NavLink } from 'react-router-dom'
import type { FamilyRole } from '@/types/api'
import { useAuth } from '@/context/AuthContext'
import { cn } from '@/lib/utils'
import { Button } from '@/components/ui/button'

const navItems: Array<{ to: string; label: string; icon: typeof LayoutDashboard; roles: FamilyRole[] }> = [
  { to: '/dashboard', label: 'Dashboard', icon: LayoutDashboard, roles: ['parent', 'co-parent', 'tutor', 'student_viewer'] },
  { to: '/students', label: 'Students', icon: Users, roles: ['parent', 'co-parent', 'tutor'] },
  { to: '/subjects', label: 'Subjects', icon: BookMarked, roles: ['parent', 'co-parent', 'tutor'] },
  { to: '/calendar', label: 'Calendar', icon: CalendarDays, roles: ['parent', 'co-parent', 'tutor'] },
  { to: '/planner', label: 'Planner', icon: CalendarDays, roles: ['parent', 'co-parent', 'tutor', 'student_viewer'] },
  { to: '/curriculum', label: 'Curriculum', icon: BookMarked, roles: ['parent', 'co-parent', 'tutor'] },
  { to: '/resources', label: 'Resources', icon: FileUp, roles: ['parent', 'co-parent', 'tutor'] },
  { to: '/assignments', label: 'Assignments', icon: ClipboardCheck, roles: ['parent', 'co-parent', 'tutor', 'student_viewer'] },
  { to: '/upload', label: 'Uploads', icon: FileUp, roles: ['parent', 'co-parent', 'tutor'] },
  { to: '/grades', label: 'Grade Book', icon: GraduationCap, roles: ['parent', 'co-parent', 'tutor', 'student_viewer'] },
  { to: '/quizzes', label: 'Quizzes', icon: ClipboardCheck, roles: ['parent', 'co-parent', 'tutor'] },
  { to: '/review', label: 'Review Queue', icon: GraduationCap, roles: ['parent', 'co-parent', 'tutor'] },
  { to: '/invitations', label: 'Invitations', icon: MailPlus, roles: ['parent', 'co-parent'] },
  { to: '/audit', label: 'Audit Log', icon: ScrollText, roles: ['parent', 'co-parent'] },
]

const roleLabels: Record<FamilyRole, string> = {
  parent: 'Parent',
  'co-parent': 'Co-parent',
  tutor: 'Tutor',
  student_viewer: 'Student viewer',
}

export function AppShell({ children }: { children: React.ReactNode }) {
  const { logout, userName, familyName, role } = useAuth()
  const items = navItems.filter((item) => (role ? item.roles.includes(role) : false))

  return (
    <div className="mx-auto min-h-screen max-w-7xl px-3 py-4 md:px-6">
      <header className="mb-4 rounded-xl border bg-card p-4 shadow-sm">
        <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
          <div>
            <h1 className="text-xl font-bold md:text-2xl">Homeschool Hero</h1>
            <p className="text-sm text-muted-foreground">
              Welcome back, {userName}
              {familyName ? ` · ${familyName}` : ''}
              {role ? ` · ${roleLabels[role]}` : ''}
            </p>
          </div>
          <Button variant="outline" onClick={() => void logout()}>
            <LogOut className="mr-2 h-4 w-4" />
            Log out
          </Button>
        </div>
        <nav className="mt-4 grid grid-cols-2 gap-2 md:grid-cols-4 lg:grid-cols-11">
          {items.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) =>
                cn(
                  'flex items-center justify-center gap-2 rounded-md border px-3 py-2 text-xs font-medium transition hover:bg-muted',
                  isActive && 'border-primary bg-primary/10 text-primary',
                )
              }
            >
              <item.icon className="h-3.5 w-3.5" />
              {item.label}
            </NavLink>
          ))}
        </nav>
      </header>

      <main className="space-y-4">{children}</main>
    </div>
  )
}
