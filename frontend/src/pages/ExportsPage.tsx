import { useCallback, useEffect, useMemo, useState } from 'react'
import { Archive, Download, Trash2 } from 'lucide-react'
import { api } from '@/lib/api'
import type { ExportEntityType, ExportFormat, ExportJob, ExportJobStatus, ExportType } from '@/types/api'
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

const entityOptions: Array<{ value: ExportEntityType; label: string; help: string }> = [
  { value: 'family', label: 'Family profile', help: 'Family settings, users, and memberships.' },
  { value: 'students', label: 'Students', help: 'Student roster and enrollment metadata.' },
  { value: 'subjects', label: 'Subjects', help: 'Subject setup and grading configuration.' },
  { value: 'assignments', label: 'Assignments', help: 'Assignment details, targets, and attachment references.' },
  { value: 'submissions', label: 'Submissions', help: 'Submission metadata plus uploaded work files in ZIP exports.' },
  { value: 'grades', label: 'Grades', help: 'Scores, percentages, letter grades, and grading notes.' },
  { value: 'attendance', label: 'Attendance', help: 'Daily attendance, hours, and excuse document references.' },
  { value: 'report_cards', label: 'Report cards', help: 'Report card data with PDF copies in ZIP exports.' },
  { value: 'transcripts', label: 'Transcripts', help: 'Transcript data with PDF copies in ZIP exports.' },
  { value: 'portfolio_entries', label: 'Portfolio entries', help: 'Portfolio metadata plus attachment files in ZIP exports.' },
  { value: 'compliance_reports', label: 'Compliance reports', help: 'Compliance reporting data and generated PDFs.' },
  { value: 'audit_events', label: 'Audit log', help: 'Family-scoped audit history.' },
]

const defaultEntities = entityOptions.map((option) => option.value)

function statusVariant(status: ExportJobStatus) {
  if (status === 'failed') return 'destructive'
  if (status === 'complete') return 'secondary'
  return 'outline'
}

function statusLabel(status: ExportJobStatus) {
  if (status === 'pending') return 'Queued'
  if (status === 'processing') return 'Processing'
  if (status === 'complete') return 'Complete'
  return 'Failed'
}

function progressValue(job: ExportJob | null) {
  if (!job) return 0
  if (job.status === 'complete' || job.status === 'failed') return 100
  if (job.status === 'processing') return 70
  return 20
}

