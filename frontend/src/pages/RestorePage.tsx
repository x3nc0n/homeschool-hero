import { useCallback, useEffect, useMemo, useState } from 'react'
import { AlertTriangle, RefreshCw, ShieldAlert } from 'lucide-react'
import { api } from '@/lib/api'
import type { ExportEntityType, RestoreBackup, RestoreExecution, RestoreValidation } from '@/types/api'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { ErrorState } from '@/components/common/ErrorState'
import { LoadingState } from '@/components/common/LoadingState'
import { Progress } from '@/components/ui/progress'

const ENTITY_OPTIONS: ExportEntityType[] = ['students', 'subjects', 'assignments', 'submissions', 'grades', 'attendance']

function formatBytes(value: number) {
  if (!value) return '—'
  if (value < 1024) return `${value} B`
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`
  if (value < 1024 * 1024 * 1024) return `${(value / (1024 * 1024)).toFixed(1)} MB`
  return `${(value / (1024 * 1024 * 1024)).toFixed(2)} GB`
}

type PendingAction =
  | { mode: 'full'; backup: RestoreBackup; token: string }
  | { mode: 'selective'; backup: RestoreBackup; token: string; entities: ExportEntityType[] }

export function RestorePage() {
  const [backups, setBackups] = useState<RestoreBackup[]>([])
  const [validations, setValidations] = useState<Record<string, RestoreValidation>>({})
  const [selectedEntities, setSelectedEntities] = useState<Record<string, ExportEntityType[]>>({})
  const [pendingAction, setPendingAction] = useState<PendingAction | null>(null)
  const [lastResult, setLastResult] = useState<RestoreExecution | null>(null)
  const [loading, setLoading] = useState(true)
  const [working, setWorking] = useState(false)
  const [error, setError] = useState('')

  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      setBackups(await api.listRestoreBackups())
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : 'Unable to load restore backups')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void load()
  }, [load])

  const runValidation = async (backupId: string) => {
    setWorking(true)
    setError('')
    try {
      const validation = await api.validateRestoreBackup(backupId)
      setValidations((current) => ({ ...current, [backupId]: validation }))
    } catch (validationError) {
      setError(validationError instanceof Error ? validationError.message : 'Unable to validate backup')
    } finally {
      setWorking(false)
    }
  }

  const toggleEntity = (backupId: string, entity: ExportEntityType) => {
    setSelectedEntities((current) => {
      const selected = new Set(current[backupId] || [])
      if (selected.has(entity)) selected.delete(entity)
      else selected.add(entity)
      return { ...current, [backupId]: [...selected] }
    })
  }

  const activeValidation = useMemo(
    () => (pendingAction ? validations[pendingAction.backup.backup_id] ?? null : null),
    [pendingAction, validations],
  )

  const confirmRestore = async () => {
    if (!pendingAction) return
    setWorking(true)
    setError('')
    try {
      const result =
        pendingAction.mode === 'full'
          ? await api.executeRestore(pendingAction.backup.backup_id, {
              confirmation_token: pendingAction.token,
              include_database: true,
              include_files: true,
              auto_backup: true,
            })
          : await api.executeSelectiveRestore(pendingAction.backup.backup_id, {
              confirmation_token: pendingAction.token,
              entity_types: pendingAction.entities,
              overwrite_existing: false,
              auto_backup: true,
            })
      setLastResult(result)
      setPendingAction(null)
      await load()
    } catch (restoreError) {
      setError(restoreError instanceof Error ? restoreError.message : 'Restore failed')
    } finally {
      setWorking(false)
    }
  }

  if (loading) return <LoadingState message="Loading restore backups…" />
  if (error && !backups.length) return <ErrorState message={error} onRetry={() => void load()} />

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <CardTitle>Restore workspace</CardTitle>
          <CardDescription>Validate first, then confirm a full or selective restore. Every restore takes a safety snapshot before execution.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="flex flex-wrap gap-2">
            <Button variant="outline" onClick={() => void load()} disabled={working}>
              <RefreshCw className="mr-2 h-4 w-4" />
              Refresh backups
            </Button>
          </div>
          {working ? (
            <div className="space-y-2">
              <Progress value={80} />
              <p className="text-sm text-muted-foreground">Restore task in progress…</p>
            </div>
          ) : null}
          {error ? <p className="text-sm text-destructive">{error}</p> : null}
          {lastResult ? (
            <div className="rounded-lg border border-emerald-500/30 bg-emerald-500/5 p-3 text-sm">
              <p className="font-medium">{lastResult.message}</p>
              <p className="text-muted-foreground">
                Mode: {lastResult.mode} · Safety snapshot #{lastResult.safety_snapshot_job_id ?? 'not created'}
              </p>
            </div>
          ) : null}
        </CardContent>
      </Card>

      {backups.length ? (
        backups.map((backup) => {
          const validation = validations[backup.backup_id]
          const selected = selectedEntities[backup.backup_id] || backup.available_entities.filter((entity) => ENTITY_OPTIONS.includes(entity))
          return (
            <Card key={backup.backup_id}>
              <CardHeader>
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <CardTitle>{backup.label}</CardTitle>
                    <CardDescription>
                      {backup.completed_at ? new Date(backup.completed_at).toLocaleString() : 'Pending completion'} · {formatBytes(backup.size_bytes)} ·{' '}
                      {backup.storage_mode.replace('_', ' ')}
                    </CardDescription>
                  </div>
                  <Badge variant={backup.manifest_present ? 'secondary' : 'destructive'}>
                    {backup.manifest_present ? 'Manifest ready' : 'Manifest missing'}
                  </Badge>
                </div>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="grid gap-3 md:grid-cols-3">
                  <div className="rounded-lg border p-3">
                    <p className="text-xs uppercase text-muted-foreground">Backup ID</p>
                    <p className="font-medium">{backup.backup_id}</p>
                  </div>
                  <div className="rounded-lg border p-3">
                    <p className="text-xs uppercase text-muted-foreground">Destination</p>
                    <p className="font-medium uppercase">{backup.destination}</p>
                  </div>
                  <div className="rounded-lg border p-3">
                    <p className="text-xs uppercase text-muted-foreground">Entities</p>
                    <p className="font-medium">{backup.available_entities.length ? backup.available_entities.join(', ') : 'Manifest only'}</p>
                  </div>
                </div>

                <div className="flex flex-wrap gap-2">
                  <Button onClick={() => void runValidation(backup.backup_id)} disabled={working}>
                    Validate backup
                  </Button>
                  <Button
                    variant="outline"
                    disabled={working || !validation?.confirmation_token || !validation.can_restore}
                    onClick={() =>
                      validation?.confirmation_token &&
                      setPendingAction({ mode: 'full', backup, token: validation.confirmation_token })
                    }
                  >
                    Full restore
                  </Button>
                  <Button
                    variant="outline"
                    disabled={working || !validation?.confirmation_token || !validation.can_restore || !selected.length}
                    onClick={() =>
                      validation?.confirmation_token &&
                      setPendingAction({ mode: 'selective', backup, token: validation.confirmation_token, entities: selected })
                    }
                  >
                    Selective restore
                  </Button>
                </div>

                <div className="space-y-2">
                  <p className="text-sm font-medium">Selective entities</p>
                  <div className="flex flex-wrap gap-2">
                    {ENTITY_OPTIONS.map((entity) => {
                      const active = selected.includes(entity)
                      const allowed = backup.available_entities.includes(entity)
                      return (
                        <button
                          key={entity}
                          type="button"
                          disabled={!allowed}
                          onClick={() => toggleEntity(backup.backup_id, entity)}
                          className={`rounded-full border px-3 py-1 text-sm ${active ? 'border-primary bg-primary/10 text-primary' : 'text-muted-foreground'} ${
                            !allowed ? 'cursor-not-allowed opacity-40' : ''
                          }`}
                        >
                          {entity.replace('_', ' ')}
                        </button>
                      )
                    })}
                  </div>
                </div>

                {validation ? (
                  <div className="rounded-lg border p-3">
                    <div className="mb-2 flex items-center justify-between gap-3">
                      <p className="font-medium">Validation summary</p>
                      <Badge variant={validation.valid ? 'secondary' : 'destructive'}>
                        {validation.valid ? 'Ready to confirm' : 'Needs attention'}
                      </Badge>
                    </div>
                    <div className="space-y-2 text-sm">
                      {validation.checks.map((check) => (
                        <div key={check.name} className="flex items-start justify-between gap-3 rounded-md border p-2">
                          <div>
                            <p className="font-medium capitalize">{check.name.replace('_', ' ')}</p>
                            <p className="text-muted-foreground">{check.message}</p>
                          </div>
                          <Badge variant={check.valid ? 'secondary' : 'destructive'}>{check.valid ? 'OK' : 'Fail'}</Badge>
                        </div>
                      ))}
                      {validation.warnings.map((warning) => (
                        <div key={warning} className="flex items-start gap-2 rounded-md border border-amber-500/30 bg-amber-500/5 p-2 text-amber-700">
                          <AlertTriangle className="mt-0.5 h-4 w-4" />
                          <span>{warning}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                ) : null}
              </CardContent>
            </Card>
          )
        })
      ) : (
        <Card>
          <CardContent className="p-6 text-sm text-muted-foreground">No restore backups are currently available.</CardContent>
        </Card>
      )}

      {pendingAction ? (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
          <Card className="w-full max-w-xl">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <ShieldAlert className="h-5 w-5 text-amber-600" />
                Confirm {pendingAction.mode === 'full' ? 'full restore' : 'selective restore'}
              </CardTitle>
              <CardDescription>
                This action will create an automatic safety backup first and then restore {pendingAction.backup.label}.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4 text-sm">
              <div className="rounded-lg border border-amber-500/30 bg-amber-500/5 p-3">
                <p className="font-medium">Warnings</p>
                <ul className="mt-2 list-disc space-y-1 pl-5 text-muted-foreground">
                  <li>Restore requires the validation token generated from the most recent validation run.</li>
                  <li>Full restore replaces the live database and uploads after the safety snapshot completes.</li>
                  {pendingAction.mode === 'selective' ? <li>Selective restore will merge entities: {pendingAction.entities.join(', ')}.</li> : null}
                </ul>
              </div>
              {activeValidation?.expires_at ? (
                <p className="text-muted-foreground">Confirmation token expires at {new Date(activeValidation.expires_at).toLocaleString()}.</p>
              ) : null}
              <div className="flex justify-end gap-2">
                <Button variant="outline" onClick={() => setPendingAction(null)} disabled={working}>
                  Cancel
                </Button>
                <Button onClick={() => void confirmRestore()} disabled={working}>
                  Confirm restore
                </Button>
              </div>
            </CardContent>
          </Card>
        </div>
      ) : null}
    </div>
  )
}
