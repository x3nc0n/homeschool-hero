import { useCallback, useEffect, useMemo, useState } from 'react'
import { HardDriveDownload, RefreshCw } from 'lucide-react'
import { api } from '@/lib/api'
import type { BackupConfig, BackupJob, BackupJobStatus, BackupStatus } from '@/types/api'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { ErrorState } from '@/components/common/ErrorState'
import { LoadingState } from '@/components/common/LoadingState'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'

function statusVariant(status: BackupJobStatus) {
  if (status === 'failed') return 'destructive'
  if (status === 'complete') return 'secondary'
  if (status === 'running') return 'default'
  return 'outline'
}

function formatBytes(value?: number | null) {
  if (!value) return '—'
  if (value < 1024) return `${value} B`
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`
  if (value < 1024 * 1024 * 1024) return `${(value / (1024 * 1024)).toFixed(1)} MB`
  return `${(value / (1024 * 1024 * 1024)).toFixed(2)} GB`
}

function artifactLabel(job?: BackupJob | null) {
  if (!job?.file_path) return '—'
  const parts = job.file_path.split(/[/\\#]/).filter(Boolean)
  return parts[parts.length - 1] ?? job.file_path
}

export function BackupsPage() {
  const [config, setConfig] = useState<BackupConfig | null>(null)
  const [status, setStatus] = useState<BackupStatus | null>(null)
  const [jobs, setJobs] = useState<BackupJob[]>([])
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')

  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const [configResponse, statusResponse, historyResponse] = await Promise.all([
        api.getBackupConfig(),
        api.getBackupStatus(),
        api.listBackups(),
      ])
      setConfig(configResponse)
      setStatus(statusResponse)
      setJobs(historyResponse)
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : 'Unable to load backups')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void load()
  }, [load])

  const activeJob = useMemo(() => jobs.find((job) => job.status === 'pending' || job.status === 'running') ?? null, [jobs])

  useEffect(() => {
    if (!activeJob) return
    const interval = window.setInterval(async () => {
      try {
        const refreshed = await api.getBackup(activeJob.id)
        setJobs((current) => [refreshed, ...current.filter((job) => job.id !== refreshed.id)])
        setStatus((current) =>
          current
            ? {
                ...current,
                last_backup: refreshed,
                last_success: refreshed.status === 'complete' ? refreshed : current.last_success,
              }
            : current,
        )
        if (refreshed.status === 'complete' || refreshed.status === 'failed') {
          await load()
        }
      } catch {
        // allow next poll to recover
      }
    }, 1500)
    return () => window.clearInterval(interval)
  }, [activeJob, load])

  const triggerManualBackup = async () => {
    setSaving(true)
    setError('')
    setMessage('')
    try {
      const job = await api.triggerBackup()
      setJobs((current) => [job, ...current.filter((item) => item.id !== job.id)])
      setStatus((current) => (current ? { ...current, last_backup: job } : current))
      setMessage('Backup queued. Status will refresh automatically.')
    } catch (triggerError) {
      setError(triggerError instanceof Error ? triggerError.message : 'Unable to trigger backup')
    } finally {
      setSaving(false)
    }
  }

  if (loading) return <LoadingState message="Loading backup settings…" />
  if (error && !config && !status) return <ErrorState message={error} onRetry={() => void load()} />

  return (
    <div className="space-y-4">
      <div className="grid gap-4 xl:grid-cols-[1.05fr_0.95fr]">
        <Card>
          <CardHeader>
            <CardTitle>Backup settings</CardTitle>
            <CardDescription>NAS-aware backup destination, encryption readiness, and schedule status.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid gap-3 md:grid-cols-2">
              <div className="rounded-lg border p-3">
                <p className="text-xs uppercase text-muted-foreground">Destination</p>
                <p className="font-medium uppercase">{config?.destination ?? 'local'}</p>
                <p className="text-xs text-muted-foreground">{config?.target_uri || config?.target_path || 'Not configured'}</p>
              </div>
              <div className="rounded-lg border p-3">
                <p className="text-xs uppercase text-muted-foreground">Schedule</p>
                <p className="font-medium">{config?.schedule || '—'}</p>
                <p className="text-xs text-muted-foreground">
                  Next run: {status?.next_scheduled ? new Date(status.next_scheduled).toLocaleString() : 'Scheduler idle'}
                </p>
              </div>
              <div className="rounded-lg border p-3">
                <p className="text-xs uppercase text-muted-foreground">Restic</p>
                <p className="font-medium">
                  {config?.restic_enabled ? 'Enabled' : config?.restic_installed ? 'Installed, waiting for encryption key' : 'Not installed'}
                </p>
                <p className="text-xs text-muted-foreground">
                  {config?.restic_repository || (config?.restic_installed ? 'Repository will initialize on first backup.' : 'Plain file copy fallback is active.')}
                </p>
              </div>
              <div className="rounded-lg border p-3">
                <p className="text-xs uppercase text-muted-foreground">Mount validation</p>
                <p className="font-medium">{config?.validation.message || 'Unknown'}</p>
                <p className="text-xs text-muted-foreground">
                  Reachable: {config?.validation.reachable ? 'Yes' : 'No'} · Writable: {config?.validation.writable ? 'Yes' : 'No'}
                </p>
              </div>
            </div>

            {config?.destination === 'smb' ? (
              <div className="rounded-lg border p-3 text-sm">
                <p className="font-medium">SMB mount</p>
                <p className="text-muted-foreground">
                  {config.smb?.host}\\{config.smb?.share} · User {config.smb?.user || 'not set'} · Password {config.smb?.password_configured ? 'configured' : 'missing'}
                </p>
              </div>
            ) : null}

            {config?.destination === 'nfs' ? (
              <div className="rounded-lg border p-3 text-sm">
                <p className="font-medium">NFS export</p>
                <p className="text-muted-foreground">
                  {config.nfs?.host}:{config.nfs?.path}
                </p>
              </div>
            ) : null}

            <div className="flex flex-wrap gap-2">
              <Button onClick={() => void triggerManualBackup()} disabled={saving || !config?.validation.writable}>
                <HardDriveDownload className="mr-2 h-4 w-4" />
                Run manual backup
              </Button>
              <Button variant="outline" onClick={() => void load()} disabled={saving}>
                <RefreshCw className="mr-2 h-4 w-4" />
                Refresh status
              </Button>
            </div>
            {message ? <p className="text-sm text-muted-foreground">{message}</p> : null}
            {error ? <p className="text-sm text-destructive">{error}</p> : null}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Latest backup status</CardTitle>
            <CardDescription>Scheduled state, last success, and current failure signal.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="flex items-center justify-between gap-3">
              <div>
                <p className="text-sm text-muted-foreground">Scheduler</p>
                <p className="font-medium">{status?.scheduler_enabled ? 'Enabled' : 'Disabled'}</p>
              </div>
              <Badge variant={status?.validation.writable ? 'secondary' : 'destructive'}>
                {status?.validation.writable ? 'Ready' : 'Attention needed'}
              </Badge>
            </div>
            <div className="rounded-lg border p-3">
              <p className="text-xs uppercase text-muted-foreground">Last backup</p>
              {status?.last_backup ? (
                <>
                  <div className="mt-1 flex items-center justify-between gap-3">
                    <p className="font-medium">{new Date(status.last_backup.started_at).toLocaleString()}</p>
                    <Badge variant={statusVariant(status.last_backup.status)}>{status.last_backup.status}</Badge>
                  </div>
                  <p className="text-xs text-muted-foreground">
                    {artifactLabel(status.last_backup)} · {formatBytes(status.last_backup.file_size)}
                  </p>
                  {status.last_backup.error_message ? (
                    <p className="mt-2 text-xs text-destructive">{status.last_backup.error_message}</p>
                  ) : null}
                </>
              ) : (
                <p className="text-sm text-muted-foreground">No backups recorded yet.</p>
              )}
            </div>
            <div className="rounded-lg border p-3">
              <p className="text-xs uppercase text-muted-foreground">Last successful backup</p>
              {status?.last_success ? (
                <>
                  <p className="mt-1 font-medium">{new Date(status.last_success.completed_at || status.last_success.started_at).toLocaleString()}</p>
                  <p className="text-xs text-muted-foreground">{formatBytes(status.last_success.file_size)}</p>
                </>
              ) : (
                <p className="text-sm text-muted-foreground">No successful backups recorded yet.</p>
              )}
            </div>
            <div className="rounded-lg border border-dashed p-3 text-sm text-muted-foreground">
              Configure NAS mount paths and backup secrets with environment variables, then use this page for trigger/history visibility.
            </div>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Backup history</CardTitle>
          <CardDescription>Database, uploads, and DM-02 export bundles captured for this family.</CardDescription>
        </CardHeader>
        <CardContent>
          {jobs.length ? (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Started</TableHead>
                  <TableHead>Type</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Destination</TableHead>
                  <TableHead>Artifact</TableHead>
                  <TableHead>Size</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {jobs.map((job) => (
                  <TableRow key={job.id}>
                    <TableCell>{new Date(job.started_at).toLocaleString()}</TableCell>
                    <TableCell className="capitalize">{job.backup_type.replace('_', ' ')}</TableCell>
                    <TableCell>
                      <Badge variant={statusVariant(job.status)}>{job.status}</Badge>
                    </TableCell>
                    <TableCell className="uppercase">{job.destination}</TableCell>
                    <TableCell>
                      <div className="space-y-1">
                        <p className="font-medium">{artifactLabel(job)}</p>
                        {job.error_message ? <p className="text-xs text-destructive">{job.error_message}</p> : null}
                      </div>
                    </TableCell>
                    <TableCell>{formatBytes(job.file_size)}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          ) : (
            <p className="text-sm text-muted-foreground">No backup history yet.</p>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
