import { useCallback, useEffect, useMemo, useState } from 'react'
import type { AuditAction, AuditEvent, AuditEventFilters } from '@/types/api'
import { api } from '@/lib/api'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { LoadingState } from '@/components/common/LoadingState'
import { ErrorState } from '@/components/common/ErrorState'
import { EmptyState } from '@/components/common/EmptyState'

const actionOptions: Array<{ value: AuditAction; label: string }> = [
  { value: 'login', label: 'Login' },
  { value: 'logout', label: 'Logout' },
  { value: 'grade_create', label: 'Grade created' },
  { value: 'grade_update', label: 'Grade updated' },
  { value: 'invitation_create', label: 'Invitation created' },
  { value: 'invitation_accept', label: 'Invitation accepted' },
]

const entityTypeOptions = [
  { value: 'session', label: 'Session' },
  { value: 'grade', label: 'Grade' },
  { value: 'invitation', label: 'Invitation' },
]

function toQueryDate(value: string, endOfDay = false) {
  if (!value) {
    return undefined
  }
  const suffix = endOfDay ? 'T23:59:59.999Z' : 'T00:00:00.000Z'
  return `${value}${suffix}`
}

function summarizeChanges(event: AuditEvent) {
  if (!event.before_snapshot && !event.after_snapshot) {
    return '—'
  }
  const after = event.after_snapshot || {}
  const before = event.before_snapshot || {}
  const keys = Array.from(new Set([...Object.keys(before), ...Object.keys(after)])).slice(0, 3)
  if (!keys.length) {
    return '—'
  }
  return keys
    .map((key) => `${key}: ${JSON.stringify(before[key] ?? '—')} → ${JSON.stringify(after[key] ?? '—')}`)
    .join(' · ')
}

export function AuditLogPage() {
  const [events, setEvents] = useState<AuditEvent[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [page, setPage] = useState(1)
  const [totalPages, setTotalPages] = useState(0)
  const [total, setTotal] = useState(0)
  const [filters, setFilters] = useState({
    actor: '',
    action: 'all',
    entity_type: 'all',
    date_from: '',
    date_to: '',
  })

  const query = useMemo<AuditEventFilters>(
    () => ({
      page,
      page_size: 10,
      actor: filters.actor || undefined,
      action: filters.action as AuditAction | 'all',
      entity_type: filters.entity_type === 'all' ? undefined : filters.entity_type,
      date_from: toQueryDate(filters.date_from),
      date_to: toQueryDate(filters.date_to, true),
    }),
    [filters, page],
  )

  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const response = await api.listAuditEvents(query)
      setEvents(response.items)
      setTotal(response.total)
      setTotalPages(response.total_pages)
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : 'Unable to load audit log')
    } finally {
      setLoading(false)
    }
  }, [query])

  useEffect(() => {
    void load()
  }, [load])

  if (loading) return <LoadingState message="Loading audit log…" />
  if (error) return <ErrorState message={error} onRetry={() => void load()} />

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <CardTitle>Audit log</CardTitle>
          <CardDescription>Track sign-ins, grade changes, and invitation activity across your family workspace.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-5">
            <div className="space-y-2">
              <Label>From</Label>
              <Input
                type="date"
                value={filters.date_from}
                onChange={(event) => setFilters((prev) => ({ ...prev, date_from: event.target.value }))}
              />
            </div>
            <div className="space-y-2">
              <Label>To</Label>
              <Input
                type="date"
                value={filters.date_to}
                onChange={(event) => setFilters((prev) => ({ ...prev, date_to: event.target.value }))}
              />
            </div>
            <div className="space-y-2">
              <Label>Actor</Label>
              <Input
                value={filters.actor}
                onChange={(event) => setFilters((prev) => ({ ...prev, actor: event.target.value }))}
                placeholder="Name, email, or user id"
              />
            </div>
            <div className="space-y-2">
              <Label>Action</Label>
              <Select value={filters.action} onValueChange={(value) => setFilters((prev) => ({ ...prev, action: value }))}>
                <SelectTrigger>
                  <SelectValue placeholder="All actions" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All actions</SelectItem>
                  {actionOptions.map((option) => (
                    <SelectItem key={option.value} value={option.value}>
                      {option.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label>Entity type</Label>
              <Select value={filters.entity_type} onValueChange={(value) => setFilters((prev) => ({ ...prev, entity_type: value }))}>
                <SelectTrigger>
                  <SelectValue placeholder="All entities" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All entities</SelectItem>
                  {entityTypeOptions.map((option) => (
                    <SelectItem key={option.value} value={option.value}>
                      {option.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button onClick={() => setPage(1)}>Refresh</Button>
            <Button
              variant="outline"
              onClick={() => {
                setFilters({ actor: '', action: 'all', entity_type: 'all', date_from: '', date_to: '' })
                setPage(1)
              }}
            >
              Reset
            </Button>
            <p className="self-center text-sm text-muted-foreground">{total} events found</p>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Recent activity</CardTitle>
        </CardHeader>
        <CardContent>
          {events.length ? (
            <>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Timestamp</TableHead>
                    <TableHead>Actor</TableHead>
                    <TableHead>Action</TableHead>
                    <TableHead>Entity</TableHead>
                    <TableHead>IP</TableHead>
                    <TableHead className="min-w-[320px]">Changes</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {events.map((event) => (
                    <TableRow key={event.id}>
                      <TableCell>{new Date(event.timestamp).toLocaleString()}</TableCell>
                      <TableCell>
                        <div className="font-medium">{event.actor_display_name || `User #${event.actor_user_id}`}</div>
                        <div className="text-xs text-muted-foreground">{event.actor_email || '—'}</div>
                      </TableCell>
                      <TableCell>{event.action}</TableCell>
                      <TableCell>
                        {event.target_entity_type}
                        {event.target_entity_id ? ` #${event.target_entity_id}` : ''}
                      </TableCell>
                      <TableCell>{event.ip_address || '—'}</TableCell>
                      <TableCell className="max-w-[420px] whitespace-normal text-xs text-muted-foreground">
                        {summarizeChanges(event)}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
              <div className="mt-4 flex items-center justify-between">
                <p className="text-sm text-muted-foreground">
                  Page {page} of {Math.max(totalPages, 1)}
                </p>
                <div className="space-x-2">
                  <Button variant="outline" disabled={page <= 1} onClick={() => setPage((current) => Math.max(current - 1, 1))}>
                    Previous
                  </Button>
                  <Button
                    variant="outline"
                    disabled={totalPages > 0 ? page >= totalPages : true}
                    onClick={() => setPage((current) => current + 1)}
                  >
                    Next
                  </Button>
                </div>
              </div>
            </>
          ) : (
            <EmptyState title="No audit events yet" description="Audited activity will appear here after sign-ins, grade changes, and invitations." />
          )}
        </CardContent>
      </Card>
    </div>
  )
}
