import { useEffect, useMemo, useRef, useState } from 'react'
import { Camera, FileText, RotateCcw, Upload } from 'lucide-react'
import type { Assignment, Student, Submission, SubmissionDetail } from '@/types/api'
import { api } from '@/lib/api'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Progress } from '@/components/ui/progress'

const MAX_UPLOAD_BYTES = 25 * 1024 * 1024
const ALLOWED_FILE_LABEL = 'PDF, JPEG, PNG, HEIC, TIFF, WEBP'
const ALLOWED_MIME_TYPES = new Set([
  'application/pdf',
  'image/jpeg',
  'image/png',
  'image/heic',
  'image/heif',
  'image/tiff',
  'image/webp',
])
const ALLOWED_EXTENSIONS = ['.pdf', '.jpg', '.jpeg', '.png', '.heic', '.heif', '.tif', '.tiff', '.webp']

type PreviewKind = 'image' | 'pdf'

function formatBytes(bytes: number) {
  if (bytes >= 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
  if (bytes >= 1024) return `${Math.round(bytes / 1024)} KB`
  return `${bytes} B`
}

function isAllowedFile(file: File) {
  const name = file.name.toLowerCase()
  return ALLOWED_MIME_TYPES.has(file.type) || ALLOWED_EXTENSIONS.some((extension) => name.endsWith(extension))
}

function startsWithSignature(bytes: Uint8Array, signature: number[]) {
  return signature.every((value, index) => bytes[index] === value)
}

function isPdfSignature(bytes: Uint8Array) {
  return startsWithSignature(bytes, [0x25, 0x50, 0x44, 0x46, 0x2d])
}

function isJpegSignature(bytes: Uint8Array) {
  return startsWithSignature(bytes, [0xff, 0xd8, 0xff])
}

function isPngSignature(bytes: Uint8Array) {
  return startsWithSignature(bytes, [0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a])
}

function isWebpSignature(bytes: Uint8Array) {
  return startsWithSignature(bytes, [0x52, 0x49, 0x46, 0x46]) && startsWithSignature(bytes.slice(8), [0x57, 0x45, 0x42, 0x50])
}

async function getPreviewKind(file: File): Promise<PreviewKind | null> {
  const header = new Uint8Array(await file.slice(0, 16).arrayBuffer())

  if (isPdfSignature(header)) return 'pdf'
  if (isJpegSignature(header) || isPngSignature(header) || isWebpSignature(header)) return 'image'

  return null
}

export function FileUpload({
  students,
  assignments,
  onUploaded,
  aiAvailable,
  ocrAvailable,
  resubmitTarget,
  onResubmitCleared,
}: {
  students: Student[]
  assignments: Assignment[]
  onUploaded: (submission: SubmissionDetail) => void
  aiAvailable: boolean
  ocrAvailable: boolean
  resubmitTarget?: Submission | SubmissionDetail | null
  onResubmitCleared?: () => void
}) {
  const [selectedStudent, setSelectedStudent] = useState<string>('')
  const [selectedAssignment, setSelectedAssignment] = useState<string>('')
  const [file, setFile] = useState<File | null>(null)
  const [previewUrl, setPreviewUrl] = useState<string>('')
  const [previewKind, setPreviewKind] = useState<PreviewKind | null>(null)
  const [isDragging, setIsDragging] = useState(false)
  const previewSelectionId = useRef(0)
  const [progress, setProgress] = useState(0)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    if (!resubmitTarget) return
    setSelectedStudent(String(resubmitTarget.student_id))
    setSelectedAssignment(String(resubmitTarget.assignment_id))
  }, [resubmitTarget])

  useEffect(() => {
    return () => {
      if (previewUrl) URL.revokeObjectURL(previewUrl)
    }
  }, [previewUrl])

  const isImage = previewKind === 'image'
  const isPdf = previewKind === 'pdf'
  const visibleAssignments = useMemo(
    () =>
      assignments.filter((assignment) => {
        if (!selectedStudent) return true
        if (!assignment.targets.length) return true
        return assignment.targets.some((target) => String(target.student_id) === selectedStudent)
      }),
    [assignments, selectedStudent],
  )

  const onFileChange = async (picked?: File) => {
    if (!picked) return
    if (!isAllowedFile(picked)) {
      setError(`Allowed file types: ${ALLOWED_FILE_LABEL}.`)
      return
    }
    if (picked.size > MAX_UPLOAD_BYTES) {
      setError('File exceeds the 25 MB size limit.')
      return
    }
    if (previewUrl) URL.revokeObjectURL(previewUrl)
    setPreviewUrl('')
    setPreviewKind(null)
    setFile(picked)
    setError('')

    const selectionId = ++previewSelectionId.current
    const nextPreviewKind = await getPreviewKind(picked)
    if (selectionId !== previewSelectionId.current || !nextPreviewKind) return

    const objectUrl = URL.createObjectURL(picked)
    if (!objectUrl.startsWith('blob:')) return
    if (selectionId !== previewSelectionId.current) {
      URL.revokeObjectURL(objectUrl)
      return
    }

    setPreviewKind(nextPreviewKind)
    setPreviewUrl(objectUrl)
  }

  const handleSubmit = async () => {
    if (!file || !selectedStudent || !selectedAssignment) {
      setError('Please choose a student, assignment, and file.')
      return
    }

    setSubmitting(true)
    setProgress(0)
    setError('')

    try {
      const result = await api.uploadSubmission(
        {
          file,
          student_id: Number(selectedStudent),
          assignment_id: Number(selectedAssignment),
          resubmission_of_submission_id: resubmitTarget?.id,
        },
        setProgress,
      )
      setProgress(100)
      onUploaded(result)
      setFile(null)
      if (previewUrl) URL.revokeObjectURL(previewUrl)
      setPreviewUrl('')
      setPreviewKind(null)
      if (!resubmitTarget) {
        setSelectedStudent('')
        setSelectedAssignment('')
      }
      onResubmitCleared?.()
    } catch (uploadError) {
      setError(uploadError instanceof Error ? uploadError.message : 'Upload failed.')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>{resubmitTarget ? 'Resubmit student work' : 'Submit student work'}</CardTitle>
        <CardDescription>
          {ocrAvailable && aiAvailable
            ? 'Drag and drop a scan/photo or use camera capture on mobile.'
            : 'Drag and drop a scan/photo or use camera capture on mobile. Reduced processing is active right now.'}
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="rounded-lg border bg-muted/20 p-3 text-sm">
          <p className="font-medium">Allowed types: {ALLOWED_FILE_LABEL}</p>
          <p className="text-muted-foreground">Maximum file size: 25 MB per file</p>
        </div>

        {resubmitTarget ? (
          <div className="flex flex-col gap-2 rounded-lg border border-primary/30 bg-primary/5 p-3 text-sm sm:flex-row sm:items-center sm:justify-between">
            <div>
              <p className="font-medium">Resubmitting submission #{resubmitTarget.id}</p>
              <p className="text-muted-foreground">
                Next upload becomes version {(resubmitTarget.submission_version || 1) + 1} and preserves prior history.
              </p>
            </div>
            <Button type="button" variant="outline" onClick={onResubmitCleared}>
              Cancel resubmission
            </Button>
          </div>
        ) : null}

        <div className="grid gap-4 md:grid-cols-2">
          <div className="space-y-2">
            <Label>Student</Label>
            <Select value={selectedStudent} onValueChange={setSelectedStudent} disabled={Boolean(resubmitTarget)}>
              <SelectTrigger>
                <SelectValue placeholder="Choose student" />
              </SelectTrigger>
              <SelectContent>
                {students.map((student) => (
                  <SelectItem key={student.id} value={String(student.id)}>
                    {student.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-2">
            <Label>Assignment</Label>
            <Select value={selectedAssignment} onValueChange={setSelectedAssignment} disabled={Boolean(resubmitTarget)}>
              <SelectTrigger>
                <SelectValue placeholder="Choose assignment" />
              </SelectTrigger>
              <SelectContent>
                {visibleAssignments.map((assignment) => (
                  <SelectItem key={assignment.id} value={String(assignment.id)}>
                    {assignment.title}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </div>

        <div
          className={`rounded-lg border-2 border-dashed p-6 text-center transition ${
            isDragging ? 'border-primary bg-primary/10' : 'border-muted-foreground/30'
          }`}
          onDragOver={(event) => {
            event.preventDefault()
            setIsDragging(true)
          }}
          onDragLeave={() => setIsDragging(false)}
          onDrop={(event) => {
            event.preventDefault()
            setIsDragging(false)
            onFileChange(event.dataTransfer.files?.[0])
          }}
        >
          <Upload className="mx-auto mb-2 h-7 w-7 text-muted-foreground" />
          <p className="text-sm font-medium">Drop file here or browse</p>
          <p className="mt-1 text-xs text-muted-foreground">{ALLOWED_FILE_LABEL} supported</p>
          <div className="mt-3 flex flex-col justify-center gap-2 sm:flex-row">
            <Label htmlFor="file-upload" className="cursor-pointer">
              <Input
                id="file-upload"
                type="file"
                className="hidden"
                accept=".pdf,.jpg,.jpeg,.png,.heic,.heif,.tif,.tiff,.webp,application/pdf,image/jpeg,image/png,image/heic,image/heif,image/tiff,image/webp"
                onChange={(event) => onFileChange(event.target.files?.[0])}
              />
              <Button type="button" variant="secondary">
                <FileText className="mr-2 h-4 w-4" />
                Choose file
              </Button>
            </Label>
            <Label htmlFor="camera-upload" className="cursor-pointer">
              <Input
                id="camera-upload"
                type="file"
                className="hidden"
                accept="image/jpeg,image/png,image/heic,image/heif,image/tiff,image/webp"
                capture="environment"
                onChange={(event) => onFileChange(event.target.files?.[0])}
              />
              <Button type="button" variant="outline">
                <Camera className="mr-2 h-4 w-4" />
                Use camera
              </Button>
            </Label>
            {resubmitTarget ? (
              <Button type="button" variant="ghost" onClick={onResubmitCleared}>
                <RotateCcw className="mr-2 h-4 w-4" />
                Clear
              </Button>
            ) : null}
          </div>
        </div>

        {file ? (
          <div className="rounded-lg border bg-muted/20 p-3 text-sm">
            <p className="font-medium">Selected: {file.name}</p>
            <p className="text-muted-foreground">{formatBytes(file.size)}</p>
            {previewUrl ? (
              <div className="mt-3">
                {isImage ? (
                  <img alt="Submission preview" src={previewUrl} className="max-h-56 rounded-md border object-contain" />
                ) : isPdf ? (
                  <object aria-label="PDF preview" data={previewUrl} type="application/pdf" className="h-64 w-full rounded-md border">
                    <p className="p-4 text-xs text-muted-foreground">PDF preview is unavailable in this browser.</p>
                  </object>
                ) : (
                  <p className="text-xs text-muted-foreground">Preview is unavailable for this file type, but the upload is supported.</p>
                )}
              </div>
            ) : null}
          </div>
        ) : null}

        {submitting ? (
          <div className="space-y-2">
            <Progress value={progress} />
            <p className="text-xs text-muted-foreground">Uploading… {progress}%</p>
          </div>
        ) : null}

        {error ? <p className="text-sm text-destructive">{error}</p> : null}

        <Button type="button" onClick={() => void handleSubmit()} disabled={submitting || !file}>
          {resubmitTarget
            ? 'Upload new version'
            : aiAvailable && ocrAvailable
              ? 'Upload submission'
              : 'Upload for manual review'}
        </Button>
      </CardContent>
    </Card>
  )
}