function formatBytes(value?: number | null) {
  if (!value) return '—'
  if (value < 1024) return `${value} B`
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`
  return `${(value / (1024 * 1024)).toFixed(1)} MB`
}

function fileNameFromPath(path: string) {
  const parts = path.split(/[/\\]/)
  return parts[parts.length - 1] || path
}

export function ExportsPage() {
  const [jobs, setJobs] = useState<ExportJob[]>([])
  const [currentJobId, setCurrentJobId] = useState<number | null>(null)
  const [exportType, setExportType] = useState<ExportType>('full')
  const [format, setFormat] = useState<ExportFormat>('zip')
  const [selectedEntities, setSelectedEntities] = useState<ExportEntityType[]>(defaultEntities)
  const [dateFrom, setDateFrom] = useState('')
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [statusMessage, setStatusMessage] = useState('')

  const currentJob = useMemo(() => jobs.find((job) => job.id === currentJobId) ?? jobs[0] ?? null, [currentJobId, jobs])

  const load = useCallback(async (preferredJobId?: number | null) => {
    setLoading(true)
    setError('')
    try {
      const data = await api.listExportJobs()
      setJobs(data)
      const resolvedJobId =
        preferredJobId && data.some((job) => job.id === preferredJobId)
          ? preferredJobId
          : data[0]?.id ?? null
      setCurrentJobId(resolvedJobId)
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : 'Unable to load export history')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void load()
  }, [load])

  useEffect(() => {
    if (!currentJob || !['pending', 'processing'].includes(currentJob.status)) {
      return
    }
    const interval = window.setInterval(async () => {
      try {
        const updated = await api.getExportJobStatus(currentJob.id)
        setJobs((existing) => {
          const others = existing.filter((job) => job.id !== updated.id)
          return [updated, ...others]
        })
        if (!['pending', 'processing'].includes(updated.status)) {
          setStatusMessage(updated.status === 'complete' ? 'Export finished successfully.' : 'Export failed. Review history and retry.')
          void load(updated.id)
        }
      } catch {
        // allow the next poll to recover
      }
    }, 1500)
    return () => window.clearInterval(interval)
  }, [currentJob, load])

  const toggleEntity = (entity: ExportEntityType) => {
    setSelectedEntities((current) =>
      current.includes(entity) ? current.filter((item) => item !== entity) : [...current, entity],
    )
  }

  const createExport = async (override?: Partial<{ export_type: ExportType; format: ExportFormat; entity_types: ExportEntityType[]; date_from: string }>) => {
    const entityTypes = override?.entity_types ?? (exportType === 'entity' ? selectedEntities : defaultEntities)
    if ((override?.export_type ?? exportType) === 'entity' && !entityTypes.length) {
      setError('Select at least one entity for an entity-specific export.')
      return
    }
    setSaving(true)
    setError('')
    setStatusMessage('')
    try {
      const created = await api.createExportJob({
        export_type: override?.export_type ?? exportType,
        format: override?.format ?? format,
        entity_types: entityTypes,
        date_from: override?.date_from ?? ((override?.export_type ?? exportType) === 'incremental' && dateFrom ? new Date(dateFrom).toISOString() : undefined),
      })
      setCurrentJobId(created.id)
      setStatusMessage('Export queued. Progress will refresh automatically.')
      await load(created.id)
    } catch (createError) {
      setError(createError instanceof Error ? createError.message : 'Unable to create export')
    } finally {
      setSaving(false)
    }
  }

  const deleteJob = async (job: ExportJob) => {
    setSaving(true)
    setError('')
    setStatusMessage('')
    try {
      await api.deleteExportJob(job.id)
      setStatusMessage('Export deleted.')
      await load(currentJobId === job.id ? null : currentJobId)
    } catch (deleteError) {
      setError(deleteError instanceof Error ? deleteError.message : 'Unable to delete export')
    } finally {
      setSaving(false)
    }
  }

  if (loading) return <LoadingState message="Loading exports…" />
  if (error && !jobs.length) return <ErrorState message={error} onRetry={() => void load(currentJobId)} />

  return (
    <div className="space-y-4">
      <div className="grid gap-4 xl:grid-cols-[1.05fr_0.95fr]">
        <Card>
          <CardHeader>
            <CardTitle>Export family data</CardTitle>
            <CardDescription>Create JSON, CSV, or ZIP portability packages for backups, migration, or record delivery.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid gap-4 md:grid-cols-3">
              <div className="space-y-2">
                <Label>Export type</Label>
                <Select value={exportType} onValueChange={(value) => setExportType(value as ExportType)}>
                  <SelectTrigger>
                    <SelectValue placeholder="Choose export type" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="full">Full family export</SelectItem>
                    <SelectItem value="incremental">Incremental export</SelectItem>
                    <SelectItem value="entity">Entity-specific export</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label>Format</Label>
                <Select value={format} onValueChange={(value) => setFormat(value as ExportFormat)}>
                  <SelectTrigger>
                    <SelectValue placeholder="Choose format" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="json">JSON</SelectItem>
                    <SelectItem value="csv">CSV</SelectItem>
                    <SelectItem value="zip">ZIP bundle</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label>Changed since</Label>
                <Input
                  type="datetime-local"
                  value={dateFrom}
                  disabled={exportType !== 'incremental'}
                  onChange={(event) => setDateFrom(event.target.value)}
                />
              </div>
            </div>

            <div className="space-y-3">
              <div>
                <Label>Included entities</Label>
                <p className="text-xs text-muted-foreground">
                  ZIP exports include CSVs plus PDFs and attachment files. Multi-entity CSV exports download as a ZIP bundle of CSV files.
                </p>
              </div>
              <div className="grid gap-3 md:grid-cols-2">
                {entityOptions.map((option) => {
                  const checked = selectedEntities.includes(option.value)
                  const disabled = exportType !== 'entity'
                  return (
                    <label key={option.value} className="flex items-start gap-3 rounded-lg border p-3">
                      <input
                        type="checkbox"
                        className="mt-1 h-4 w-4"
                        checked={checked}
                        disabled={disabled}
                        onChange={() => toggleEntity(option.value)}
                      />
                      <div>
                        <p className="font-medium">{option.label}</p>
                        <p className="text-xs text-muted-foreground">{option.help}</p>
                      </div>
                    </label>
                  )
                })}
              </div>
            </div>

            <div className="flex flex-wrap gap-2">
              <Button onClick={() => void createExport()} disabled={saving}>
                <Archive className="mr-2 h-4 w-4" />
                Create export
              </Button>
              <Button
                variant="secondary"
                onClick={() => void createExport({ export_type: 'full', format: 'zip', entity_types: defaultEntities })}
                disabled={saving}
              >
                <Download className="mr-2 h-4 w-4" />
                Export Everything
              </Button>
            </div>

            {statusMessage ? <p className="text-sm text-muted-foreground">{statusMessage}</p> : null}
            {error ? <p className="text-sm text-destructive">{error}</p> : null}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Export package notes</CardTitle>
            <CardDescription>Use the right package for backups, portability, and document handoff.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3 text-sm">
            <div className="rounded-lg border p-3">
              <p className="font-medium">JSON</p>
              <p className="mt-1 text-muted-foreground">Best for DM-01 portability imports and full-fidelity family data archives.</p>
            </div>
            <div className="rounded-lg border p-3">
              <p className="font-medium">CSV</p>
              <p className="mt-1 text-muted-foreground">Best for spreadsheet review. Single-entity exports download as one CSV; multi-entity exports ship as a CSV bundle.</p>
            </div>
            <div className="rounded-lg border p-3">
              <p className="font-medium">ZIP bundle</p>
              <p className="mt-1 text-muted-foreground">Best for full backups. Includes CSVs, JSON metadata, report PDFs, transcript PDFs, and attachment files.</p>
            </div>
            <div className="rounded-lg border border-dashed p-3 text-muted-foreground">
              Incremental exports include only rows changed since the selected timestamp to keep backup packages smaller.
            </div>
          </CardContent>
        </Card>
      </div>

      {currentJob ? (
        <Card>
          <CardHeader>
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <CardTitle>Latest export</CardTitle>
                <CardDescription>{fileNameFromPath(currentJob.file_path)}</CardDescription>
              </div>
              <Badge variant={statusVariant(currentJob.status)}>{statusLabel(currentJob.status)}</Badge>
            </div>
          </CardHeader>
          <CardContent className="space-y-4">
            <Progress value={progressValue(currentJob)} className="h-2" />
            <div className="grid gap-3 md:grid-cols-4">
              <div className="rounded-lg border p-3">
                <p className="text-xs text-muted-foreground">Type</p>
                <p className="font-medium capitalize">{currentJob.export_type.replace('_', ' ')}</p>
              </div>
              <div className="rounded-lg border p-3">
                <p className="text-xs text-muted-foreground">Format</p>
                <p className="font-medium uppercase">{currentJob.format}</p>
              </div>
              <div className="rounded-lg border p-3">
                <p className="text-xs text-muted-foreground">Size</p>
                <p className="font-medium">{formatBytes(currentJob.file_size)}</p>
              </div>
              <div className="rounded-lg border p-3">
                <p className="text-xs text-muted-foreground">Expires</p>
                <p className="font-medium">{new Date(currentJob.expires_at).toLocaleString()}</p>
              </div>
            </div>
            <div className="rounded-lg border p-3">
              <p className="text-xs text-muted-foreground">Entities</p>
              <p className="mt-1 text-sm">{currentJob.entity_types.map((item) => entityOptions.find((option) => option.value === item)?.label ?? item).join(', ')}</p>
            </div>
          </CardContent>
        </Card>
      ) : (
        <EmptyState title="No exports yet" description="Create a portability package to back up or move your family data." />
      )}

      <Card>
        <CardHeader>
          <CardTitle>Export history</CardTitle>
          <CardDescription>Recent export packages for this family workspace.</CardDescription>
        </CardHeader>
        <CardContent>
          {jobs.length ? (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>File</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Type</TableHead>
                  <TableHead>Format</TableHead>
                  <TableHead>Created</TableHead>
                  <TableHead>Size</TableHead>
                  <TableHead></TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {jobs.map((job) => (
                  <TableRow key={job.id}>
                    <TableCell>{fileNameFromPath(job.file_path)}</TableCell>
                    <TableCell>
                      <Badge variant={statusVariant(job.status)}>{statusLabel(job.status)}</Badge>
                    </TableCell>
                    <TableCell className="capitalize">{job.export_type.replace('_', ' ')}</TableCell>
                    <TableCell className="uppercase">{job.format}</TableCell>
                    <TableCell>{new Date(job.created_at).toLocaleString()}</TableCell>
                    <TableCell>{formatBytes(job.file_size)}</TableCell>
                    <TableCell className="text-right">
                      <div className="flex justify-end gap-2">
                        <Button variant="outline" size="sm" onClick={() => setCurrentJobId(job.id)}>
                          View
                        </Button>
                        <Button
                          variant="outline"
                          size="sm"
                          disabled={job.status !== 'complete'}
                          onClick={() => window.open(api.getExportDownloadUrl(job.id), '_blank', 'noopener,noreferrer')}
                        >
                          <Download className="mr-2 h-4 w-4" />
                          Download
                        </Button>
                        <Button variant="outline" size="sm" disabled={saving} onClick={() => void deleteJob(job)}>
                          <Trash2 className="mr-2 h-4 w-4" />
                          Delete
                        </Button>
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          ) : (
            <EmptyState title="No exports yet" description="Generated backups and portability packages will appear here." />
          )}
        </CardContent>
      </Card>
    </div>
  )
}
