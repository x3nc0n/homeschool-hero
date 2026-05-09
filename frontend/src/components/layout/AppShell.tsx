import { type FormEvent, useEffect, useMemo, useState } from 'react'
import {
  Bell,
  BookMarked,
  BookOpenCheck,
  CalendarDays,
  ClipboardCheck,
  Download,
  FileText,
  FileUp,
  FolderSync,
  GraduationCap,
  HardDriveDownload,
  HeartPulse,
  Inbox,
  LayoutDashboard,
  Library,
  LogOut,
  MailPlus,
  Menu,
  ScrollText,
  Search,
  Settings,
  ShieldCheck,
  Smartphone,
  Upload,
  UserCheck,
  Users,
  WifiOff,
  X,
} from 'lucide-react'
import { NavLink, useLocation, useNavigate } from 'react-router-dom'
import type { FamilyRole } from '@/types/api'
import { useAuth } from '@/context/AuthContext'
import { useNotifications } from '@/context/NotificationsContext'
import { usePwa } from '@/context/PwaContext'
import { storeRecentSearch } from '@/lib/searchHistory'
import { cn } from '@/lib/utils'
import { Breadcrumbs } from '@/components/common/Breadcrumbs'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'

type NavItem = {
  to: string
  label: string
  icon: typeof LayoutDashboard
  roles: FamilyRole[]
}

type NavGroup = {
  label: string
  items: NavItem[]
}

