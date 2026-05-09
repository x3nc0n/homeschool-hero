import { useCallback, useEffect, useMemo, useState } from 'react'
import { FileUpload } from '@/components/features/FileUpload'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { useCapabilities } from '@/context/CapabilitiesContext'
import { api } from '@/lib/api'
import type { Assignment, Student, Submission, SubmissionDetail, SubmissionVersion } from '@/types/api'
import { LoadingState } from '@/components/common/LoadingState'
import { ErrorState } from '@/components/common/ErrorState'
import { EmptyState } from '@/components/common/EmptyState'
import { PullToRefresh } from '@/components/common/PullToRefresh'
import { Progress } from '@/components/ui/progress'

function formatBytes(bytes?: number) {
  if (!bytes) return 'Unknown size'
  if (bytes >= 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
  if (bytes >= 1024) return `${Math.round(bytes / 1024)} KB`
  return `${bytes} B`
}

function formatVersionMeta(version: SubmissionVersion) {
  const details = [formatBytes(version.file_size_bytes)]
  if (version.page_count) details.push(`${version.page_count} page${version.page_count === 1 ? '' : 's'}`)
  if (version.image_width && version.image_height) details.push(`${version.image_width}×${version.image_height}`)
  return details.join(' • ')
}

function formatGradingStatus(status?: string | null) {
  if (!status) return 'Pending'
  return status.replace(/_/g, ' ')
}

function gradingProgress(status?: string | null) {
  switch (status) {
    case 'pending':
      return 5
    case 'ocr_processing':
      return 20
    case 'ocr_complete':
      return 40
    case 'ai_grading':
      return 65
    case 'ai_complete':
      return 80
    case 'review_needed':
      return 90
    case 'reviewed':
      return 95
    case 'final':
      return 100
    default:
      return 0
  }
}

export function UploadPage() {
  const [students, setStudents] = useState<Student[]>([])
  const [assignments, setAssignments] = useState<Assignment[]>([])
  const [submissions, setSubmissions] = useState<Submission[]>([])
  const [latestSubmission, setLatestSubmission] = useState<SubmissionDetail | null>(null)
  const [selectedSubmissionId, setSelectedSubmissionId] = useState<number | null>(null)
  const [selectedSubmission, setSelectedSubmission] = useState<SubmissionDetail | null>(null)
  const [resubmitTarget, setResubmitTarget] = useState<SubmissionDetail | null>(null)
  const [loading, setLoading] = useState(true)
  const [detailLoading, setDetailLoading] = useState(false)
  const [error, setError] = useState('')
  const { capabilities } = useCapabilities()

  const studentLabelById = useMemo(
    () => Object.fromEntries(students.map((student) => [student.id, student.name])),
    [students],
  )
  const assignmentLabelById = useMemo(
    () => Object.fromEntries(assignments.map((assignment) => [assignment.id, assignment.title])),
    [assignments],
  )

  const loadCurrentSubmissions = useCallback(async (preferredId?: number) => {
    const submissionData = await api.listSubmissions()
    setSubmissions(submissionData)
    const nextSelectedId = preferredId ?? selectedSubmissionId ?? submissionData[0]?.id ?? null
    setSelectedSubmissionId(nextSelectedId)
  }, [selectedSubmissionId])

  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const [studentData, assignmentData, submissionData] = await Promise.all([
        api.listStudents(),
        api.listAssignments({ page: 1, page_size: 100 }),
        api.listSubmissions(),
      ])
      setStudents(studentData)
      setAssignments(assignmentData.items)
      setSubmissions(submissionData)
      setSelectedSubmissionId((current) => current ?? submissionData[0]?.id ?? null)
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : 'Unable to load upload data')
    } finally {
      setLoading(false)
    }
  }, [])

  const loadSubmissionDetail = useCallback(async (submissionId: number) => {
    setDetailLoading(true)
    try {
      const detail = await api.getSubmission(submissionId)
      setSelectedSubmission(detail)
    } catch (detailError) {
      setError(detailError instanceof Error ? detailError.message : 'Unable to load submission detail')
    } finally {
      setDetailLoading(false)
    }
  }, [])

  useEffect(() => {
    void load()
  }, [load])

  useEffect(() => {
    if (!selectedSubmissionId) {
      setSelectedSubmission(null)
      return
    }
    void loadSubmissionDetail(selectedSubmissionId)
  }, [loadSubmissionDetail, selectedSubmissionId])

  const handleUploaded = useCallback(async (submission: SubmissionDetail) => {
    setLatestSubmission(submission)
    setSelectedSubmission(submission)
    setSelectedSubmissionId(submission.id)
    setResubmitTarget(null)
    await loadCurrentSubmissions(submission.id)
  }, [loadCurrentSubmissions])

  if (loading) return <LoadingState message="Loading upload screen…" />
  if (error) return <ErrorState message={error} onRetry={() => void load()} />

  if (!students.length || !assignments.length) {
    return (
      <EmptyState
        title="Setup needed"
        description="Add at least one student and assignment before uploading work."
      />
    )
  }

  return (
    <PullToRefresh onRefresh={load}>
      <div className="space-y-4">
        {!capabilities.ai_grading.enabled || !capabilities.ocr.enabled ? (
        <div className="rounded-md border border-amber-300 bg-amber-50 px-4 py-3 text-sm text-amber-900">
          {!capabilities.ocr.enabled
            ? 'Uploads will be stored, but OCR text extraction is currently unavailable.'
            : 'AI grading is currently unavailable, so uploads will go directly to manual review.'}
        </div>
      ) : null}

      <FileUpload
        students={students}
        assignments={assignments}
        onUploaded={(submission) => void handleUploaded(submission)}
        aiAvailable={capabilities.ai_grading.enabled}
        ocrAvailable={capabilities.ocr.enabled}
        resubmitTarget={resubmitTarget}
        onResubmitCleared={() => setResubmitTarget(null)}
      />

      <div className="grid gap-4 xl:grid-cols-[0.95fr_1.05fr]">
        <Card>
          <CardHeader>
            <CardTitle>Current submissions</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {submissions.length ? (
              submissions.map((submission) => (
                <button
                  key={submission.id}
                  type="button"
                  className={`w-full rounded-lg border p-3 text-left transition ${
                    selectedSubmissionId === submission.id ? 'border-primary bg-primary/5' : 'hover:border-primary/40'
                  }`}
                  onClick={() => setSelectedSubmissionId(submission.id)}
                >
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <p className="font-medium">{assignmentLabelById[submission.assignment_id] || `Assignment #${submission.assignment_id}`}</p>
                      <p className="text-sm text-muted-foreground">{studentLabelById[submission.student_id] || `Student #${submission.student_id}`}</p>
                    </div>
                    <div className="flex flex-col items-end gap-1">
                      <Badge variant="secondary">v{submission.submission_version || 1}</Badge>
                      <Badge variant="outline">{formatGradingStatus(submission.grading_job?.status)}</Badge>
                    </div>
                  </div>
                  <p className="mt-2 text-xs text-muted-foreground">{submission.file_name || submission.original_filename || 'Uploaded file'}</p>
                </button>
              ))
            ) : (
              <p className="text-sm text-muted-foreground">No submissions uploaded yet.</p>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Submission detail</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            {detailLoading ? (
              <LoadingState message="Loading submission detail…" />
            ) : selectedSubmission ? (
              <>
                <div className="rounded-lg border p-4 text-sm">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div>
                      <p className="font-medium">
                        {assignmentLabelById[selectedSubmission.assignment_id] || `Assignment #${selectedSubmission.assignment_id}`}
                      </p>
                      <p className="text-muted-foreground">
                        {studentLabelById[selectedSubmission.student_id] || `Student #${selectedSubmission.student_id}`}
                      </p>
                    </div>
                    <Badge>Current version v{selectedSubmission.submission_version || 1}</Badge>
                  </div>
                  <div className="mt-3 space-y-1 text-muted-foreground">
                    <p>{selectedSubmission.file_name || selectedSubmission.original_filename}</p>
                    <p>{formatVersionMeta(selectedSubmission)}</p>
                    {selectedSubmission.file_url ? (
                      <a className="text-primary underline-offset-4 hover:underline" href={selectedSubmission.file_url} target="_blank" rel="noreferrer">
                        Open file
                      </a>
                    ) : null}
                  </div>
                  <div className="mt-4 flex flex-wrap gap-2">
                    <Button type="button" onClick={() => setResubmitTarget(selectedSubmission)}>
                      Resubmit new version
                    </Button>
                  </div>
                </div>

                <div className="rounded-lg border p-4 text-sm">
                  <div className="flex items-center justify-between gap-2">
                    <h3 className="font-semibold">Grading progress</h3>
                    <Badge variant={selectedSubmission.grading_job?.status === 'final' ? 'default' : 'secondary'}>
                      {formatGradingStatus(selectedSubmission.grading_job?.status)}
                    </Badge>
                  </div>
                  <div className="mt-3 space-y-2">
                    <Progress value={gradingProgress(selectedSubmission.grading_job?.status)} />
                    <p className="text-xs text-muted-foreground">
                      {selectedSubmission.grading_job?.status_history?.[Math.max((selectedSubmission.grading_job?.status_history?.length || 1) - 1, 0)]?.detail ||
                        'Waiting for the grading worker.'}
                    </p>
                    {selectedSubmission.grading_job?.ai_confidence != null ? (
                      <p className="text-xs text-muted-foreground">
                        Confidence {(selectedSubmission.grading_job.ai_confidence ?? 0).toFixed(2)}
                      </p>
                    ) : null}
                    {selectedSubmission.grading_job?.manual_review_reason ? (
                      <p className="text-xs text-amber-700">{selectedSubmission.grading_job.manual_review_reason}</p>
                    ) : null}
                  </div>
                </div>

                <div className="space-y-3">
                  <div className="flex items-center justify-between gap-2">
                    <h3 className="text-sm font-semibold">Version history</h3>
                    <span className="text-xs text-muted-foreground">{selectedSubmission.version_history.length} version(s)</span>
                  </div>
                  <div className="space-y-3">
                    {selectedSubmission.version_history.map((version) => (
                      <div key={version.id} className="rounded-lg border p-3 text-sm">
                        <div className="flex flex-wrap items-center justify-between gap-2">
                          <div className="flex items-center gap-2">
                            <span className="font-medium">Version {version.submission_version || 1}</span>
                            {version.is_current ? <Badge>Current</Badge> : <Badge variant="secondary">Archived</Badge>}
                          </div>
                          <span className="text-xs text-muted-foreground">
                            {version.uploaded_at ? new Date(version.uploaded_at).toLocaleString() : 'Unknown upload time'}
                          </span>
                        </div>
                        <p className="mt-2 text-muted-foreground">{version.file_name || version.original_filename}</p>
                        <p className="text-xs text-muted-foreground">{formatVersionMeta(version)}</p>
                        {version.file_url ? (
                          <a className="mt-2 inline-flex text-primary underline-offset-4 hover:underline" href={version.file_url} target="_blank" rel="noreferrer">
                            View version
                          </a>
                        ) : null}
                      </div>
                    ))}
                  </div>
                </div>
              </>
            ) : latestSubmission ? (
              <p className="text-sm text-muted-foreground">Latest upload saved as submission #{latestSubmission.id}.</p>
            ) : (
              <p className="text-sm text-muted-foreground">Choose a submission to review its version history.</p>
            )}
          </CardContent>
        </Card>
        </div>
      </div>
    </PullToRefresh>
  )
}
