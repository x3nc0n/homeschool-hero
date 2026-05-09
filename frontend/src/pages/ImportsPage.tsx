import { useCallback, useEffect, useMemo, useState } from 'react'
import { Download, FileUp, Play, ShieldCheck } from 'lucide-react'
import { API_BASE_URL, api } from '@/lib/api'
import type { ImportEntityType, ImportJob, ImportJobStatus } from '@/types/api'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { EmptyState } from '@/components/common/EmptyState'
import { ErrorState } from '@/components/common/ErrorState'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { LoadingState } from '@/components/common/LoadingState'
import { Progress } from '@/components/ui/progress'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'

const entityOptions: Array<{ value: ImportEntityType; label: string; format: 'CSV' | 'JSON'; help: string }> = [
  { value: 'students', label: 'Students', format: 'CSV', help: 'Create student records from one row per learner.' },
  { value: 'subjects', label: 'Subjects', format: 'CSV', help: 'Import subjects with optional color values.' },
  { value: 'assignments', label: 'Assignments', format: 'CSV', help: 'Map assignments to existing subjects and students.' },
  { value: 'grades', label: 'Grades', format: 'CSV', help: 'Import gradebook rows by student and assignment title.' },
  { value: 'attendance', label: 'Attendance', format: 'CSV', help: 'Load attendance by student and date.' },
  { value: 'curriculum_packages', label: 'Curriculum packages', format: 'JSON', help: 'Import package, unit, lesson, and resource trees from JSON.' },
]

const templateEntities = entityOptions.filter((option) => option.format === 'CSV')

function statusVariant(status: ImportJobStatus) {
  if (status === 'failed') return 'destructive'
  if (status === 'complete') return 'secondary'
  return 'outline'
}

function statusLabel(status: ImportJobStatus) {
  if (status === 'pending') return 'Ready'
  if (status === 'validating') return 'Validating'
  if (status === 'importing') return 'Importing'
  if (status === 'complete') return 'Complete'
  return 'Failed'
}

function fileNameFromPath(path: string) {
  const parts = path.split(/[/\\]/)
  return parts[parts.length - 1] || path
}

