import { useCallback, useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import type { Notification } from '@/types/api'
import { api } from '@/lib/api'
import { useNotifications } from '@/context/NotificationsContext'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { LoadingState } from '@/components/common/LoadingState'
import { ErrorState } from '@/components/common/ErrorState'
import { EmptyState } from '@/components/common/EmptyState'

type ReadFilter = 'all' | 'unread' | 'read'

function toReadFilterValue(filter: ReadFilter) {
  if (filter === 'all') return undefined
  return filter === 'read'
}

export function NotificationsPage() {
  const navigate = useNavigate()
  const { unreadCount, markAllAsRead, markAsRead, refresh } = useNotifications()
  const [items, setItems] = useState<Notification[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [page, setPage] = useState(1)
  const [totalPages, setTotalPages] = useState(1)
  const [total, setTotal] = useState(0)
  const [filter, setFilter] = useState<ReadFilter>('all')

  const query = useMemo(() => ({ page, page_size: 12, read: toReadFilterValue(filter) }), [filter, page])

  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const response = await api.listNotifications(query)
      setItems(response.items)
      setTotal(response.total)
      setTotalPages(response.total_pages)
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : 'Unable to load notifications')
    } finally {
      setLoading(false)
    }
  }, [query])

  useEffect(() => {
    void load()
  }, [load])

  const openNotification = async (notification: Notification) => {
    if (!notification.read) {
      await markAsRead(notification.id)
    }
    await refresh()
    await load()
    if (notification.link?.startsWith('http://') || notification.link?.startsWith('https://')) {
      window.location.href = notification.link
      return
    }
    navigate(notification.link || '/dashboard')
  }

  if (loading) return <LoadingState message="Loading notifications…" />
  if (error) return <ErrorState message={error} onRetry={() => void load()} />

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <CardTitle>Notifications</CardTitle>
          <CardDescription>Keep up with due dates, grading updates, backups, and security alerts.</CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
          <div className="flex flex-wrap items-center gap-2">
            <Badge variant={unreadCount ? 'secondary' : 'outline'}>{unreadCount} unread</Badge>
            <Badge variant="outline">{total} total</Badge>
          </div>
          <div className="flex flex-col gap-2 sm:flex-row">
            <Select
              value={filter}
              onValueChange={(value: ReadFilter) => {
                setFilter(value)
                setPage(1)
              }}
            >
              <SelectTrigger className="w-full sm:w-40">
                <SelectValue placeholder="Filter" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All</SelectItem>
                <SelectItem value="unread">Unread</SelectItem>
                <SelectItem value="read">Read</SelectItem>
              </SelectContent>
            </Select>
            <Button variant="outline" onClick={() => void markAllAsRead().then(refresh).then(load)}>
              Mark all read
            </Button>
          </div>
        </CardContent>
      </Card>

      {items.length ? (
        <div className="space-y-3">
          {items.map((notification) => (
            <Card key={notification.id} className={!notification.read ? 'border-primary/40' : undefined}>
              <CardContent className="flex flex-col gap-3 p-4 md:flex-row md:items-start md:justify-between">
                <div className="space-y-2">
                  <div className="flex flex-wrap items-center gap-2">
                    <p className="font-medium">{notification.title}</p>
                    <Badge variant={notification.read ? 'outline' : 'secondary'}>{notification.type.replace('_', ' ')}</Badge>
                    {!notification.read ? <Badge variant="default">Unread</Badge> : null}
                  </div>
                  <p className="text-sm text-muted-foreground">{notification.message}</p>
                  <p className="text-xs text-muted-foreground">{new Date(notification.created_at).toLocaleString()}</p>
                </div>
                <div className="flex flex-wrap gap-2">
                  {!notification.read ? (
                    <Button size="sm" variant="outline" onClick={() => void markAsRead(notification.id).then(refresh).then(load)}>
                      Mark read
                    </Button>
                  ) : null}
                  <Button size="sm" onClick={() => void openNotification(notification)}>
                    Open
                  </Button>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      ) : (
        <EmptyState title="No notifications" description="New updates will appear here as soon as they happen." />
      )}

      <div className="flex items-center justify-between gap-3">
        <p className="text-sm text-muted-foreground">
          Page {page} of {Math.max(totalPages, 1)}
        </p>
        <div className="flex gap-2">
          <Button variant="outline" disabled={page <= 1} onClick={() => setPage((current) => Math.max(1, current - 1))}>
            Previous
          </Button>
          <Button variant="outline" disabled={page >= totalPages} onClick={() => setPage((current) => current + 1)}>
            Next
          </Button>
        </div>
      </div>
    </div>
  )
}