const navGroups: NavGroup[] = [
  {
    label: 'Dashboard',
    items: [
      { to: '/', label: 'Dashboard', icon: LayoutDashboard, roles: ['parent', 'co-parent', 'tutor', 'student_viewer'] },
      { to: '/notifications', label: 'Notifications', icon: Bell, roles: ['parent', 'co-parent', 'tutor', 'student_viewer'] },
    ],
  },
  {
    label: 'Students',
    items: [{ to: '/students', label: 'Student roster', icon: Users, roles: ['parent', 'co-parent', 'tutor'] }],
  },
  {
    label: 'Academics',
    items: [
      { to: '/calendar', label: 'Calendar', icon: CalendarDays, roles: ['parent', 'co-parent', 'tutor'] },
      { to: '/planner', label: 'Planner', icon: CalendarDays, roles: ['parent', 'co-parent', 'tutor', 'student_viewer'] },
      { to: '/subjects', label: 'Subjects', icon: BookMarked, roles: ['parent', 'co-parent', 'tutor'] },
      { to: '/curriculum', label: 'Curriculum', icon: Library, roles: ['parent', 'co-parent', 'tutor'] },
      { to: '/lesson-plans', label: 'Lesson Plans', icon: BookOpenCheck, roles: ['parent', 'co-parent', 'tutor', 'student_viewer'] },
      { to: '/attendance', label: 'Attendance', icon: UserCheck, roles: ['parent', 'co-parent', 'tutor'] },
    ],
  },
  {
    label: 'Assignments & Grading',
    items: [
      { to: '/assignments', label: 'Assignments', icon: ClipboardCheck, roles: ['parent', 'co-parent', 'tutor', 'student_viewer'] },
      { to: '/grades', label: 'Grade Book', icon: GraduationCap, roles: ['parent', 'co-parent', 'tutor', 'student_viewer'] },
      { to: '/review', label: 'Review Queue', icon: Inbox, roles: ['parent', 'co-parent', 'tutor'] },
      { to: '/upload', label: 'Uploads', icon: Upload, roles: ['parent', 'co-parent', 'tutor'] },
      { to: '/quizzes', label: 'Quizzes', icon: ClipboardCheck, roles: ['parent', 'co-parent', 'tutor'] },
    ],
  },
  {
    label: 'Reports',
    items: [
      { to: '/report-cards', label: 'Report Cards', icon: FileText, roles: ['parent', 'co-parent', 'tutor', 'student_viewer'] },
      { to: '/transcripts', label: 'Transcripts', icon: FileText, roles: ['parent', 'co-parent', 'tutor', 'student_viewer'] },
      { to: '/compliance', label: 'Compliance', icon: ShieldCheck, roles: ['parent', 'co-parent', 'tutor', 'student_viewer'] },
      { to: '/compliance-reports', label: 'Compliance Reports', icon: FileText, roles: ['parent', 'co-parent', 'tutor', 'student_viewer'] },
      { to: '/portfolio', label: 'Portfolio', icon: BookOpenCheck, roles: ['parent', 'co-parent', 'tutor', 'student_viewer'] },
    ],
  },
  {
    label: 'Data',
    items: [
      { to: '/imports', label: 'Import data', icon: FolderSync, roles: ['parent', 'co-parent', 'tutor'] },
      { to: '/exports', label: 'Export data', icon: Download, roles: ['parent', 'co-parent'] },
      { to: '/resources', label: 'Resources', icon: FileUp, roles: ['parent', 'co-parent', 'tutor'] },
    ],
  },
  {
    label: 'Settings',
    items: [
      { to: '/invitations', label: 'Invitations', icon: MailPlus, roles: ['parent', 'co-parent'] },
      { to: '/audit', label: 'Audit Log', icon: ScrollText, roles: ['parent', 'co-parent'] },
      { to: '/settings/family', label: 'Family', icon: Settings, roles: ['parent', 'co-parent'] },
      { to: '/settings/notifications', label: 'Notifications', icon: Settings, roles: ['parent', 'co-parent', 'tutor', 'student_viewer'] },
      { to: '/settings/backups', label: 'Backups', icon: HardDriveDownload, roles: ['parent', 'co-parent'] },
      { to: '/settings/restore', label: 'Restore', icon: HardDriveDownload, roles: ['parent', 'co-parent'] },
      { to: '/settings/status', label: 'System status', icon: HeartPulse, roles: ['parent', 'co-parent'] },
    ],
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
  const { canInstall, installApp, isOfflineReady, isOnline, needsRefresh, dismissOfflineReady, applyUpdate } = usePwa()
  const location = useLocation()
  const navigate = useNavigate()
  const [notificationsOpen, setNotificationsOpen] = useState(false)
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false)
  const currentSearchQuery = useMemo(() => new URLSearchParams(location.search).get('q') || '', [location.search])
  const [searchValue, setSearchValue] = useState(currentSearchQuery)

  const groups = useMemo(
    () =>
      navGroups
        .map((group) => ({
          ...group,
          items: group.items.filter((item) => (role ? item.roles.includes(role) : false)),
        }))
        .filter((group) => group.items.length),
    [role],
  )

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

  useEffect(() => {
    setMobileMenuOpen(false)
    setNotificationsOpen(false)
  }, [location.pathname])

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

  const renderNavGroups = (compact = false) =>
    groups.map((group) => (
      <section key={group.label} className="space-y-2">
        <p className={cn('px-1 text-xs font-semibold uppercase tracking-wide text-muted-foreground', compact && 'pt-2')}>{group.label}</p>
        <div className="space-y-1">
          {group.items.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.to === '/'}
              className={({ isActive }) =>
                cn('flex min-h-11 items-center gap-2 rounded-lg px-3 py-2 text-sm transition hover:bg-muted', isActive && 'bg-primary/10 font-medium text-primary')
              }
            >
              <item.icon className="h-4 w-4 shrink-0" />
              <span>{item.label}</span>
            </NavLink>
          ))}
        </div>
      </section>
    ))

  const mobileTabs = useMemo(
    () =>
      [
        { to: '/', label: 'Home', icon: LayoutDashboard },
        { to: '/students', label: 'Students', icon: Users },
        { to: '/assignments', label: 'Tasks', icon: ClipboardCheck },
        { to: '/upload', label: 'Upload', icon: Upload },
        { to: '/notifications', label: 'Alerts', icon: Bell },
      ].filter((item) => groups.some((group) => group.items.some((navItem) => navItem.to === item.to))),
    [groups],
  )

  return (
    <div className="min-h-screen bg-muted/20">
      <div className="mx-auto max-w-7xl px-3 py-4 pb-24 md:px-6 md:pb-6">
        <div className="grid gap-4 md:grid-cols-[260px_minmax(0,1fr)]">
          <aside className="hidden md:block">
            <div className="sticky top-4 space-y-4 rounded-xl border bg-card p-4 shadow-sm">
              <div>
                <p className="text-lg font-bold">Homeschool Hero</p>
                <p className="text-sm text-muted-foreground">{familyName || 'Family workspace'}</p>
              </div>
              <div className="rounded-lg border bg-muted/30 p-3 text-sm">
                <p className="font-medium">{userName}</p>
                <p className="text-xs text-muted-foreground">{role ? roleLabels[role] : 'Signed in'}</p>
              </div>
              <nav className="space-y-4">{renderNavGroups()}</nav>
            </div>
          </aside>

          <div className="min-w-0 space-y-4">
            <header className="rounded-xl border bg-card p-4 shadow-sm">
              <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
                <div className="space-y-2">
                  <div className="flex items-center justify-between gap-3 md:hidden">
                    <div>
                      <p className="text-lg font-bold">Homeschool Hero</p>
                      <p className="text-sm text-muted-foreground">{familyName || 'Family workspace'}</p>
                    </div>
                    <Button type="button" variant="outline" size="icon" aria-label="Open navigation" onClick={() => setMobileMenuOpen(true)}>
                      <Menu className="h-5 w-5" />
                    </Button>
                  </div>
                  <Breadcrumbs />
                  <div>
                    <h1 className="text-xl font-bold md:text-2xl">Welcome back, {userName}</h1>
                    <p className="text-sm text-muted-foreground">
                      {familyName ? `${familyName} · ` : ''}
                      {role ? roleLabels[role] : 'Workspace'}
                    </p>
                  </div>
                </div>

                <div className="flex w-full flex-col gap-2 lg:max-w-xl">
                  <form onSubmit={submitSearch} className="flex gap-2">
                    <div className="relative flex-1">
                      <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                      <Input id="global-search-input" value={searchValue} onChange={(event) => setSearchValue(event.target.value)} placeholder="Search everything" className="pl-9 pr-16" />
                      <span className="pointer-events-none absolute right-3 top-1/2 hidden -translate-y-1/2 text-xs text-muted-foreground md:block">Ctrl+K</span>
                    </div>
                    <Button type="submit" variant="outline">
                      Search
                    </Button>
                  </form>

                  <div className="relative flex flex-wrap items-center gap-2">
                    <Button type="button" variant="outline" className="relative" onClick={() => setNotificationsOpen((current) => !current)}>
                      <Bell className="mr-2 h-4 w-4" />
                      Notifications
                      {unreadCount ? (
                        <span className="absolute -right-2 -top-2 rounded-full bg-primary px-1.5 py-0.5 text-[10px] font-semibold text-primary-foreground">
                          {unreadCount > 99 ? '99+' : unreadCount}
                        </span>
                      ) : null}
                    </Button>
                    {notificationsOpen ? (
                      <div className="absolute right-0 top-12 z-20 w-[min(28rem,90vw)] rounded-xl border bg-popover p-3 shadow-lg">
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
                                className={cn('w-full rounded-lg border p-3 text-left transition hover:bg-muted/60', !notification.read && 'border-primary/40 bg-primary/5')}
                                onClick={() => void openNotification(notification.link, notification.id, notification.read)}
                              >
                                <div className="mb-1 flex items-center justify-between gap-2">
                                  <p className="font-medium">{notification.title}</p>
                                  <Badge variant={notification.read ? 'outline' : 'secondary'}>{notification.type.replace('_', ' ')}</Badge>
                                </div>
                                <p className="text-sm text-muted-foreground">{notification.message}</p>
                                <p className="mt-2 text-xs text-muted-foreground">{new Date(notification.created_at).toLocaleString()}</p>
                              </button>
                            ))
                          ) : (
                            <p className="rounded-lg border border-dashed p-6 text-center text-sm text-muted-foreground">You&apos;re all caught up.</p>
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
                    <Button type="button" variant="outline" onClick={() => void logout()}>
                      <LogOut className="mr-2 h-4 w-4" />
                      Log out
                    </Button>
                  </div>
                </div>
              </div>
            </header>

            {!isOnline ? (
              <div className="rounded-xl border border-amber-300 bg-amber-50 px-4 py-3 text-sm text-amber-900">
                <div className="flex items-start gap-3">
                  <WifiOff className="mt-0.5 h-4 w-4 shrink-0" />
                  <div>
                    <p className="font-medium">Offline mode</p>
                    <p>Cached pages are still available. New changes will resume when your connection returns.</p>
                  </div>
                </div>
              </div>
            ) : null}

            {canInstall ? (
              <div className="rounded-xl border border-primary/20 bg-primary/5 px-4 py-3 text-sm">
                <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                  <div className="flex items-start gap-3">
                    <Smartphone className="mt-0.5 h-4 w-4 shrink-0 text-primary" />
                    <div>
                      <p className="font-medium">Install Homeschool Hero</p>
                      <p className="text-muted-foreground">Add the app to your home screen for a faster, full-screen mobile experience.</p>
                    </div>
                  </div>
                  <Button type="button" onClick={() => void installApp()}>
                    Install app
                  </Button>
                </div>
              </div>
            ) : null}

            {needsRefresh ? (
              <div className="rounded-xl border border-sky-300 bg-sky-50 px-4 py-3 text-sm text-sky-950">
                <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                  <div>
                    <p className="font-medium">Update ready</p>
                    <p>A newer version of Homeschool Hero is available.</p>
                  </div>
                  <Button type="button" variant="outline" onClick={() => void applyUpdate()}>
                    Reload update
                  </Button>
                </div>
              </div>
            ) : null}

            {isOfflineReady ? (
              <div className="rounded-xl border border-emerald-300 bg-emerald-50 px-4 py-3 text-sm text-emerald-950">
                <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                  <div>
                    <p className="font-medium">Offline support ready</p>
                    <p>The app shell and recent assets are cached for basic offline access.</p>
                  </div>
                  <Button type="button" variant="outline" onClick={dismissOfflineReady}>
                    Dismiss
                  </Button>
                </div>
              </div>
            ) : null}

            <main className="space-y-4">{children}</main>
          </div>
        </div>
      </div>

      {mobileMenuOpen ? (
        <div className="fixed inset-0 z-40 md:hidden">
          <button type="button" className="absolute inset-0 bg-black/40" aria-label="Close navigation" onClick={() => setMobileMenuOpen(false)} />
          <aside className="absolute inset-y-0 left-0 flex w-[min(22rem,88vw)] flex-col gap-4 overflow-y-auto border-r bg-card p-4 shadow-xl">
            <div className="flex items-center justify-between gap-3">
              <div>
                <p className="text-lg font-bold">Homeschool Hero</p>
                <p className="text-sm text-muted-foreground">{familyName || 'Family workspace'}</p>
              </div>
              <Button type="button" variant="ghost" size="icon" aria-label="Close navigation" onClick={() => setMobileMenuOpen(false)}>
                <X className="h-5 w-5" />
              </Button>
            </div>
            <div className="rounded-lg border bg-muted/30 p-3 text-sm">
              <p className="font-medium">{userName}</p>
              <p className="text-xs text-muted-foreground">{role ? roleLabels[role] : 'Signed in'}</p>
            </div>
            <nav className="space-y-4">{renderNavGroups(true)}</nav>
          </aside>
        </div>
      ) : null}

      {mobileTabs.length ? (
        <nav className="fixed inset-x-0 bottom-0 z-30 border-t bg-card/95 px-2 py-2 backdrop-blur md:hidden" style={{ paddingBottom: 'calc(env(safe-area-inset-bottom, 0px) + 0.5rem)' }}>
          <div className={cn('mx-auto grid max-w-7xl gap-1', mobileTabs.length === 4 ? 'grid-cols-4' : 'grid-cols-5')}>
            {mobileTabs.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.to === '/'}
                className={({ isActive }) =>
                  cn('flex min-h-14 flex-col items-center justify-center gap-1 rounded-lg px-2 py-2 text-[11px] font-medium text-muted-foreground', isActive && 'bg-primary/10 text-primary')
                }
              >
                <item.icon className="h-4 w-4" />
                <span>{item.label}</span>
              </NavLink>
            ))}
          </div>
        </nav>
      ) : null}
    </div>
  )
}
