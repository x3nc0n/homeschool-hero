import { useCallback, useEffect, useMemo, useState } from 'react'
import { RefreshCw } from 'lucide-react'
import { api } from '@/lib/api'
import type { ServiceHealthLevel, SystemStatusResponse } from '@/types/health'
import { ErrorState } from '@/components/common/ErrorState'
import { LoadingState } from '@/components/common/LoadingState'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Progress } from '@/components/ui/progress'

function badgeVariant(status: ServiceHealthLevel | 'healthy' | 'degraded' | 'unhealthy') {
  if (status === 'healthy') return 'secondary'
  if (status === 'degraded' || status === 'not_configured') return 'outline'
  return 'destructive'
}

function dotClass(status: ServiceHealthLevel | 'healthy' | 'degraded' | 'unhealthy') {
  if (status === 'healthy') return 'bg-emerald-500'
  if (status === 'degraded' || status === 'not_configured') return 'bg-amber-500'
  return 'bg-red-500'
}

function formatBytes(value?: number | null) {
  if (!value && value !== 0) return '—'
  if (value < 1024) return `${value} B`
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`
  if (value < 1024 * 1024 * 1024) return `${(value / (1024 * 1024)).toFixed(1)} MB`
  return `${(value / (1024 * 1024 * 1024)).toFixed(2)} GB`
}

function formatTimestamp(value?: string | null) {
  return value ? new Date(value).toLocaleString() : '—'
}

export function StatusPage() {
  const [status, setStatus] = useState<SystemStatusResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [error, setError] = useState('')

  const load = useCallback(async (background = false) => {
    if (background) {
      setRefreshing(true)
    } else {
      setLoading(true)
    }
    setError('')
    try {
      setStatus(await api.getSystemStatus())
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : 'Unable to load status center')
    } finally {
      setLoading(false)
      setRefreshing(false)
    }
  }, [])

  useEffect(() => {
    void load()
  }, [load])

  useEffect(() => {
    const interval = window.setInterval(() => void load(true), 30_000)
    return () => window.clearInterval(interval)
  }, [load])

  const services = useMemo(() => Object.values(status?.services || {}), [status])

  if (loading) return <LoadingState message="Loading status center…" />
  if (error && !status) return <ErrorState message={error} onRetry={() => void load()} />

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-2xl font-semibold">Status center</h2>
          <p className="text-sm text-muted-foreground">Live system state with 30-second auto refresh.</p>
        </div>
        <Button variant="outline" onClick={() => void load(true)} disabled={refreshing}>
          <RefreshCw className="mr-2 h-4 w-4" />
          {refreshing ? 'Refreshing…' : 'Refresh'}
        </Button>
      </div>

      <div className="grid gap-4 md:grid-cols-4">
        <Card>
          <CardHeader>
            <CardDescription>Overall health</CardDescription>
            <CardTitle className="flex items-center gap-2 capitalize">
              <span className={`h-3 w-3 rounded-full ${dotClass(status?.status || 'unhealthy')}`} />
              {status?.status}
            </CardTitle>
          </CardHeader>
        </Card>
        <Card>
          <CardHeader>
            <CardDescription>Readiness</CardDescription>
            <CardTitle>{status?.ready ? 'Ready' : 'Not ready'}</CardTitle>
          </CardHeader>
        </Card>
        <Card>
          <CardHeader>
            <CardDescription>Uptime</CardDescription>
            <CardTitle>{status?.uptime_human || '—'}</CardTitle>
          </CardHeader>
        </Card>
        <Card>
          <CardHeader>
            <CardDescription>Version</CardDescription>
            <CardTitle>{status?.version || '—'}</CardTitle>
          </CardHeader>
        </Card>
      </div>

      <div className="grid gap-4 xl:grid-cols-[1.2fr_0.95fr]">
        <Card>
          <CardHeader>
            <CardTitle>Service traffic lights</CardTitle>
            <CardDescription>Database, cache, AI, email, backup destination, and storage.</CardDescription>
          </CardHeader>
          <CardContent className="grid gap-3 md:grid-cols-2">
            {services.map((service) => (
              <div key={service.name} className="rounded-lg border p-3">
                <div className="flex items-center justify-between gap-3">
                  <div className="flex items-center gap-2">
                    <span className={`h-3 w-3 rounded-full ${dotClass(service.status)}`} />
                    <div>
                      <p className="font-medium">{service.label}</p>
                      <p className="text-xs text-muted-foreground">{service.required ? 'Required' : 'Optional'}</p>
                    </div>
                  </div>
                  <Badge variant={badgeVariant(service.status)} className="capitalize">
                    {service.status.replace('_', ' ')}
                  </Badge>
                </div>
                <p className="mt-3 text-sm text-muted-foreground">{service.message}</p>
                <div className="mt-2 flex flex-wrap gap-3 text-xs text-muted-foreground">
                  <span>Configured: {service.configured ? 'Yes' : 'No'}</span>
                  <span>Checked: {new Date(service.checked_at).toLocaleTimeString()}</span>
                  <span>Response: {service.response_time_ms ? `${service.response_time_ms.toFixed(0)} ms` : '—'}</span>
                </div>
              </div>
            ))}
          </CardContent>
        </Card>

        <div className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Backup status</CardTitle>
              <CardDescription>Last backup time, current state, and next scheduled run.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="flex items-center justify-between gap-3">
                <span className="text-sm text-muted-foreground">Destination</span>
                <Badge variant={status?.backup?.validation.writable ? 'secondary' : 'outline'}>
                  {(status?.backup?.destination || 'local').toUpperCase()}
                </Badge>
              </div>
              <div className="rounded-lg border p-3">
                <p className="text-xs uppercase text-muted-foreground">Last backup</p>
                <p className="mt-1 font-medium">{formatTimestamp(status?.backup?.last_backup?.started_at)}</p>
                <p className="text-xs text-muted-foreground">{status?.backup?.last_backup?.status || 'No backup recorded yet.'}</p>
              </div>
              <div className="rounded-lg border p-3">
                <p className="text-xs uppercase text-muted-foreground">Last successful backup</p>
                <p className="mt-1 font-medium">
                  {formatTimestamp(status?.backup?.last_success?.completed_at || status?.backup?.last_success?.started_at)}
                </p>
                <p className="text-xs text-muted-foreground">{formatBytes(status?.backup?.last_success?.file_size)}</p>
              </div>
              <div className="rounded-lg border p-3">
                <p className="text-xs uppercase text-muted-foreground">Next scheduled</p>
                <p className="mt-1 font-medium">
                  {status?.backup?.next_scheduled ? new Date(status.backup.next_scheduled).toLocaleString() : 'Scheduler idle'}
                </p>
                <p className="text-xs text-muted-foreground">{status?.backup?.validation.message || 'Backup destination not configured.'}</p>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Disk usage</CardTitle>
              <CardDescription>Uploads directory capacity with warning thresholds.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="flex items-center justify-between gap-3">
                <span className="text-sm text-muted-foreground">Usage</span>
                <Badge variant={badgeVariant(status?.disk.status || 'unhealthy')}>
                  {status ? status.disk.used_percent.toFixed(1) : '0.0'}%
                </Badge>
              </div>
              <Progress value={status?.disk.used_percent || 0} />
              <div className="grid gap-3 sm:grid-cols-2">
                <div className="rounded-lg border p-3">
                  <p className="text-xs uppercase text-muted-foreground">Used / free</p>
                  <p className="mt-1 font-medium">
                    {formatBytes(status?.disk.used_bytes)} / {formatBytes(status?.disk.free_bytes)}
                  </p>
                </div>
                <div className="rounded-lg border p-3">
                  <p className="text-xs uppercase text-muted-foreground">Thresholds</p>
                  <p className="mt-1 font-medium">
                    {status?.disk.warning_threshold_percent}% warning · {status?.disk.critical_threshold_percent}% critical
                  </p>
                </div>
              </div>
              <p className="text-xs text-muted-foreground">{status?.disk.path}</p>
            </CardContent>
          </Card>
        </div>
      </div>

      {error ? <p className="text-sm text-destructive">{error}</p> : null}
    </div>
  )
}
