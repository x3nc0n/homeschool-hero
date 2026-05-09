import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import type { Notification } from '@/types/api'
import { api } from '@/lib/api'
import { useAuth } from '@/context/AuthContext'

type NotificationsContextValue = {
  recent: Notification[]
  unreadCount: number
  loading: boolean
  refresh: () => Promise<void>
  markAsRead: (id: number) => Promise<void>
  markAllAsRead: () => Promise<void>
}

const NotificationsContext = createContext<NotificationsContextValue | undefined>(undefined)

export function NotificationsProvider({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, loading: authLoading } = useAuth()
  const [recent, setRecent] = useState<Notification[]>([])
  const [unreadCount, setUnreadCount] = useState(0)
  const [loading, setLoading] = useState(false)

  const refresh = useCallback(async () => {
    if (!isAuthenticated) {
      setRecent([])
      setUnreadCount(0)
      return
    }

    setLoading(true)
    try {
      const response = await api.listNotifications({ page: 1, page_size: 6 })
      setRecent(response.items)
      setUnreadCount(response.unread_count)
    } finally {
      setLoading(false)
    }
  }, [isAuthenticated])

  useEffect(() => {
    if (authLoading) return
    if (!isAuthenticated) {
      setRecent([])
      setUnreadCount(0)
      return
    }

    void refresh()
    const timer = window.setInterval(() => {
      void refresh()
    }, 60000)
    return () => window.clearInterval(timer)
  }, [authLoading, isAuthenticated, refresh])

  const markAsRead = useCallback(async (id: number) => {
    await api.markNotificationRead(id)
    setRecent((current) =>
      current.map((notification) => (notification.id === id ? { ...notification, read: true } : notification)),
    )
    setUnreadCount((current) => Math.max(0, current - 1))
  }, [])

  const markAllAsRead = useCallback(async () => {
    await api.markAllNotificationsRead()
    setRecent((current) => current.map((notification) => ({ ...notification, read: true })))
    setUnreadCount(0)
  }, [])

  const value = useMemo(
    () => ({
      recent,
      unreadCount,
      loading,
      refresh,
      markAsRead,
      markAllAsRead,
    }),
    [loading, markAllAsRead, markAsRead, recent, refresh, unreadCount],
  )

  return <NotificationsContext.Provider value={value}>{children}</NotificationsContext.Provider>
}

export function useNotifications() {
  const context = useContext(NotificationsContext)
  if (!context) {
    throw new Error('useNotifications must be used inside NotificationsProvider')
  }
  return context
}