export function ImportsPage() {
  const [jobs, setJobs] = useState<ImportJob[]>([])
  const [currentJobId, setCurrentJobId] = useState<number | null>(null)
  const [entityType, setEntityType] = useState<ImportEntityType>('students')
  const [file, setFile] = useState<File | null>(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [statusMessage, setStatusMessage] = useState('')

  const currentJob = useMemo(() => jobs.find((job) => job.id === currentJobId) ?? jobs[0] ?? null, [currentJobId, jobs])
  const selectedEntity = entityOptions.find((option) => option.value === entityType) ?? entityOptions[0]
  const progressValue = useMemo(() => {
    if (!currentJob) return 0
    if (currentJob.status === 'complete') return 100
    if (!currentJob.total_rows) return 0
    return Math.min(100, Math.round((currentJob.processed_rows / currentJob.total_rows) * 100))
  }, [currentJob])

  const load = useCallback(async (preferredJobId?: number | null) => {
    setLoading(true)
    setError('')
    try {
      const data = await api.listImportJobs()
      setJobs(data)
      const resolvedJobId =
        preferredJobId && data.some((job) => job.id === preferredJobId)
          ? preferredJobId
          : data[0]?.id ?? null
      setCurrentJobId(resolvedJobId)
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : 'Unable to load import history')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void load()
  }, [load])

  useEffect(() => {
    if (!currentJob || !['validating', 'importing'].includes(currentJob.status)) {
      return
    }
    const interval = window.setInterval(async () => {
      try {
        const updated = await api.getImportJobStatus(currentJob.id)
        setJobs((existing) => {
          const others = existing.filter((job) => job.id !== updated.id)
          return [updated, ...others]
        })
        if (!['validating', 'importing'].includes(updated.status)) {
          setStatusMessage(updated.status === 'complete' ? 'Import finished successfully.' : 'Import finished with errors.')
          void load(updated.id)
        }
      } catch {
        // polling failures can recover on next pass
      }
    }, 1000)
    return () => window.clearInterval(interval)
  }, [currentJob, load])

  const uploadFile = async () => {
    if (!file) {
      setError('Choose a file before uploading.')
      return
    }
    setSaving(true)
    setError('')
    setStatusMessage('')
    try {
      const uploaded = await api.uploadImportFile(entityType, file)
      setFile(null)
      setCurrentJobId(uploaded.id)
      setStatusMessage('File uploaded. Run validation before importing.')
      await load(uploaded.id)
    } catch (uploadError) {
      setError(uploadError instanceof Error ? uploadError.message : 'Unable to upload import file')
    } finally {
      setSaving(false)
    }
  }

  const validateJob = async () => {
    if (!currentJob) return
    setSaving(true)
    setError('')
    setStatusMessage('')
    try {
      const validated = await api.validateImportJob(currentJob.id)
      setStatusMessage(validated.error_count ? 'Dry run found issues to fix.' : 'Dry run passed. The file is ready to import.')
      await load(validated.id)
    } catch (validationError) {
      setError(validationError instanceof Error ? validationError.message : 'Unable to validate import')
    } finally {
      setSaving(false)
    }
  }

  const executeJob = async () => {
    if (!currentJob) return
    setSaving(true)
    setError('')
    setStatusMessage('')
    try {
      const started = await api.executeImportJob(currentJob.id)
      setStatusMessage('Import started. Progress will refresh automatically.')
      setCurrentJobId(started.id)
      await load(started.id)
    } catch (executeError) {
      setError(executeError instanceof Error ? executeError.message : 'Unable to execute import')
    } finally {
      setSaving(false)
    }
  }

  if (loading) return <LoadingState message="Loading imports…" />
  if (error && !jobs.length) return <ErrorState message={error} onRetry={() => void load(currentJobId)} />

  return (
    <div className="space-y-4">
      <div className="grid gap-4 xl:grid-cols-[1fr_1.15fr]">
        <Card>
          <CardHeader>
            <CardTitle>Import data</CardTitle>
            <CardDescription>Upload a CSV or JSON file, run a dry validation pass, then import in bulk.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <Label>Entity type</Label>
              <Select value={entityType} onValueChange={(value) => setEntityType(value as ImportEntityType)}>
                <SelectTrigger>
                  <SelectValue placeholder="Choose import type" />
                </SelectTrigger>
                <SelectContent>
                  {entityOptions.map((option) => (
                    <SelectItem key={option.value} value={option.value}>
                      {option.label} ({option.format})
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <p className="text-xs text-muted-foreground">{selectedEntity.help}</p>
            </div>

            <div className="space-y-2">
              <Label>File</Label>
              <Input
                type="file"
                accept={selectedEntity.format === 'CSV' ? '.csv,text/csv' : '.json,application/json'}
                onChange={(event) => setFile(event.target.files?.[0] ?? null)}
              />
              <p className="text-xs text-muted-foreground">
                Expected format: {selectedEntity.format}. Dry run validation checks required fields, types, and family-scoped references.
              </p>
            </div>

            <div className="flex flex-wrap gap-2">
              <Button onClick={() => void uploadFile()} disabled={saving || !file}>
                <FileUp className="mr-2 h-4 w-4" />
                Upload file
              </Button>
              <Button variant="outline" onClick={() => void validateJob()} disabled={saving || !currentJob}>
                <ShieldCheck className="mr-2 h-4 w-4" />
                Validate dry run
              </Button>
              <Button
                variant="secondary"
                onClick={() => void executeJob()}
                disabled={saving || !currentJob || currentJob.status === 'importing' || currentJob.status === 'complete'}
              >
                <Play className="mr-2 h-4 w-4" />
                Execute import
              </Button>
            </div>

            {statusMessage ? <p className="text-sm text-muted-foreground">{statusMessage}</p> : null}
            {error ? <p className="text-sm text-destructive">{error}</p> : null}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Templates</CardTitle>
            <CardDescription>Download a starter CSV for each tabular import type.</CardDescription>
          </CardHeader>
          <CardContent className="grid gap-3 md:grid-cols-2">
            {templateEntities.map((option) => (
              <a
                key={option.value}
                href={`${API_BASE_URL}/imports/templates/${option.value}`}
                className="rounded-lg border p-3 text-sm transition hover:bg-muted/60"
              >
                <div className="mb-2 flex items-center justify-between gap-2">
                  <span className="font-medium">{option.label}</span>
                  <Download className="h-4 w-4 text-muted-foreground" />
                </div>
                <p className="text-xs text-muted-foreground">{option.help}</p>
              </a>
            ))}
            <div className="rounded-lg border border-dashed p-3 text-sm">
              <p className="font-medium">Curriculum packages (JSON)</p>
              <p className="mt-2 text-xs text-muted-foreground">
                Upload a JSON object or array with package, unit, lesson, and resource structures. Validation checks school year and subject references before import.
              </p>
            </div>
          </CardContent>
        </Card>
      </div>

      {currentJob ? (
        <Card>
          <CardHeader>
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <CardTitle>Current job</CardTitle>
                <CardDescription>{fileNameFromPath(currentJob.file_path)}</CardDescription>
              </div>
              <Badge variant={statusVariant(currentJob.status)}>{statusLabel(currentJob.status)}</Badge>
            </div>
          </CardHeader>
          <CardContent className="space-y-4">
            <Progress value={progressValue} className="h-2" />
            <div className="grid gap-3 md:grid-cols-4">
              <div className="rounded-lg border p-3">
                <p className="text-xs text-muted-foreground">Entity</p>
                <p className="font-medium">{entityOptions.find((option) => option.value === currentJob.entity_type)?.label ?? currentJob.entity_type}</p>
              </div>
              <div className="rounded-lg border p-3">
                <p className="text-xs text-muted-foreground">Rows</p>
                <p className="font-medium">{currentJob.total_rows || 0}</p>
              </div>
              <div className="rounded-lg border p-3">
                <p className="text-xs text-muted-foreground">Processed</p>
                <p className="font-medium">{currentJob.processed_rows}</p>
              </div>
              <div className="rounded-lg border p-3">
                <p className="text-xs text-muted-foreground">Errors</p>
                <p className="font-medium">{currentJob.error_count}</p>
              </div>
            </div>

            {currentJob.errors.length ? (
              <div className="space-y-3">
                <div>
                  <h3 className="font-semibold">Error report</h3>
                  <p className="text-sm text-muted-foreground">Fix the rows below, re-upload the file, and validate again.</p>
                </div>
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Row</TableHead>
                      <TableHead>Field</TableHead>
                      <TableHead>Message</TableHead>
                      <TableHead>Suggestion</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {currentJob.errors.map((item, index) => (
                      <TableRow key={`${item.row ?? 'header'}-${item.field ?? 'general'}-${index}`}>
                        <TableCell>{item.row ?? '—'}</TableCell>
                        <TableCell>{item.field || 'general'}</TableCell>
                        <TableCell>{item.message}</TableCell>
                        <TableCell>{item.suggestion || '—'}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            ) : (
              <p className="text-sm text-muted-foreground">No validation issues are currently recorded for this job.</p>
            )}
          </CardContent>
        </Card>
      ) : (
        <EmptyState title="No imports yet" description="Upload a file to create your first import job." />
      )}

      <Card>
        <CardHeader>
          <CardTitle>Import history</CardTitle>
          <CardDescription>Recent validation and import jobs for this family workspace.</CardDescription>
        </CardHeader>
        <CardContent>
          {jobs.length ? (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>File</TableHead>
                  <TableHead>Type</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Rows</TableHead>
                  <TableHead>Updated</TableHead>
                  <TableHead></TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {jobs.map((job) => (
                  <TableRow key={job.id}>
                    <TableCell>{fileNameFromPath(job.file_path)}</TableCell>
                    <TableCell>{entityOptions.find((option) => option.value === job.entity_type)?.label ?? job.entity_type}</TableCell>
                    <TableCell>
                      <Badge variant={statusVariant(job.status)}>{statusLabel(job.status)}</Badge>
                    </TableCell>
                    <TableCell>
                      {job.processed_rows}/{job.total_rows || 0}
                    </TableCell>
                    <TableCell>{new Date(job.completed_at || job.created_at).toLocaleString()}</TableCell>
                    <TableCell className="text-right">
                      <Button variant="outline" size="sm" onClick={() => setCurrentJobId(job.id)}>
                        Review
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          ) : (
            <EmptyState title="No history available" description="Validated and completed imports will appear here." />
          )}
        </CardContent>
      </Card>
    </div>
  )
}
