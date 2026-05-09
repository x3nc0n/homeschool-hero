import { BookMarked, ClipboardCheck, FileUp, GraduationCap, LayoutDashboard, LogOut, Users } from 'lucide-react'
import { NavLink } from 'react-router-dom'
import { useAuth } from '@/context/AuthContext'
import { cn } from '@/lib/utils'
import { Button } from '@/components/ui/button'

const navItems = [
  { to: '/dashboard', label: 'Dashboard', icon: LayoutDashboard },
  { to: '/students', label: 'Students', icon: Users },
  { to: '/subjects', label: 'Subjects', icon: BookMarked },
  { to: '/assignments', label: 'Assignments', icon: ClipboardCheck },
  { to: '/upload', label: 'Uploads', icon: FileUp },
  { to: '/grades', label: 'Grade Book', icon: GraduationCap },
  { to: '/quizzes', label: 'Quizzes', icon: ClipboardCheck },
  { to: '/review', label: 'Review Queue', icon: GraduationCap },
]

export function AppShell({ children }: { children: React.ReactNode }) {
  const { logout, userName, familyName } = useAuth()

  return (
    <div className="mx-auto min-h-screen max-w-7xl px-3 py-4 md:px-6">
      <header className="mb-4 rounded-xl border bg-card p-4 shadow-sm">
        <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
          <div>
            <h1 className="text-xl font-bold md:text-2xl">Homeschool Hero</h1>
            <p className="text-sm text-muted-foreground">
              Welcome back, {userName}
              {familyName ? ` · ${familyName}` : ''}
            </p>
          </div>
          <Button variant="outline" onClick={() => void logout()}>
            <LogOut className="mr-2 h-4 w-4" />
            Log out
          </Button>
        </div>
        <nav className="mt-4 grid grid-cols-2 gap-2 md:grid-cols-4 lg:grid-cols-8">
          {navItems.map((item) => (
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
