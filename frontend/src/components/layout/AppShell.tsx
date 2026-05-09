import { type FormEvent, useEffect, useMemo, useState } from 'react'
import {
  Bell,
  BookMarked,
  CalendarDays,
  ClipboardCheck,
  FileUp,
  GraduationCap,
  LayoutDashboard,
  LogOut,
  MailPlus,
  ScrollText,
  Search,
  Settings,
  UserCheck,
  Users,
} from 'lucide-react'
import { NavLink, useLocation, useNavigate } from 'react-router-dom'
import type { FamilyRole } from '@/types/api'
import { useAuth } from '@/context/AuthContext'
import { useNotifications } from '@/context/NotificationsContext'
import { storeRecentSearch } from '@/lib/searchHistory'
import { cn } from '@/lib/utils'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'

const navItems: Array<{ to: string; label: string; icon: typeof LayoutDashboard; roles: FamilyRole[] }> = [
  { to: '/dashboard', label: 'Dashboard', icon: LayoutDashboard, roles: ['parent', 'co-parent', 'tutor', 'student_viewer'] },
  { to: '/students', label: 'Students', icon: Users, roles: ['parent', 'co-parent', 'tutor'] },
  { to: '/subjects', label: 'Subjects', icon: BookMarked, roles: ['parent', 'co-parent', 'tutor'] },
  { to: '/calendar', label: 'Calendar', icon: CalendarDays, roles: ['parent', 'co-parent', 'tutor'] },
  { to: '/attendance', label: 'Attendance', icon: UserCheck, roles: ['parent', 'co-parent', 'tutor'] },
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
  { to: '/notifications', label: 'Notifications', icon: Bell, roles: ['parent', 'co-parent', 'tutor', 'student_viewer'] },
  {
    to: '/settings/notifications',
    label: 'Notification Settings',
    icon: Settings,
    roles: ['parent', 'co-parent', 'tutor', 'student_viewer'],
  },
]

const roleLabels: Record<FamilyRole, string> = {
  parent: 'Parent',
  'co-parent': 'Co-parent',
  tutor: 'Tutor',
  student_viewer: 'Student viewer',
}

export function AppShell({ children }: { children: React.ReactNode }) {
  const { logout, userName, familyName, role } = useAuth()
  const { recent, unreadCount, markAllAsRead, markAsRead } = useNotifications()
  const location = useLocation()
  const navigate = useNavigate()
  const items = navItems.filter((item) => (role ? item.roles.includes(role) : false))
  const currentSearchQuery = useMemo(() => new URLSearchParams(location.search).get('q') || '', [location.search])
  const [searchValue, setSearchValue] = useState(currentSearchQuery)
  const [notificationsOpen, setNotificationsOpen] = useState(false)

  useEffect(() => {
    if (location.pathname === '/search') {
      setSearchValue(currentSearchQuery)
    }
  }, [currentSearchQuery, location.pathname])

  useEffect(() => {
    const handleShortcut = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'k') {
        event.preventDefault()
        const target = document.getElementById('global-search-input') as HTMLInputElement | null
        target?.focus()
        target?.select()
      }
    }
    window.addEventListener('keydown', handleShortcut)
    return () => window.removeEventListener('keydown', handleShortcut)
  }, [])

  const submitSearch = (event: FormEvent) => {
    event.preventDefault()
    const normalized = searchValue.trim()
    if (normalized) {
      storeRecentSearch(normalized)
      navigate(`/search?q=${encodeURIComponent(normalized)}`)
      return
    }
    navigate('/search')
  }

  const openNotification = async (link?: string | null, id?: number, read?: boolean) => {
    if (id && !read) {
      await markAsRead(id)
    }
    setNotificationsOpen(false)
    if (!link) {
      navigate('/notifications')
      return
    }
    if (link.startsWith('http://') || link.startsWith('https://')) {
      window.location.assign(link)
      return
    }
    navigate(link)
  }

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
          <div className="flex flex-col gap-2 md:min-w-[360px]">
            <form onSubmit={submitSearch} className="flex gap-2">
              <div className="relative flex-1">
                <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                <Input
                  id="global-search-input"
                  value={searchValue}
                  onChange={(event) => setSearchValue(event.target.value)}
                  placeholder="Search everything"
                  className="pl-9 pr-16"
                />
                <span className="pointer-events-none absolute right-3 top-1/2 hidden -translate-y-1/2 text-xs text-muted-foreground md:block">
                  Ctrl+K
                </span>
              </div>
              <Button type="submit" variant="outline">
                Search
              </Button>
            </form>
            <div className="relative flex flex-wrap items-center gap-2">
              <Button variant="outline" className="relative" onClick={() => setNotificationsOpen((current) => !current)}>
                <Bell className="mr-2 h-4 w-4" />
                Notifications
                {unreadCount ? (
                  <span className="absolute -right-2 -top-2 rounded-full bg-primary px-1.5 py-0.5 text-[10px] font-semibold text-primary-foreground">
                    {unreadCount > 99 ? '99+' : unreadCount}
                  </span>
                ) : null}
              </Button>
              {notificationsOpen ? (
                <div className="absolute right-0 top-10 z-20 w-[min(28rem,90vw)] rounded-xl border bg-popover p-3 shadow-lg">
                  <div className="mb-3 flex items-center justify-between gap-3">
                    <div>
                      <p className="font-semibold">Recent notifications</p>
                      <p className="text-xs text-muted-foreground">{unreadCount} unread</p>
                    </div>
                    <Button size="sm" variant="ghost" onClick={() => void markAllAsRead()}>
                      Mark all read
                    </Button>
                  </div>
                  <div className="space-y-2">
                    {recent.length ? (
                      recent.map((notification) => (
                        <button
                          key={notification.id}
                          type="button"
                          className={cn(
                            'w-full rounded-lg border p-3 text-left transition hover:bg-muted/60',
                            !notification.read && 'border-primary/40 bg-primary/5',
                          )}
                          onClick={() => void openNotification(notification.link, notification.id, notification.read)}
                        >
                          <div className="mb-1 flex items-center justify-between gap-2">
                            <p className="font-medium">{notification.title}</p>
                            <Badge variant={notification.read ? 'outline' : 'secondary'}>
                              {notification.type.replace('_', ' ')}
                            </Badge>
                          </div>
                          <p className="text-sm text-muted-foreground">{notification.message}</p>
                          <p className="mt-2 text-xs text-muted-foreground">{new Date(notification.created_at).toLocaleString()}</p>
                        </button>
                      ))
                    ) : (
                      <p className="rounded-lg border border-dashed p-6 text-center text-sm text-muted-foreground">
                        You&apos;re all caught up.
                      </p>
                    )}
                  </div>
                  <div className="mt-3 flex items-center justify-between gap-2">
                    <Button size="sm" variant="outline" onClick={() => void openNotification('/notifications')}>
                      View all
                    </Button>
                    <Button size="sm" variant="ghost" onClick={() => void openNotification('/settings/notifications')}>
                      Preferences
                    </Button>
                  </div>
                </div>
              ) : null}
              <Button variant="outline" onClick={() => void logout()}>
                <LogOut className="mr-2 h-4 w-4" />
                Log out
              </Button>
            </div>
          </div>
        </div>
        <nav className="mt-4 grid grid-cols-2 gap-2 md:grid-cols-4 lg:grid-cols-6 xl:grid-cols-8">
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
