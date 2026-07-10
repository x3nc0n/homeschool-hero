import { type FormEvent, useEffect, useMemo, useRef, useState } from 'react'
import {
  BarChart,
  Bell,
  BookOpen,
  BookOpenCheck,
  Calendar,
  CalendarDays,
  ChevronDown,
  ChevronUp,
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
import { useTranslation } from 'react-i18next'
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
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip'

type NavItem = {
  to: string
  labelKey: string
  icon: typeof LayoutDashboard
  capabilities?: string[]
  appRoles?: AppRole[]
  feature?: string
}

// First PINNED_COUNT items are always visible. Items after are behind the "More" disclosure.
// Ordered by daily-use priority for a typical parent.
const PINNED_COUNT = 6

const ALL_NAV_ITEMS: NavItem[] = [
  { to: '/dashboard', labelKey: 'navItems.dashboard', icon: LayoutDashboard },
  { to: '/upload', labelKey: 'navItems.upload', icon: Upload, capabilities: ['manage_submissions'] },
  {
    to: '/assignments',
    labelKey: 'navItems.assignments',
    icon: FileText,
    capabilities: ['manage_curriculum', 'manage_grading', 'manage_submissions', 'view_own_progress', 'read_curriculum', 'read_submissions', 'read_grades'],
    appRoles: ['student'],
  },
  {
    to: '/grades',
    labelKey: 'navItems.grades',
    icon: BarChart,
    capabilities: ['manage_curriculum', 'manage_grading', 'manage_submissions', 'view_own_progress', 'read_grades'],
    appRoles: ['student'],
  },
  { to: '/calendar', labelKey: 'navItems.calendar', icon: Calendar, capabilities: ['manage_curriculum', 'manage_grading', 'manage_submissions'] },
  { to: '/students', labelKey: 'navItems.students', icon: Users, capabilities: ['manage_household', 'manage_family', 'manage_curriculum'] },
  // ── More section ──
  { to: '/subjects', labelKey: 'navItems.subjects', icon: BookOpen, capabilities: ['manage_curriculum', 'manage_grading', 'manage_submissions'] },
  {
    to: '/curriculum',
    labelKey: 'navItems.curriculum',
    icon: GraduationCap,
    capabilities: ['manage_curriculum', 'manage_grading', 'manage_submissions', 'view_own_progress', 'read_curriculum', 'read_grades'],
    appRoles: ['student'],
  },
  {
    to: '/planner',
    labelKey: 'navItems.planner',
    icon: CalendarDays,
    capabilities: ['manage_curriculum', 'manage_grading', 'manage_submissions', 'view_own_progress', 'read_curriculum', 'read_grades'],
    appRoles: ['student'],
    feature: 'planner',
  },
  { to: '/attendance', labelKey: 'navItems.attendance', icon: UserCheck, capabilities: ['manage_curriculum', 'manage_grading', 'manage_submissions'], feature: 'attendance' },
  { to: '/quizzes', labelKey: 'navItems.quizzes', icon: ClipboardCheck, capabilities: ['manage_grading'], feature: 'quizzes' },
  {
    to: '/academic-records',
    labelKey: 'navItems.academicRecords',
    icon: FileStack,
    capabilities: ['manage_curriculum', 'manage_grading', 'manage_submissions', 'view_own_progress', 'read_grades', 'read_curriculum'],
    appRoles: ['student'],
  },
  {
    to: '/portfolio',
    labelKey: 'navItems.portfolio',
    icon: BookOpenCheck,
    capabilities: ['manage_curriculum', 'manage_grading', 'manage_submissions', 'view_own_progress', 'read_grades', 'read_curriculum'],
    appRoles: ['student'],
    feature: 'portfolio',
  },
  {
    to: '/compliance',
    labelKey: 'navItems.compliance',
    icon: ShieldCheck,
    capabilities: ['manage_curriculum', 'manage_grading', 'manage_submissions', 'view_own_progress', 'read_grades', 'read_curriculum'],
    appRoles: ['student'],
    feature: 'compliance',
  },
  { to: '/settings/family', labelKey: 'navItems.family', icon: Settings, capabilities: ['manage_household', 'manage_family'] },
  { to: '/data', labelKey: 'navItems.dataManagement', icon: Database, capabilities: ['manage_curriculum', 'manage_grading', 'manage_submissions', 'manage_platform'] },
  { to: '/settings/appearance', labelKey: 'navItems.appearance', icon: Palette },
  { to: '/notifications/preferences', labelKey: 'navItems.notificationSettings', icon: Bell },
]

const focusableSelector = [
  'a[href]',
  'button:not([disabled])',
  'input:not([disabled])',
  'select:not([disabled])',
  'textarea:not([disabled])',
  '[tabindex]:not([tabindex="-1"])',
].join(', ')

export function AppShell({ children }: { children: React.ReactNode }) {
  const { t } = useTranslation('common')
  const { logout, userName, familyName, role, enabledFeatures, hasCapability, hasRole } = useAuth()
  const { preferences } = useTheme()
  const { recent, unreadCount, markAllAsRead, markAsRead } = useNotifications()
  const { canInstall, installApp, isOfflineReady, isOnline, needsRefresh, dismissOfflineReady, applyUpdate } = usePwa()
  const location = useLocation()
  const navigate = useNavigate()
  const [notificationsOpen, setNotificationsOpen] = useState(false)
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false)
  const [moreExpanded, setMoreExpanded] = useState(false)
  const currentSearchQuery = useMemo(() => new URLSearchParams(location.search).get('q') || '', [location.search])
  const [searchValue, setSearchValue] = useState(currentSearchQuery)
  const notificationsButtonRef = useRef<HTMLButtonElement | null>(null)
  const notificationsPanelRef = useRef<HTMLDivElement | null>(null)
  const mobileMenuButtonRef = useRef<HTMLButtonElement | null>(null)
  const mobileMenuPanelRef = useRef<HTMLElement | null>(null)

  const visibleItems = useMemo(
    () =>
      ALL_NAV_ITEMS.filter((item) => {
        const capabilityMatch = item.capabilities?.some((cap) => hasCapability(cap)) ?? false
        const roleMatch = item.appRoles?.some((appRole) => hasRole(appRole)) ?? false
        const hasAccess = (!item.capabilities?.length && !item.appRoles?.length) || capabilityMatch || roleMatch
        return hasAccess && (item.feature ? enabledFeatures[item.feature] !== false : true)
      }),
    [enabledFeatures, hasCapability, hasRole],
  )

  const pinnedItems = useMemo(() => visibleItems.slice(0, PINNED_COUNT), [visibleItems])
  const moreItems = useMemo(() => visibleItems.slice(PINNED_COUNT), [visibleItems])

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

  const renderNavItem = (item: NavItem, collapsed = false) => {
    const label = t(item.labelKey)
    const link = (
      <NavLink
        to={item.to}
        end={item.to === '/'}
        className={({ isActive }) =>
          cn(
            'flex min-h-11 items-center gap-2 rounded-lg px-3 py-2 text-sm transition hover:bg-muted',
            collapsed && 'justify-center px-2',
            isActive && 'bg-primary/10 font-medium text-primary',
          )
        }
      >
        <item.icon aria-hidden="true" className="h-4 w-4 shrink-0" />
        <span className={cn(collapsed && 'sr-only')}>{label}</span>
      </NavLink>
    )

    if (collapsed) {
      return (
        <Tooltip key={item.to}>
          <TooltipTrigger asChild>{link}</TooltipTrigger>
          <TooltipContent side="right">{label}</TooltipContent>
        </Tooltip>
      )
    }

    return <NavLink
      key={item.to}
      to={item.to}
      end={item.to === '/'}
      className={({ isActive }) =>
        cn(
          'flex min-h-11 items-center gap-2 rounded-lg px-3 py-2 text-sm transition hover:bg-muted',
          isActive && 'bg-primary/10 font-medium text-primary',
        )
      }
    >
      <item.icon aria-hidden="true" className="h-4 w-4 shrink-0" />
      <span>{label}</span>
    </NavLink>
  }

  const renderNav = (collapsed = false) => {
    const moreToggleInner = (
      <button
        type="button"
        aria-expanded={moreExpanded}
        aria-controls="nav-more-items"
        aria-label={moreExpanded ? t('nav.lessLabel') : t('nav.moreLabel')}
        onClick={() => setMoreExpanded((prev) => !prev)}
        className={cn(
          'flex min-h-11 w-full items-center gap-2 rounded-lg px-3 py-2 text-sm text-muted-foreground transition hover:bg-muted hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
          collapsed && 'justify-center px-2',
        )}
      >
        {moreExpanded ? (
          <ChevronUp aria-hidden="true" className="h-4 w-4 shrink-0" />
        ) : (
          <ChevronDown aria-hidden="true" className="h-4 w-4 shrink-0" />
        )}
        <span className={cn(collapsed && 'sr-only')}>{moreExpanded ? t('nav.less') : t('nav.more')}</span>
      </button>
    )

    return (
      <div className="space-y-1">
        {pinnedItems.map((item) => renderNavItem(item, collapsed))}
        {moreItems.length > 0 && (
          <>
            <div className="border-t border-border/40 pt-1">
              {collapsed ? (
                <Tooltip>
                  <TooltipTrigger asChild>{moreToggleInner}</TooltipTrigger>
                  <TooltipContent side="right">{moreExpanded ? t('nav.less') : t('nav.more')}</TooltipContent>
                </Tooltip>
              ) : (
                moreToggleInner
              )}
            </div>
            {moreExpanded ? (
              <div id="nav-more-items" className="space-y-1">
                {moreItems.map((item) => renderNavItem(item, collapsed))}
              </div>
            ) : null}
          </>
        )}
      </div>
    )
  }

  const mobileTabs = useMemo(
    () =>
      [
        { to: '/dashboard', labelKey: 'mobileTabs.home', icon: LayoutDashboard },
        { to: '/students', labelKey: 'mobileTabs.students', icon: Users },
        { to: '/assignments', labelKey: 'mobileTabs.tasks', icon: ClipboardCheck },
        { to: '/upload', labelKey: 'mobileTabs.upload', icon: Upload },
        { to: '/notifications', labelKey: 'mobileTabs.alerts', icon: Bell },
      ].filter((item) => visibleItems.some((navItem) => navItem.to === item.to)),
    [visibleItems],
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
        {unreadCount ? t('notifications.unreadCount_other', { count: unreadCount }) : ''}
      </div>
      <div className="mx-auto max-w-7xl px-3 py-4 pb-24 md:px-6 md:pb-6">
        <div className={cn('grid gap-4', desktopSidebarCollapsed ? 'md:grid-cols-[92px_minmax(0,1fr)]' : 'md:grid-cols-[260px_minmax(0,1fr)]')}>
          <aside aria-label={t('nav.ariaWorkspace')} className={cn('hidden md:block', desktopSidebarOnRight && 'md:order-2')}>
            <div className="sticky top-4 max-h-[calc(100vh-2rem)] space-y-4 overflow-y-auto rounded-xl border bg-card p-4 shadow-sm">
              <div>
                <p className="text-lg font-bold">{desktopSidebarCollapsed ? 'HH' : t('appName')}</p>
                {!desktopSidebarCollapsed ? <p className="text-sm text-muted-foreground">{familyName || t('workspace.family')}</p> : null}
              </div>
              <div className={cn('rounded-lg border bg-muted/30 p-3 text-sm', desktopSidebarCollapsed && 'px-2 text-center')}>
                <p className="font-medium">{desktopSidebarCollapsed ? userName.slice(0, 1).toUpperCase() : userName}</p>
                {!desktopSidebarCollapsed ? (
                  <p className="text-xs text-muted-foreground">
                    {role ? t(`roles.${role as FamilyRole}`) : t('workspace.signedIn')}
                  </p>
                ) : null}
              </div>
              <TooltipProvider delayDuration={200}>
                <nav aria-label={t('nav.ariaPrimary')} className="space-y-1">
                  {renderNav(desktopSidebarCollapsed)}
                </nav>
              </TooltipProvider>
              {!desktopSidebarCollapsed ? (
                <div className="border-t border-border/40 pt-2">
                  <Button type="button" variant="ghost" size="sm" className="w-full justify-start gap-2 text-muted-foreground hover:text-foreground" onClick={() => void logout()}>
                    <LogOut aria-hidden="true" className="h-4 w-4 shrink-0" />
                    {t('buttons.logOut')}
                  </Button>
                </div>
              ) : (
                <div className="border-t border-border/40 pt-2">
                  <TooltipProvider delayDuration={200}>
                    <Tooltip>
                      <TooltipTrigger asChild>
                        <Button
                          type="button"
                          variant="ghost"
                          size="icon"
                          className="w-full text-muted-foreground hover:text-foreground"
                          aria-label={t('buttons.logOut')}
                          onClick={() => void logout()}
                        >
                          <LogOut aria-hidden="true" className="h-4 w-4" />
                        </Button>
                      </TooltipTrigger>
                      <TooltipContent side="right">{t('buttons.logOut')}</TooltipContent>
                    </Tooltip>
                  </TooltipProvider>
                </div>
              )}
            </div>
          </aside>

          <div className={cn('min-w-0 space-y-4', desktopSidebarOnRight && 'md:order-1')}>
            <header className="rounded-xl border bg-card px-4 py-3 shadow-sm">
              <div className="flex items-center justify-between gap-3">
                <div className="flex min-w-0 items-center gap-3">
                  <Button
                    ref={mobileMenuButtonRef}
                    type="button"
                    variant="outline"
                    size="icon"
                    className="shrink-0 md:hidden"
                    aria-label={t('header.openNav')}
                    aria-controls="mobile-navigation-panel"
                    aria-expanded={mobileMenuOpen}
                    onClick={() => setMobileMenuOpen(true)}
                  >
                    <Menu aria-hidden="true" className="h-5 w-5" />
                  </Button>
                  <Breadcrumbs />
                </div>

                <div className="flex items-center gap-1.5">
                  <form onSubmit={submitSearch} className="hidden sm:block" role="search">
                    <div className="relative">
                      <label htmlFor="global-search-input" className="sr-only">
                        {t('header.searchLabel')}
                      </label>
                      <Search aria-hidden="true" className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                      <Input
                        id="global-search-input"
                        value={searchValue}
                        onChange={(event) => setSearchValue(event.target.value)}
                        placeholder={t('search.placeholder')}
                        aria-describedby="global-search-help"
                        className="w-44 pl-9 pr-14 lg:w-60"
                      />
                      <span aria-hidden="true" className="pointer-events-none absolute right-3 top-1/2 hidden -translate-y-1/2 text-xs text-muted-foreground md:block">
                        Ctrl+K
                      </span>
                    </div>
                  </form>
                  <p id="global-search-help" className="sr-only">
                    {t('header.searchShortcutHint')}
                  </p>

                  <div className="relative">
                    <Button
                      ref={notificationsButtonRef}
                      type="button"
                      variant="ghost"
                      size="icon"
                      aria-label={unreadCount ? t('header.notificationsLabel', { count: unreadCount }) : t('notifications.title')}
                      aria-controls="notifications-panel"
                      aria-expanded={notificationsOpen}
                      aria-haspopup="dialog"
                      onClick={() => setNotificationsOpen((current) => !current)}
                    >
                      <Bell aria-hidden="true" className="h-5 w-5" />
                      {unreadCount ? (
                        <span aria-hidden="true" className="absolute -right-1 -top-1 rounded-full bg-primary px-1.5 py-0.5 text-[10px] font-semibold text-primary-foreground">
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
                              {t('notifications.recent')}
                            </p>
                            <p className="text-xs text-muted-foreground">
                              {unreadCount ? t('notifications.unreadCount_other', { count: unreadCount }) : t('notifications.caughtUp')}
                            </p>
                          </div>
                          <Button size="sm" variant="ghost" onClick={() => void markAllAsRead()} disabled={!unreadCount}>
                            {t('buttons.markAllRead')}
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
                            <p className="rounded-lg border border-dashed p-6 text-center text-sm text-muted-foreground">{t('notifications.caughtUp')}</p>
                          )}
                        </div>
                        <div className="mt-3 flex items-center justify-between gap-2">
                          <Button size="sm" variant="outline" onClick={() => void openNotification('/notifications')}>
                            {t('buttons.viewAll')}
                          </Button>
                          <Button size="sm" variant="ghost" onClick={() => void openNotification('/settings/notifications')}>
                            {t('buttons.preferences')}
                          </Button>
                        </div>
                      </div>
                    ) : null}
                  </div>

                  <Button
                    type="button"
                    variant="ghost"
                    size="icon"
                    className="md:hidden"
                    aria-label={t('buttons.logOut')}
                    onClick={() => void logout()}
                  >
                    <LogOut aria-hidden="true" className="h-5 w-5" />
                  </Button>
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
                      <p className="font-medium">{t('appName')}</p>
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
                    <p>A newer version of {t('appName')} is available.</p>
                  </div>
                  <Button type="button" variant="outline" onClick={() => void applyUpdate()}>
                    {t('buttons.refresh')}
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
          <button type="button" tabIndex={-1} className="absolute inset-0 bg-black/40" aria-label={t('header.closeNav')} onClick={() => setMobileMenuOpen(false)} />
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
                  {t('appName')}
                </p>
                <p className="text-sm text-muted-foreground">{familyName || t('workspace.family')}</p>
              </div>
              <Button type="button" variant="ghost" size="icon" aria-label={t('header.closeNav')} onClick={() => setMobileMenuOpen(false)}>
                <X aria-hidden="true" className="h-5 w-5" />
              </Button>
            </div>
            <div className="rounded-lg border bg-muted/30 p-3 text-sm">
              <p className="font-medium">{userName}</p>
              <p className="text-xs text-muted-foreground">
                {role ? t(`roles.${role as FamilyRole}`) : t('workspace.signedIn')}
              </p>
            </div>
            <nav aria-label={t('nav.ariaMobile')} className="space-y-1">
              {renderNav(false)}
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
                <span>{t(item.labelKey)}</span>
              </NavLink>
            ))}
          </div>
        </nav>
      ) : null}
    </div>
  )
}
