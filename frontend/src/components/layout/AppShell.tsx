import { type FormEvent, useEffect, useMemo, useRef, useState } from 'react'
import {
  BarChart,
  Bell,
  BookOpen,
  BookOpenCheck,
  Calendar,
  CalendarDays,
  ClipboardCheck,
  Database,
  FileStack,
  FileText,
  GraduationCap,
  LayoutDashboard,
  LogOut,
  Menu,
  Palette,
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
import type { AppRole, FamilyRole } from '@/types/api'
import { useAuth } from '@/context/AuthContext'
import { useNotifications } from '@/context/NotificationsContext'
import { usePwa } from '@/context/PwaContext'
import { useTheme } from '@/context/ThemeContext'
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
  capabilities?: string[]
  appRoles?: AppRole[]
  feature?: string
}

type NavGroup = {
  label: string
  items: NavItem[]
}

const navGroups: NavGroup[] = [
  {
    label: 'Academics',
    items: [
      { to: '/dashboard', label: 'Dashboard', icon: LayoutDashboard },
      { to: '/students', label: 'Students', icon: Users, capabilities: ['manage_household', 'manage_family', 'manage_curriculum'] },
      { to: '/subjects', label: 'Subjects', icon: BookOpen, capabilities: ['manage_curriculum', 'manage_grading', 'manage_submissions'] },
      {
        to: '/curriculum',
        label: 'Curriculum',
        icon: GraduationCap,
        capabilities: ['manage_curriculum', 'manage_grading', 'manage_submissions', 'view_own_progress', 'read_curriculum', 'read_grades'],
        appRoles: ['student'],
      },
      { to: '/calendar', label: 'Calendar', icon: Calendar, capabilities: ['manage_curriculum', 'manage_grading', 'manage_submissions'] },
      {
        to: '/planner',
        label: 'Planner',
        icon: CalendarDays,
        capabilities: ['manage_curriculum', 'manage_grading', 'manage_submissions', 'view_own_progress', 'read_curriculum', 'read_grades'],
        appRoles: ['student'],
        feature: 'planner',
      },
      { to: '/attendance', label: 'Attendance', icon: UserCheck, capabilities: ['manage_curriculum', 'manage_grading', 'manage_submissions'], feature: 'attendance' },
    ],
  },
  {
    label: 'Schoolwork',
    items: [
      {
        to: '/assignments',
        label: 'Assignments',
        icon: FileText,
        capabilities: ['manage_curriculum', 'manage_grading', 'manage_submissions', 'view_own_progress', 'read_curriculum', 'read_submissions', 'read_grades'],
        appRoles: ['student'],
      },
      { to: '/upload', label: 'Upload', icon: Upload, capabilities: ['manage_submissions'] },
      { to: '/quizzes', label: 'Quizzes', icon: ClipboardCheck, capabilities: ['manage_grading'], feature: 'quizzes' },
      {
        to: '/grades',
        label: 'Gradebook',
        icon: BarChart,
        capabilities: ['manage_curriculum', 'manage_grading', 'manage_submissions', 'view_own_progress', 'read_grades'],
        appRoles: ['student'],
      },
    ],
  },
  {
    label: 'Records',
    items: [
      {
        to: '/academic-records',
        label: 'Academic Records',
        icon: FileStack,
        capabilities: ['manage_curriculum', 'manage_grading', 'manage_submissions', 'view_own_progress', 'read_grades', 'read_curriculum'],
        appRoles: ['student'],
      },
      {
        to: '/portfolio',
        label: 'Portfolio',
        icon: BookOpenCheck,
        capabilities: ['manage_curriculum', 'manage_grading', 'manage_submissions', 'view_own_progress', 'read_grades', 'read_curriculum'],
        appRoles: ['student'],
        feature: 'portfolio',
      },
      {
        to: '/compliance',
        label: 'Compliance',
        icon: ShieldCheck,
        capabilities: ['manage_curriculum', 'manage_grading', 'manage_submissions', 'view_own_progress', 'read_grades', 'read_curriculum'],
        appRoles: ['student'],
        feature: 'compliance',
      },
    ],
  },
  {
    label: 'Settings',
    items: [
      { to: '/settings/family', label: 'Family & Features', icon: Settings, capabilities: ['manage_household', 'manage_family'] },
      { to: '/data', label: 'Data Management', icon: Database, capabilities: ['manage_curriculum', 'manage_grading', 'manage_submissions', 'manage_platform'] },
      { to: '/settings/appearance', label: 'Appearance', icon: Palette },
      { to: '/notifications/preferences', label: 'Notifications', icon: Bell },
    ],
  },
]

