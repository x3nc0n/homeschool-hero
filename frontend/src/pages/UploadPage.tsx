import { useEffect, useState } from 'react'
import { FileUpload } from '@/components/features/FileUpload'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { useCapabilities } from '@/context/CapabilitiesContext'
import { api } from '@/lib/api'
import type { Assignment, Student, Submission } from '@/types/api'
import { LoadingState } from '@/components/common/LoadingState'
import { ErrorState } from '@/components/common/ErrorState'
import { EmptyState } from '@/components/common/EmptyState'

export function UploadPage() {
  const [students, setStudents] = useState<Student[]>([])
  const [assignments, setAssignments] = useState<Assignment[]>([])
  const [latestSubmission, setLatestSubmission] = useState<Submission | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const { capabilities } = useCapabilities()

  const load = async () => {
    setLoading(true)
    setError('')
    try {
      const [studentData, assignmentData] = await Promise.all([api.listStudents(), api.listAssignments()])
      setStudents(studentData)
      setAssignments(assignmentData)
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : 'Unable to load upload data')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void load()
  }, [])

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
        onUploaded={setLatestSubmission}
        aiAvailable={capabilities.ai_grading.enabled}
        ocrAvailable={capabilities.ocr.enabled}
      />

      <Card>
        <CardHeader>
          <CardTitle>Latest upload</CardTitle>
        </CardHeader>
        <CardContent>
          {latestSubmission ? (
            <div className="rounded-md border p-3 text-sm">
              <p>
                Submission #{latestSubmission.id} uploaded for assignment {latestSubmission.assignment_id}, student{' '}
                {latestSubmission.student_id}.
              </p>
            </div>
          ) : (
            <p className="text-sm text-muted-foreground">No uploads this session yet.</p>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
