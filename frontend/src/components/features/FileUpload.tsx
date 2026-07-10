import { useEffect, useMemo, useRef, useState } from 'react'
import { Camera, Check, FileText, Lock, RotateCcw, Upload } from 'lucide-react'
import { useTranslation } from 'react-i18next'
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
type StepState = 'done' | 'current' | 'upcoming'

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

function StepIndicator({ num, state, label }: { num: number; state: StepState; label: string }) {
  return (
    <div className="flex flex-col items-center gap-1.5">
      <div
        className={`flex h-8 w-8 items-center justify-center rounded-full text-xs font-semibold transition-colors ${
          state === 'done'
            ? 'bg-primary text-primary-foreground'
            : state === 'current'
              ? 'border-2 border-primary text-primary'
              : 'border-2 border-muted-foreground/30 text-muted-foreground/50'
        }`}
        aria-hidden="true"
      >
        {state === 'done' ? <Check className="h-4 w-4" /> : num}
      </div>
      <span
        className={`text-center text-xs leading-tight ${
          state === 'done' ? 'font-medium text-primary' : state === 'current' ? 'font-medium text-foreground' : 'text-muted-foreground/60'
        }`}
      >
        {label}
      </span>
    </div>
  )
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
  const { t } = useTranslation('common')
  const [selectedStudent, setSelectedStudent] = useState<string>('')
  const [selectedAssignment, setSelectedAssignment] = useState<string>('')
  const [file, setFile] = useState<File | null>(null)
  const [previewKind, setPreviewKind] = useState<PreviewKind | null>(null)
  const [isDragging, setIsDragging] = useState(false)
  const previewSelectionId = useRef(0)
  const previewCanvasRef = useRef<HTMLCanvasElement | null>(null)
  const [progress, setProgress] = useState(0)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    if (!resubmitTarget) return
    setSelectedStudent(String(resubmitTarget.student_id))
    setSelectedAssignment(String(resubmitTarget.assignment_id))
  }, [resubmitTarget])

  useEffect(() => {
    let cancelled = false

    const canvas = previewCanvasRef.current
    if (!canvas) return

    const context = canvas.getContext('2d')
    if (!context) return

    context.clearRect(0, 0, canvas.width, canvas.height)

    if (!file || previewKind !== 'image' || typeof createImageBitmap !== 'function') {
      canvas.width = 0
      canvas.height = 0
      return
    }

    void createImageBitmap(file)
      .then((bitmap) => {
        if (cancelled) {
          bitmap.close()
          return
        }

        const maxWidth = 640
        const maxHeight = 224
        const scale = Math.min(1, maxWidth / bitmap.width, maxHeight / bitmap.height)
        const width = Math.max(1, Math.round(bitmap.width * scale))
        const height = Math.max(1, Math.round(bitmap.height * scale))

        canvas.width = width
        canvas.height = height
        context.clearRect(0, 0, width, height)
        context.drawImage(bitmap, 0, 0, width, height)
        bitmap.close()
      })
      .catch(() => {
        if (cancelled) return
        canvas.width = 0
        canvas.height = 0
      })

    return () => {
      cancelled = true
    }
  }, [file, previewKind])

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

  // The file zone is locked until both student and assignment are chosen.
  const readyForFile = Boolean(selectedStudent && selectedAssignment)

  const step1State: StepState = selectedStudent ? 'done' : 'current'
  const step2State: StepState = selectedAssignment ? 'done' : selectedStudent ? 'current' : 'upcoming'
  const step3State: StepState = file ? 'done' : readyForFile ? 'current' : 'upcoming'

  const onFileChange = async (picked?: File) => {
    if (!picked) return
    if (!isAllowedFile(picked)) {
      setError(t('upload.errorAllowedTypes', { formats: ALLOWED_FILE_LABEL }))
      return
    }
    if (picked.size > MAX_UPLOAD_BYTES) {
      setError(t('upload.errorFileSize'))
      return
    }
    setPreviewKind(null)
    setFile(picked)
    setError('')

    const selectionId = ++previewSelectionId.current
    const nextPreviewKind = await getPreviewKind(picked)
    if (selectionId !== previewSelectionId.current || !nextPreviewKind) return

    setPreviewKind(nextPreviewKind)
  }

  const handleSubmit = async () => {
    if (!file || !selectedStudent || !selectedAssignment) {
      setError(t('upload.errorSelectAll'))
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
      setPreviewKind(null)
      if (!resubmitTarget) {
        setSelectedStudent('')
        setSelectedAssignment('')
      }
      onResubmitCleared?.()
    } catch (uploadError) {
      setError(uploadError instanceof Error ? uploadError.message : t('upload.errorSelectAll'))
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>{resubmitTarget ? t('upload.resubmitTitle') : t('upload.title')}</CardTitle>
        <CardDescription>
          {ocrAvailable && aiAvailable ? t('upload.descriptionFull') : t('upload.descriptionReduced')}
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-5">
        {/* Step progress indicator */}
        <div
          className="flex items-start justify-between gap-2"
          aria-label="Upload steps"
          role="list"
        >
          <div role="listitem" className="flex-1">
            <StepIndicator num={1} state={step1State} label={t('upload.step1Label')} />
          </div>
          {/* Connector line */}
          <div className={`mt-4 h-0.5 flex-1 self-start transition-colors ${step1State === 'done' ? 'bg-primary' : 'bg-muted-foreground/20'}`} aria-hidden="true" />
          <div role="listitem" className="flex-1">
            <StepIndicator num={2} state={step2State} label={t('upload.step2Label')} />
          </div>
          {/* Connector line */}
          <div className={`mt-4 h-0.5 flex-1 self-start transition-colors ${step2State === 'done' ? 'bg-primary' : 'bg-muted-foreground/20'}`} aria-hidden="true" />
          <div role="listitem" className="flex-1">
            <StepIndicator num={3} state={step3State} label={t('upload.step3Label')} />
          </div>
        </div>

        <div className="rounded-lg border bg-muted/20 p-3 text-sm">
          <p className="font-medium">{t('upload.allowedTypesLine', { formats: ALLOWED_FILE_LABEL })}</p>
          <p className="text-muted-foreground">{t('upload.maxSizeLine')}</p>
        </div>

        {resubmitTarget ? (
          <div className="flex flex-col gap-2 rounded-lg border border-primary/30 bg-primary/5 p-3 text-sm sm:flex-row sm:items-center sm:justify-between">
            <div>
              <p className="font-medium">{t('upload.resubmitBannerTitle', { id: resubmitTarget.id })}</p>
              <p className="text-muted-foreground">
                {t('upload.resubmitBannerBody', { version: (resubmitTarget.submission_version || 1) + 1 })}
              </p>
            </div>
            <Button type="button" variant="outline" onClick={onResubmitCleared}>
              {t('upload.cancelResubmit')}
            </Button>
          </div>
        ) : null}

        <div className="grid gap-4 md:grid-cols-2">
          <div className="space-y-2">
            <Label htmlFor="student-select">{t('upload.stepStudent')}</Label>
            <Select value={selectedStudent} onValueChange={setSelectedStudent} disabled={Boolean(resubmitTarget)}>
              <SelectTrigger id="student-select">
                <SelectValue placeholder={t('upload.placeholderStudent')} />
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
            <Label htmlFor="assignment-select">{t('upload.stepAssignment')}</Label>
            <Select value={selectedAssignment} onValueChange={setSelectedAssignment} disabled={Boolean(resubmitTarget)}>
              <SelectTrigger id="assignment-select">
                <SelectValue placeholder={t('upload.placeholderAssignment')} />
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

        {/* File zone — locked until both student and assignment are selected */}
        <div
          className={`rounded-lg border-2 border-dashed p-6 text-center transition ${
            !readyForFile
              ? 'cursor-not-allowed border-muted-foreground/20 bg-muted/30'
              : isDragging
                ? 'border-primary bg-primary/10'
                : 'border-muted-foreground/30'
          }`}
          onDragOver={(event) => {
            if (!readyForFile) return
            event.preventDefault()
            setIsDragging(true)
          }}
          onDragLeave={() => setIsDragging(false)}
          onDrop={(event) => {
            event.preventDefault()
            setIsDragging(false)
            if (!readyForFile) return
            void onFileChange(event.dataTransfer.files?.[0])
          }}
        >
          {!readyForFile ? (
            <>
              <Lock className="mx-auto mb-2 h-7 w-7 text-muted-foreground/40" aria-hidden="true" />
              <p id="file-zone-hint" className="text-sm text-muted-foreground">
                {t('upload.stepZoneLocked')}
              </p>
            </>
          ) : (
            <>
              <Upload className="mx-auto mb-2 h-7 w-7 text-muted-foreground" aria-hidden="true" />
              <p className="text-sm font-medium">{t('upload.dropZoneTitle')}</p>
              <p className="mt-1 text-xs text-muted-foreground">{t('upload.dropZoneHint', { formats: ALLOWED_FILE_LABEL })}</p>
              <div className="mt-3 flex flex-col justify-center gap-2 sm:flex-row">
                <Label htmlFor="file-upload" className="cursor-pointer">
                  <Input
                    id="file-upload"
                    type="file"
                    className="hidden"
                    accept=".pdf,.jpg,.jpeg,.png,.heic,.heif,.tif,.tiff,.webp,application/pdf,image/jpeg,image/png,image/heic,image/heif,image/tiff,image/webp"
                    onChange={(event) => void onFileChange(event.target.files?.[0])}
                  />
                  <Button type="button" variant="secondary" tabIndex={-1}>
                    <FileText className="mr-2 h-4 w-4" aria-hidden="true" />
                    {t('upload.chooseFile')}
                  </Button>
                </Label>
                <Label htmlFor="camera-upload" className="cursor-pointer">
                  <Input
                    id="camera-upload"
                    type="file"
                    className="hidden"
                    accept="image/jpeg,image/png,image/heic,image/heif,image/tiff,image/webp"
                    capture="environment"
                    onChange={(event) => void onFileChange(event.target.files?.[0])}
                  />
                  <Button type="button" variant="outline" tabIndex={-1}>
                    <Camera className="mr-2 h-4 w-4" aria-hidden="true" />
                    {t('upload.useCamera')}
                  </Button>
                </Label>
                {resubmitTarget ? (
                  <Button type="button" variant="ghost" onClick={onResubmitCleared}>
                    <RotateCcw className="mr-2 h-4 w-4" aria-hidden="true" />
                    {t('upload.cancelResubmit')}
                  </Button>
                ) : null}
              </div>
            </>
          )}
        </div>

        {file ? (
          <div className="rounded-lg border bg-muted/20 p-3 text-sm">
            <p className="font-medium">{t('upload.selectedFile', { name: file.name })}</p>
            <p className="text-muted-foreground">{formatBytes(file.size)}</p>
            {previewKind ? (
              <div className="mt-3">
                {isImage ? (
                  <canvas
                    ref={previewCanvasRef}
                    aria-label="Submission preview"
                    className="max-h-56 max-w-full rounded-md border object-contain"
                    role="img"
                  />
                ) : isPdf ? (
                  <p className="text-xs text-muted-foreground">PDF preview is disabled in the browser for security, but the upload is supported.</p>
                ) : (
                  <p className="text-xs text-muted-foreground">{t('upload.previewUnavailable')}</p>
                )}
              </div>
            ) : null}
          </div>
        ) : null}

        {submitting ? (
          <div className="space-y-2">
            <Progress value={progress} />
            <p className="text-xs text-muted-foreground">{t('upload.uploading', { progress })}</p>
          </div>
        ) : null}

        {error ? <p className="text-sm text-destructive" role="alert">{error}</p> : null}

        <Button type="button" onClick={() => void handleSubmit()} disabled={submitting || !file}>
          {resubmitTarget
            ? t('upload.uploadVersionButton')
            : aiAvailable && ocrAvailable
              ? t('upload.uploadButton')
              : t('upload.uploadManualButton')}
        </Button>
      </CardContent>
    </Card>
  )
}