const roleLabels: Record<FamilyRole, string> = {
  parent: 'Parent',
  'co-parent': 'Co-parent',
  tutor: 'Tutor',
  student_viewer: 'Student viewer',
}

const focusableSelector = [
  'a[href]',
  'button:not([disabled])',
  'input:not([disabled])',
  'select:not([disabled])',
  'textarea:not([disabled])',
  '[tabindex]:not([tabindex="-1"])',
].join(', ')

export function AppShell({ children }: { children: React.ReactNode }) {
  const { logout, userName, familyName, role, enabledFeatures, hasCapability, hasRole } = useAuth()
  const { preferences } = useTheme()
  const { recent, unreadCount, markAllAsRead, markAsRead } = useNotifications()
  const { canInstall, installApp, isOfflineReady, isOnline, needsRefresh, dismissOfflineReady, applyUpdate } = usePwa()
  const location = useLocation()
  const navigate = useNavigate()
  const [notificationsOpen, setNotificationsOpen] = useState(false)
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false)
  const currentSearchQuery = useMemo(() => new URLSearchParams(location.search).get('q') || '', [location.search])
  const [searchValue, setSearchValue] = useState(currentSearchQuery)
  const notificationsButtonRef = useRef<HTMLButtonElement | null>(null)
  const notificationsPanelRef = useRef<HTMLDivElement | null>(null)
  const mobileMenuButtonRef = useRef<HTMLButtonElement | null>(null)
  const mobileMenuPanelRef = useRef<HTMLElement | null>(null)

  const groups = useMemo(
    () =>
      navGroups
        .map((group) => ({
          ...group,
          items: group.items.filter((item) => {
            const capabilityMatch = item.capabilities?.some((capability) => hasCapability(capability)) ?? false
            const roleMatch = item.appRoles?.some((appRole) => hasRole(appRole)) ?? false
            const hasAccess = (!item.capabilities?.length && !item.appRoles?.length) || capabilityMatch || roleMatch
            return hasAccess && (item.feature ? enabledFeatures[item.feature] !== false : true)
          }),
        }))
        .filter((group) => group.items.length),
    [enabledFeatures, hasCapability, hasRole],
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
  }, [location.pathname, location.search])

  useEffect(() => {
    if (!notificationsOpen) return

    const panel = notificationsPanelRef.current
    const trigger = notificationsButtonRef.current
    if (!panel) return

    const getFocusable = () =>
      Array.from(panel.querySelectorAll<HTMLElement>(focusableSelector)).filter(
        (element) => !element.hasAttribute('disabled') && element.tabIndex !== -1,
      )

    window.requestAnimationFrame(() => {
      ;(getFocusable()[0] || panel).focus()
    })

    const handlePointer = (event: MouseEvent | TouchEvent) => {
      const target = event.target
      if (!(target instanceof Node)) return
      if (panel.contains(target) || trigger?.contains(target)) return
      setNotificationsOpen(false)
    }

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        event.preventDefault()
        setNotificationsOpen(false)
        trigger?.focus()
        return
      }

      if (event.key !== 'Tab') return

      const focusable = getFocusable()
      if (!focusable.length) {
        event.preventDefault()
        panel.focus()
        return
      }

      const first = focusable[0]
      const last = focusable[focusable.length - 1]
      const active = document.activeElement

      if (event.shiftKey && active === first) {
        event.preventDefault()
        last.focus()
      } else if (!event.shiftKey && active === last) {
        event.preventDefault()
        first.focus()
      }
    }

    document.addEventListener('mousedown', handlePointer)
    document.addEventListener('touchstart', handlePointer)
    document.addEventListener('keydown', handleKeyDown)

    return () => {
      document.removeEventListener('mousedown', handlePointer)
      document.removeEventListener('touchstart', handlePointer)
      document.removeEventListener('keydown', handleKeyDown)
    }
  }, [notificationsOpen])

  useEffect(() => {
    if (!mobileMenuOpen) return

    const panel = mobileMenuPanelRef.current
    const trigger = mobileMenuButtonRef.current
    if (!panel) return

    const getFocusable = () =>
      Array.from(panel.querySelectorAll<HTMLElement>(focusableSelector)).filter(
        (element) => !element.hasAttribute('disabled') && element.tabIndex !== -1,
      )

    window.requestAnimationFrame(() => {
      ;(getFocusable()[0] || panel).focus()
    })

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        event.preventDefault()
        setMobileMenuOpen(false)
        trigger?.focus()
        return
      }

      if (event.key !== 'Tab') return

      const focusable = getFocusable()
      if (!focusable.length) {
        event.preventDefault()
        panel.focus()
        return
      }

      const first = focusable[0]
      const last = focusable[focusable.length - 1]
      const active = document.activeElement

      if (event.shiftKey && active === first) {
        event.preventDefault()
        last.focus()
      } else if (!event.shiftKey && active === last) {
        event.preventDefault()
        first.focus()
      }
    }

    document.addEventListener('keydown', handleKeyDown)
    return () => document.removeEventListener('keydown', handleKeyDown)
  }, [mobileMenuOpen])

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

  const renderNavGroups = (compact = false, collapsed = false) =>
    groups.map((group) => (
      <section key={group.label} className="space-y-2">
        <p className={cn('px-1 text-xs font-semibold uppercase tracking-wide text-muted-foreground', compact && 'pt-2', collapsed && 'sr-only')}>{group.label}</p>
        <div className="space-y-1">
          {group.items.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.to === '/'}
              className={({ isActive }) =>
                cn(
                  'flex min-h-11 items-center gap-2 rounded-lg px-3 py-2 text-sm transition hover:bg-muted',
                  collapsed && 'justify-center px-2',
                  isActive && 'bg-primary/10 font-medium text-primary',
                )
              }
              title={collapsed ? item.label : undefined}
            >
              <item.icon aria-hidden="true" className="h-4 w-4 shrink-0" />
              <span className={cn(collapsed && 'sr-only')}>{item.label}</span>
            </NavLink>
          ))}
        </div>
      </section>
    ))

  const mobileTabs = useMemo(
    () =>
      [
        { to: '/dashboard', label: 'Home', icon: LayoutDashboard },
        { to: '/students', label: 'Students', icon: Users },
        { to: '/assignments', label: 'Tasks', icon: ClipboardCheck },
        { to: '/upload', label: 'Upload', icon: Upload },
        { to: '/notifications', label: 'Alerts', icon: Bell },
      ].filter((item) => groups.some((group) => group.items.some((navItem) => navItem.to === item.to))),
    [groups],
  )

  const desktopSidebarCollapsed = preferences.sidebar_position === 'collapsed'
  const desktopSidebarOnRight = preferences.sidebar_position === 'right'

  return (
    <div className="min-h-screen bg-muted/20">
      <a
        href="#main-content"
        className="sr-only absolute left-4 top-4 z-50 rounded-md bg-background px-4 py-2 text-sm font-medium text-foreground shadow focus:not-sr-only focus:outline-none focus-visible:ring-4 focus-visible:ring-ring/40"
      >
        Skip to main content
      </a>
      <div aria-live="polite" className="sr-only">
        {unreadCount ? `${unreadCount} unread notification${unreadCount === 1 ? '' : 's'}.` : 'No unread notifications.'}
      </div>
      <div className="mx-auto max-w-7xl px-3 py-4 pb-24 md:px-6 md:pb-6">
        <div className={cn('grid gap-4', desktopSidebarCollapsed ? 'md:grid-cols-[92px_minmax(0,1fr)]' : 'md:grid-cols-[260px_minmax(0,1fr)]')}>
          <aside aria-label="Workspace navigation" className={cn('hidden md:block', desktopSidebarOnRight && 'md:order-2')}>
            <div className="sticky top-4 max-h-[calc(100vh-2rem)] space-y-4 overflow-y-auto rounded-xl border bg-card p-4 shadow-sm">
              <div>
                <p className="text-lg font-bold">{desktopSidebarCollapsed ? 'HH' : 'Homeschool Hero'}</p>
                {!desktopSidebarCollapsed ? <p className="text-sm text-muted-foreground">{familyName || 'Family workspace'}</p> : null}
              </div>
              <div className={cn('rounded-lg border bg-muted/30 p-3 text-sm', desktopSidebarCollapsed && 'px-2 text-center')}>
                <p className="font-medium">{desktopSidebarCollapsed ? userName.slice(0, 1).toUpperCase() : userName}</p>
                {!desktopSidebarCollapsed ? <p className="text-xs text-muted-foreground">{role ? roleLabels[role] : 'Signed in'}</p> : null}
              </div>
              <nav aria-label="Primary navigation" className="space-y-4">
                {renderNavGroups(false, desktopSidebarCollapsed)}
              </nav>
            </div>
          </aside>

          <div className={cn('min-w-0 space-y-4', desktopSidebarOnRight && 'md:order-1')}>
            <header className="rounded-xl border bg-card p-4 shadow-sm">
              <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
                <div className="space-y-2">
                  <div className="flex items-center justify-between gap-3 md:hidden">
                    <div>
                      <p className="text-lg font-bold">Homeschool Hero</p>
                      <p className="text-sm text-muted-foreground">{familyName || 'Family workspace'}</p>
                    </div>
                    <Button
                      ref={mobileMenuButtonRef}
                      type="button"
                      variant="outline"
                      size="icon"
                      aria-label="Open navigation"
                      aria-controls="mobile-navigation-panel"
                      aria-expanded={mobileMenuOpen}
                      onClick={() => setMobileMenuOpen(true)}
                    >
                      <Menu aria-hidden="true" className="h-5 w-5" />
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
                      <label htmlFor="global-search-input" className="sr-only">
                        Search the workspace
                      </label>
                      <Search aria-hidden="true" className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                      <Input
                        id="global-search-input"
                        value={searchValue}
                        onChange={(event) => setSearchValue(event.target.value)}
                        placeholder="Search everything"
                        aria-describedby="global-search-help"
                        className="pl-9 pr-16"
                      />
                      <span aria-hidden="true" className="pointer-events-none absolute right-3 top-1/2 hidden -translate-y-1/2 text-xs text-muted-foreground md:block">
                        Ctrl/Cmd+K
                      </span>
                    </div>
                    <Button type="submit" variant="outline">
                      Search
                    </Button>
                  </form>
                  <p id="global-search-help" className="sr-only">
                    Press Control or Command plus K to focus the global search field.
                  </p>

                  <div className="relative flex flex-wrap items-center gap-2">
                    <Button
                      ref={notificationsButtonRef}
                      type="button"
                      variant="outline"
                      className="relative"
                      aria-controls="notifications-panel"
                      aria-expanded={notificationsOpen}
                      aria-haspopup="dialog"
                      onClick={() => setNotificationsOpen((current) => !current)}
                    >
                      <Bell aria-hidden="true" className="mr-2 h-4 w-4" />
                      Notifications
                      {unreadCount ? (
                        <span aria-hidden="true" className="absolute -right-2 -top-2 rounded-full bg-primary px-1.5 py-0.5 text-[10px] font-semibold text-primary-foreground">
                          {unreadCount > 99 ? '99+' : unreadCount}
                        </span>
                      ) : null}
                    </Button>
                    {notificationsOpen ? (
                      <div
                        ref={notificationsPanelRef}
                        id="notifications-panel"
                        role="dialog"
                        aria-modal="false"
                        aria-labelledby="notifications-panel-title"
                        tabIndex={-1}
                        className="absolute right-0 top-12 z-20 w-[min(28rem,90vw)] rounded-xl border bg-popover p-3 shadow-lg"
                      >
                        <div className="mb-3 flex items-center justify-between gap-3">
                          <div>
                            <p id="notifications-panel-title" className="font-semibold">
                              Recent notifications
                            </p>
                            <p className="text-xs text-muted-foreground">{unreadCount} unread</p>
                          </div>
                          <Button size="sm" variant="ghost" onClick={() => void markAllAsRead()} disabled={!unreadCount}>
                            Mark all read
                          </Button>
                        </div>
                        <div aria-live="polite" className="space-y-2">
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
                      <LogOut aria-hidden="true" className="mr-2 h-4 w-4" />
                      Log out
                    </Button>
                  </div>
                </div>
              </div>
            </header>

            {!isOnline ? (
              <div role="status" aria-live="polite" className="rounded-xl border border-amber-300 bg-amber-50 px-4 py-3 text-sm text-amber-900">
                <div className="flex items-start gap-3">
                  <WifiOff aria-hidden="true" className="mt-0.5 h-4 w-4 shrink-0" />
                  <div>
                    <p className="font-medium">Offline mode</p>
                    <p>Cached pages are still available. New changes will resume when your connection returns.</p>
                  </div>
                </div>
              </div>
            ) : null}

            {canInstall ? (
              <div role="status" aria-live="polite" className="rounded-xl border border-primary/20 bg-primary/5 px-4 py-3 text-sm">
                <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                  <div className="flex items-start gap-3">
                    <Smartphone aria-hidden="true" className="mt-0.5 h-4 w-4 shrink-0 text-primary" />
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
              <div role="status" aria-live="polite" className="rounded-xl border border-sky-300 bg-sky-50 px-4 py-3 text-sm text-sky-950">
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
              <div role="status" aria-live="polite" className="rounded-xl border border-emerald-300 bg-emerald-50 px-4 py-3 text-sm text-emerald-950">
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

            <main id="main-content" tabIndex={-1} className="space-y-4">
              {children}
            </main>
          </div>
        </div>
      </div>

      {mobileMenuOpen ? (
        <div className="fixed inset-0 z-40 md:hidden">
          <button type="button" tabIndex={-1} className="absolute inset-0 bg-black/40" aria-label="Close navigation" onClick={() => setMobileMenuOpen(false)} />
          <aside
            ref={mobileMenuPanelRef}
            id="mobile-navigation-panel"
            role="dialog"
            aria-modal="true"
            aria-labelledby="mobile-navigation-title"
            tabIndex={-1}
            className="absolute inset-y-0 left-0 flex w-[min(22rem,88vw)] flex-col gap-4 overflow-y-auto border-r bg-card p-4 shadow-xl"
          >
            <div className="flex items-center justify-between gap-3">
              <div>
                <p id="mobile-navigation-title" className="text-lg font-bold">
                  Homeschool Hero
                </p>
                <p className="text-sm text-muted-foreground">{familyName || 'Family workspace'}</p>
              </div>
              <Button type="button" variant="ghost" size="icon" aria-label="Close navigation" onClick={() => setMobileMenuOpen(false)}>
                <X aria-hidden="true" className="h-5 w-5" />
              </Button>
            </div>
            <div className="rounded-lg border bg-muted/30 p-3 text-sm">
              <p className="font-medium">{userName}</p>
              <p className="text-xs text-muted-foreground">{role ? roleLabels[role] : 'Signed in'}</p>
            </div>
            <nav aria-label="Mobile navigation" className="space-y-4">
              {renderNavGroups(true)}
            </nav>
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
                <item.icon aria-hidden="true" className="h-4 w-4" />
                <span>{item.label}</span>
              </NavLink>
            ))}
          </div>
        </nav>
      ) : null}
    </div>
  )
}
