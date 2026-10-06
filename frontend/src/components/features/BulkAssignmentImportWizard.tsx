import { type DragEvent, useEffect, useMemo, useRef, useState } from 'react'
import { AlertCircle, CheckCircle2, FileText, Loader2, Sparkles, Trash2, Upload, X } from 'lucide-react'
import { ApiError, api } from '@/lib/api'
import type {
  AssignmentCategory,
  AssignmentImportAnswer,
  AssignmentImportConfirmResponse,
  AssignmentImportDefaults,
  AssignmentImportItem,
  AssignmentImportQuestion,
  AssignmentImportSession,
  AssignmentRecurrence,
  AssignmentTargetInput,
  GradingPeriod,
  Student,
  Subject,
} from '@/types/api'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardAction, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Progress } from '@/components/ui/progress'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Textarea } from '@/components/ui/textarea'

type WizardStep = 'upload' | 'clarify' | 'preview' | 'complete'

type BulkAssignmentImportWizardProps = {
  subjects: Subject[]
  students: Student[]
  gradingPeriods: GradingPeriod[]
  onClose: () => void
  onImported: () => void
}

type ClarificationDraft = {
  value: string
  values: string[]
  applyToAll: boolean
}

const ACCEPTED_EXTENSIONS = ['.txt', '.md', '.docx', '.pdf']
const ACCEPTED_MIME_TYPES = [
  'text/plain',
  'text/markdown',
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
  'application/pdf',
]
const ACCEPTED_FILE_TYPES = `${ACCEPTED_EXTENSIONS.join(',')},${ACCEPTED_MIME_TYPES.join(',')}`
const MAX_FILE_BYTES = 10 * 1024 * 1024
const categories: AssignmentCategory[] = ['homework', 'quiz', 'test', 'project', 'participation', 'extra_credit', 'other']
const recurrences: AssignmentRecurrence[] = ['none', 'daily', 'weekly']

function formatFileSize(bytes: number) {
  if (bytes >= 1024 * 1024) return `${(bytes / 1024 / 1024).toFixed(1)} MB`
  return `${Math.max(1, Math.round(bytes / 1024))} KB`
}

function normalizeDateInput(value?: string | null) {
  return value ? value.slice(0, 10) : ''
}

function toApiDateTime(value?: string | null) {
  if (!value) return null
  return value.includes('T') ? value : `${value}T00:00:00Z`
}

function serializeItemForApi(item: AssignmentImportItem): AssignmentImportItem {
  return {
    ...item,
    due_date: toApiDateTime(item.due_date),
    targets: item.targets.map((target) => ({
      ...target,
      due_date: toApiDateTime(target.due_date) || undefined,
    })),
  }
}

function statusLabel(status?: AssignmentImportItem['status']) {
  switch (status) {
    case 'ready':
      return 'Ready'
    case 'needs_clarification':
      return 'Needs info'
    case 'invalid':
      return 'Fix row'
    default:
      return 'Draft'
  }
}

function statusVariant(status?: AssignmentImportItem['status']): 'default' | 'secondary' | 'destructive' | 'outline' {
  if (status === 'ready') return 'default'
  if (status === 'invalid') return 'destructive'
  if (status === 'needs_clarification') return 'secondary'
  return 'outline'
}

function isStudentQuestion(question: AssignmentImportQuestion) {
  return question.field === 'student_ids' || question.field === 'targets' || question.field.includes('student')
}

function parseChoiceValue(value: string, question: AssignmentImportQuestion) {
  const match = question.choices.find((choice) => String(choice.id) === value)
  return match?.id ?? value
}

function getFriendlyApiError(error: unknown) {
  if (error instanceof ApiError && (error.status === 503 || error.code === 'ai_import_unavailable')) {
    return 'AI assignment import is not configured yet. Ask an administrator to enable AI import, or use the regular assignment form for now.'
  }
  return error instanceof Error ? error.message : 'Unable to analyze this file right now.'
}

export function BulkAssignmentImportWizard({
  subjects,
  students,
  gradingPeriods,
  onClose,
  onImported,
}: BulkAssignmentImportWizardProps) {
  const fileInputRef = useRef<HTMLInputElement | null>(null)
  const [step, setStep] = useState<WizardStep>('upload')
  const [file, setFile] = useState<File | null>(null)
  const [isDragging, setIsDragging] = useState(false)
  const [analyzing, setAnalyzing] = useState(false)
  const [analysisProgress, setAnalysisProgress] = useState(0)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [draft, setDraft] = useState<AssignmentImportSession | null>(null)
  const [answers, setAnswers] = useState<Record<string, ClarificationDraft>>({})
  const [selectedItemIds, setSelectedItemIds] = useState<string[]>([])
  const [confirmResult, setConfirmResult] = useState<AssignmentImportConfirmResponse | null>(null)
  const [defaults, setDefaults] = useState({
    subject_id: 'none',
    student_ids: [] as string[],
    grading_period_id: 'none',
    due_date: '',
  })

  useEffect(() => {
    if (!analyzing) {
      setAnalysisProgress(0)
      return
    }

    setAnalysisProgress(10)
    const interval = window.setInterval(() => {
      setAnalysisProgress((current) => {
        if (current >= 90) return current
        return Math.min(90, current + Math.max(4, Math.round((90 - current) / 4)))
      })
    }, 450)

    return () => window.clearInterval(interval)
  }, [analyzing])

  const selectedFileFeedback = useMemo(() => {
    if (!file) return 'Choose a TXT, Markdown, Word document, or PDF up to 10 MB.'
    return `${file.name} • ${formatFileSize(file.size)}`
  }, [file])

  const chooseFile = (nextFile: File | undefined) => {
    setError('')
    if (!nextFile) return
    const lowerName = nextFile.name.toLowerCase()
    const hasAllowedExtension = ACCEPTED_EXTENSIONS.some((extension) => lowerName.endsWith(extension))
    const hasAllowedMime = !nextFile.type || ACCEPTED_MIME_TYPES.includes(nextFile.type)

    if (!hasAllowedExtension || !hasAllowedMime) {
      setFile(null)
      setError('Please choose a .txt, .md, .docx, or .pdf file.')
      return
    }

    if (nextFile.size > MAX_FILE_BYTES) {
      setFile(null)
      setError('That file is larger than 10 MB. Please split the plan or choose a smaller file.')
      return
    }

    setFile(nextFile)
  }

  const buildDefaults = (): AssignmentImportDefaults => {
    const payload: AssignmentImportDefaults = {
      category: 'homework',
      max_score: 100,
      weight: 1,
    }
    if (defaults.subject_id !== 'none') payload.subject_id = Number(defaults.subject_id)
    if (defaults.grading_period_id !== 'none') payload.grading_period_id = Number(defaults.grading_period_id)
    if (defaults.student_ids.length) payload.student_ids = defaults.student_ids.map(Number)
    if (defaults.due_date) payload.due_date = `${defaults.due_date}T00:00:00Z`
    return payload
  }

  const setSession = (session: AssignmentImportSession) => {
    setDraft(session)
    setSelectedItemIds((current) => {
      const itemIds = session.items.map((item) => item.client_item_id)
      const next = current.filter((itemId) => itemIds.includes(itemId))
      if (next.length) return next
      return session.items
        .filter((item) => item.status !== 'invalid')
        .map((item) => item.client_item_id)
    })
  }

  const analyze = async () => {
    if (!file) {
      setError('Choose a planning file before starting the AI import.')
      return
    }

    setError('')
    setAnalyzing(true)
    try {
      const session = await api.createAssignmentImportSession(file, buildDefaults())
      setAnalysisProgress(100)
      const fullSession = session.items.length ? session : await api.getAssignmentImportSession(session.id)
      setSession(fullSession)
      setAnswers({})
      setStep(fullSession.questions.length ? 'clarify' : 'preview')
    } catch (uploadError) {
      setError(getFriendlyApiError(uploadError))
    } finally {
      setAnalyzing(false)
    }
  }

  const updateAnswer = (question: AssignmentImportQuestion, patch: Partial<ClarificationDraft>) => {
    setAnswers((current) => {
      const existing = current[question.id] ?? {
        value: '',
        values: [],
        applyToAll: question.allow_apply_to_all,
      }
      return {
        ...current,
        [question.id]: {
          ...existing,
          ...patch,
        },
      }
    })
  }

  const toggleAnswerValue = (question: AssignmentImportQuestion, choiceId: string) => {
    const current = answers[question.id]?.values ?? []
    updateAnswer(question, {
      values: current.includes(choiceId) ? current.filter((value) => value !== choiceId) : [...current, choiceId],
    })
  }

  const answerToPayload = (question: AssignmentImportQuestion): AssignmentImportAnswer | null => {
    const draftAnswer = answers[question.id]
    if (!draftAnswer) return null
    const indexes =
      draftAnswer.applyToAll || !question.allow_apply_to_all
        ? question.assignment_indexes
        : question.assignment_indexes.slice(0, 1)

    if (isStudentQuestion(question)) {
      if (!draftAnswer.values.length) return null
      return {
        question_id: question.id,
        value: draftAnswer.values.map((value) => parseChoiceValue(value, question)),
        apply_to_assignment_indexes: indexes,
      }
    }

    if (!draftAnswer.value) return null
    return {
      question_id: question.id,
      value: parseChoiceValue(draftAnswer.value, question),
      apply_to_assignment_indexes: indexes,
    }
  }

  const submitClarifications = async () => {
    if (!draft) return
    const payloadAnswers = draft.questions.map(answerToPayload).filter((answer): answer is AssignmentImportAnswer => Boolean(answer))
    if (!payloadAnswers.length) {
      setError('Answer at least one question to continue.')
      return
    }

    setSaving(true)
    setError('')
    try {
      const updated = await api.updateAssignmentImportSession(draft.id, { answers: payloadAnswers })
      setSession(updated)
      setStep(updated.questions.length ? 'clarify' : 'preview')
    } catch (clarificationError) {
      setError(clarificationError instanceof Error ? clarificationError.message : 'Unable to apply those answers.')
    } finally {
      setSaving(false)
    }
  }

  const updateItem = (clientItemId: string, patch: Partial<AssignmentImportItem>) => {
    setDraft((current) =>
      current
        ? {
            ...current,
            items: current.items.map((item) =>
              item.client_item_id === clientItemId
                ? {
                    ...item,
                    ...patch,
                  }
                : item,
            ),
          }
        : current,
    )
  }

  const toggleStudentTarget = (item: AssignmentImportItem, studentId: number) => {
    const hasTarget = item.targets.some((target) => target.student_id === studentId)
    const targets: AssignmentTargetInput[] = hasTarget
      ? item.targets.filter((target) => target.student_id !== studentId)
      : [
          ...item.targets,
          {
            student_id: studentId,
            due_date: normalizeDateInput(item.due_date) || undefined,
            status: 'assigned',
          },
        ]
    updateItem(item.client_item_id, { targets })
  }

  const savePreviewEdits = async () => {
    if (!draft) return null
    setSaving(true)
    setError('')
    try {
      const updated = await api.updateAssignmentImportSession(draft.id, { items: draft.items.map(serializeItemForApi) })
      setSession(updated)
      return updated
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : 'Unable to save the preview edits.')
      return null
    } finally {
      setSaving(false)
    }
  }

  const confirm = async () => {
    if (!draft) return
    if (!selectedItemIds.length) {
      setError('Select at least one ready assignment to create.')
      return
    }

    const updated = await savePreviewEdits()
    if (!updated) return

    setSaving(true)
    setError('')
    try {
      const result = await api.confirmAssignmentImportSession(updated.id, {
        client_revision: updated.revision,
        item_ids: selectedItemIds,
      })
      setConfirmResult(result)
      setStep('complete')
      onImported()
    } catch (confirmError) {
      setError(confirmError instanceof Error ? confirmError.message : 'Unable to create these assignments.')
    } finally {
      setSaving(false)
    }
  }

  const toggleDefaultStudent = (studentId: number) => {
    const key = String(studentId)
    setDefaults((current) => ({
      ...current,
      student_ids: current.student_ids.includes(key)
        ? current.student_ids.filter((value) => value !== key)
        : [...current.student_ids, key],
    }))
  }

  return (
    <Card>
      <CardHeader>
        <div>
          <CardTitle>Import assignments</CardTitle>
          <CardDescription>Upload a planning file, answer any friendly follow-up questions, review each row, then create assignments.</CardDescription>
        </div>
        <CardAction>
          <Button type="button" variant="ghost" size="sm" onClick={onClose}>
            <X className="h-4 w-4" />
            Close
          </Button>
        </CardAction>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="flex flex-wrap gap-2">
          {[
            ['upload', 'Upload'],
            ['clarify', 'Clarify'],
            ['preview', 'Preview'],
            ['complete', 'Done'],
          ].map(([value, label], index) => (
            <Badge key={value} variant={value === step ? 'secondary' : 'outline'}>
              {index + 1}. {label}
            </Badge>
          ))}
        </div>

        {error ? (
          <div role="alert" className="flex gap-2 rounded-lg border border-destructive/30 bg-destructive/5 px-4 py-3 text-sm text-destructive">
            <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
            <span>{error}</span>
          </div>
        ) : null}

        {step === 'upload' ? (
          <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_320px]">
            <div
              className={`rounded-lg border-2 border-dashed p-6 text-center transition ${
                isDragging ? 'border-primary bg-primary/10' : 'border-muted-foreground/30'
              }`}
              onDragOver={(event: DragEvent<HTMLDivElement>) => {
                event.preventDefault()
                setIsDragging(true)
              }}
              onDragLeave={() => setIsDragging(false)}
              onDrop={(event: DragEvent<HTMLDivElement>) => {
                event.preventDefault()
                setIsDragging(false)
                chooseFile(event.dataTransfer.files?.[0])
              }}
            >
              <FileText className="mx-auto mb-3 h-9 w-9 text-muted-foreground" />
              <p className="text-base font-medium">Drop your assignment plan here</p>
              <p className="mx-auto mt-1 max-w-xl text-sm text-muted-foreground">
                We accept TXT, Markdown, Word documents, and PDFs. Scanned image-only PDFs may need to be typed or converted first.
              </p>
              <div className="mt-4 flex flex-wrap items-center justify-center gap-2">
                <input
                  ref={fileInputRef}
                  id="bulk-assignment-import-file"
                  type="file"
                  className="sr-only"
                  accept={ACCEPTED_FILE_TYPES}
                  onChange={(event) => chooseFile(event.target.files?.[0])}
                />
                <Button type="button" variant="secondary" onClick={() => fileInputRef.current?.click()}>
                  <Upload className="h-4 w-4" />
                  Choose file
                </Button>
                <Button type="button" onClick={() => void analyze()} disabled={!file || analyzing}>
                  {analyzing ? <Loader2 className="h-4 w-4 animate-spin" /> : <Sparkles className="h-4 w-4" />}
                  Analyze with AI
                </Button>
              </div>
              <p className="mt-3 text-sm text-muted-foreground">{selectedFileFeedback}</p>
              {analyzing ? (
                <div className="mx-auto mt-4 max-w-md space-y-2 text-left">
                  <div className="flex items-center justify-between text-xs text-muted-foreground">
                    <span>Uploading, extracting text, and drafting assignments…</span>
                    <span>{analysisProgress}%</span>
                  </div>
                  <Progress value={analysisProgress} />
                </div>
              ) : null}
            </div>

            <Card size="sm">
              <CardHeader>
                <CardTitle>Helpful defaults</CardTitle>
                <CardDescription>Optional. These fill gaps when the file does not name a subject, student, or due date.</CardDescription>
              </CardHeader>
              <CardContent className="space-y-3">
                <div className="space-y-2">
                  <Label>Subject</Label>
                  <Select value={defaults.subject_id} onValueChange={(value) => setDefaults((current) => ({ ...current, subject_id: value }))}>
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="none">Ask me if missing</SelectItem>
                      {subjects.map((subject) => (
                        <SelectItem key={subject.id} value={String(subject.id)}>
                          {subject.name}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-2">
                  <Label>Due date</Label>
                  <Input
                    type="date"
                    value={defaults.due_date}
                    onChange={(event) => setDefaults((current) => ({ ...current, due_date: event.target.value }))}
                  />
                </div>
                <div className="space-y-2">
                  <Label>Grading period</Label>
                  <Select
                    value={defaults.grading_period_id}
                    onValueChange={(value) => setDefaults((current) => ({ ...current, grading_period_id: value }))}
                  >
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="none">No default</SelectItem>
                      {gradingPeriods.map((period) => (
                        <SelectItem key={period.id} value={String(period.id)}>
                          {period.name}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-2">
                  <Label>Students</Label>
                  <div className="max-h-40 space-y-2 overflow-auto rounded-lg border p-2">
                    {students.length ? (
                      students.map((student) => (
                        <label key={student.id} className="flex items-center gap-2 text-sm">
                          <input
                            type="checkbox"
                            checked={defaults.student_ids.includes(String(student.id))}
                            onChange={() => toggleDefaultStudent(student.id)}
                          />
                          <span>{student.name}</span>
                        </label>
                      ))
                    ) : (
                      <p className="text-sm text-muted-foreground">No students found.</p>
                    )}
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>
        ) : null}

        {step === 'clarify' && draft ? (
          <div className="space-y-4">
            <SummaryCards draft={draft} />
            <div className="space-y-3">
              {draft.questions.map((question) => {
                const answer = answers[question.id] ?? {
                  value: '',
                  values: [],
                  applyToAll: question.allow_apply_to_all,
                }
                return (
                  <Card key={question.id} size="sm">
                    <CardHeader>
                      <CardTitle>{question.message}</CardTitle>
                      <CardDescription>
                        {question.assignment_indexes.length > 1
                          ? `${question.assignment_indexes.length} assignments need this answer.`
                          : 'One assignment needs this answer.'}
                      </CardDescription>
                    </CardHeader>
                    <CardContent className="space-y-3">
                      {isStudentQuestion(question) ? (
                        <div className="grid gap-2 md:grid-cols-2">
                          {question.choices.map((choice) => (
                            <label key={String(choice.id)} className="flex items-center gap-2 rounded-md border p-2 text-sm">
                              <input
                                type="checkbox"
                                checked={answer.values.includes(String(choice.id))}
                                onChange={() => toggleAnswerValue(question, String(choice.id))}
                              />
                              <span>{choice.label}</span>
                            </label>
                          ))}
                        </div>
                      ) : question.choices.length ? (
                        <Select value={answer.value} onValueChange={(value) => updateAnswer(question, { value })}>
                          <SelectTrigger>
                            <SelectValue placeholder="Choose an answer" />
                          </SelectTrigger>
                          <SelectContent>
                            {question.choices.map((choice) => (
                              <SelectItem key={String(choice.id)} value={String(choice.id)}>
                                {choice.label}
                              </SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                      ) : (
                        <Input
                          value={answer.value}
                          onChange={(event) => updateAnswer(question, { value: event.target.value })}
                          placeholder="Type the missing value"
                        />
                      )}
                      {question.allow_apply_to_all ? (
                        <label className="flex items-center gap-2 text-sm text-muted-foreground">
                          <input
                            type="checkbox"
                            checked={answer.applyToAll}
                            onChange={(event) => updateAnswer(question, { applyToAll: event.target.checked })}
                          />
                          <span>Apply this answer to all unresolved assignments in this question</span>
                        </label>
                      ) : null}
                    </CardContent>
                  </Card>
                )
              })}
            </div>
            <div className="flex flex-wrap gap-2">
              <Button type="button" onClick={() => void submitClarifications()} disabled={saving}>
                {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <CheckCircle2 className="h-4 w-4" />}
                Apply answers
              </Button>
              <Button type="button" variant="outline" onClick={() => setStep('preview')}>
                Skip to preview
              </Button>
            </div>
          </div>
        ) : null}

        {step === 'preview' && draft ? (
          <div className="space-y-4">
            <SummaryCards draft={draft} />
            {draft.warnings.length ? (
              <div className="rounded-lg border bg-muted/20 px-4 py-3 text-sm text-muted-foreground">
                {draft.warnings.map((warning) => (
                  <p key={warning}>{warning}</p>
                ))}
              </div>
            ) : null}
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="w-10">Create</TableHead>
                  <TableHead>Assignment</TableHead>
                  <TableHead>Subject</TableHead>
                  <TableHead>Due</TableHead>
                  <TableHead>Scoring</TableHead>
                  <TableHead>Students</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead className="w-10">Remove</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {draft.items.map((item) => {
                  const selected = selectedItemIds.includes(item.client_item_id)
                  return (
                    <TableRow key={item.client_item_id}>
                      <TableCell>
                        <input
                          type="checkbox"
                          aria-label={`Create ${item.title || 'assignment'}`}
                          checked={selected}
                          disabled={item.status === 'invalid'}
                          onChange={(event) =>
                            setSelectedItemIds((current) =>
                              event.target.checked
                                ? [...current, item.client_item_id]
                                : current.filter((itemId) => itemId !== item.client_item_id),
                            )
                          }
                        />
                      </TableCell>
                      <TableCell className="min-w-72 space-y-2 whitespace-normal">
                        <Input
                          value={item.title || ''}
                          onChange={(event) => updateItem(item.client_item_id, { title: event.target.value })}
                          placeholder="Assignment title"
                        />
                        <Textarea
                          value={item.description || ''}
                          onChange={(event) => updateItem(item.client_item_id, { description: event.target.value })}
                          placeholder="Optional directions"
                        />
                        {item.source_excerpt ? <p className="text-xs text-muted-foreground">From file: “{item.source_excerpt}”</p> : null}
                      </TableCell>
                      <TableCell className="min-w-44">
                        <Select
                          value={item.subject_id ? String(item.subject_id) : 'none'}
                          onValueChange={(value) =>
                            updateItem(item.client_item_id, { subject_id: value === 'none' ? null : Number(value) })
                          }
                        >
                          <SelectTrigger>
                            <SelectValue />
                          </SelectTrigger>
                          <SelectContent>
                            <SelectItem value="none">Choose subject</SelectItem>
                            {subjects.map((subject) => (
                              <SelectItem key={subject.id} value={String(subject.id)}>
                                {subject.name}
                              </SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                      </TableCell>
                      <TableCell className="min-w-40 space-y-2">
                        <Input
                          type="date"
                          value={normalizeDateInput(item.due_date)}
                          onChange={(event) => updateItem(item.client_item_id, { due_date: event.target.value || null })}
                        />
                        <Select
                          value={item.grading_period_id ? String(item.grading_period_id) : 'none'}
                          onValueChange={(value) =>
                            updateItem(item.client_item_id, { grading_period_id: value === 'none' ? null : Number(value) })
                          }
                        >
                          <SelectTrigger>
                            <SelectValue />
                          </SelectTrigger>
                          <SelectContent>
                            <SelectItem value="none">No period</SelectItem>
                            {gradingPeriods.map((period) => (
                              <SelectItem key={period.id} value={String(period.id)}>
                                {period.name}
                              </SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                      </TableCell>
                      <TableCell className="min-w-44 space-y-2">
                        <Select
                          value={item.category}
                          onValueChange={(value: AssignmentCategory) => updateItem(item.client_item_id, { category: value })}
                        >
                          <SelectTrigger>
                            <SelectValue />
                          </SelectTrigger>
                          <SelectContent>
                            {categories.map((category) => (
                              <SelectItem key={category} value={category}>
                                {category}
                              </SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                        <div className="grid grid-cols-2 gap-2">
                          <Input
                            aria-label="Max score"
                            type="number"
                            min="1"
                            step="0.5"
                            value={item.max_score}
                            onChange={(event) => updateItem(item.client_item_id, { max_score: Number(event.target.value || 0) })}
                          />
                          <Input
                            aria-label="Weight"
                            type="number"
                            min="0"
                            step="0.1"
                            value={item.weight}
                            onChange={(event) => updateItem(item.client_item_id, { weight: Number(event.target.value || 0) })}
                          />
                        </div>
                        <Select
                          value={item.recurrence}
                          onValueChange={(value: AssignmentRecurrence) => updateItem(item.client_item_id, { recurrence: value })}
                        >
                          <SelectTrigger>
                            <SelectValue />
                          </SelectTrigger>
                          <SelectContent>
                            {recurrences.map((recurrence) => (
                              <SelectItem key={recurrence} value={recurrence}>
                                {recurrence}
                              </SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                        {item.recurrence !== 'none' ? (
                          <Input
                            aria-label="Recurrence end date"
                            type="date"
                            value={normalizeDateInput(item.recurrence_end_date)}
                            onChange={(event) => updateItem(item.client_item_id, { recurrence_end_date: event.target.value || null })}
                          />
                        ) : null}
                      </TableCell>
                      <TableCell className="min-w-44 whitespace-normal">
                        <div className="max-h-40 space-y-2 overflow-auto rounded-lg border p-2">
                          {students.map((student) => (
                            <label key={student.id} className="flex items-center gap-2 text-sm">
                              <input
                                type="checkbox"
                                checked={item.targets.some((target) => target.student_id === student.id)}
                                onChange={() => toggleStudentTarget(item, student.id)}
                              />
                              <span>{student.name}</span>
                            </label>
                          ))}
                        </div>
                      </TableCell>
                      <TableCell className="min-w-44 whitespace-normal">
                        <Badge variant={statusVariant(item.status)}>{statusLabel(item.status)}</Badge>
                        {(item.validation_errors?.length || item.errors?.length) ? (
                          <ul className="mt-2 list-disc space-y-1 pl-4 text-xs text-destructive">
                            {[...(item.validation_errors ?? []), ...(item.errors ?? [])].map((validationError) => (
                              <li key={validationError}>{validationError}</li>
                            ))}
                          </ul>
                        ) : null}
                        {item.missing_fields?.length ? (
                          <p className="mt-2 text-xs text-muted-foreground">Missing: {item.missing_fields.join(', ')}</p>
                        ) : null}
                      </TableCell>
                      <TableCell>
                        <Button
                          type="button"
                          variant="ghost"
                          size="icon"
                          onClick={() => setSelectedItemIds((current) => current.filter((itemId) => itemId !== item.client_item_id))}
                          aria-label={`Skip ${item.title || 'assignment'}`}
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      </TableCell>
                    </TableRow>
                  )
                })}
              </TableBody>
            </Table>
            <div className="flex flex-wrap gap-2">
              <Button type="button" variant="outline" onClick={() => void savePreviewEdits()} disabled={saving}>
                Save preview edits
              </Button>
              <Button type="button" onClick={() => void confirm()} disabled={saving || !selectedItemIds.length}>
                {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <CheckCircle2 className="h-4 w-4" />}
                Create {selectedItemIds.length} assignment{selectedItemIds.length === 1 ? '' : 's'}
              </Button>
            </div>
          </div>
        ) : null}

        {step === 'complete' && confirmResult ? (
          <Card size="sm">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <CheckCircle2 className="h-5 w-5 text-primary" />
                Import complete
              </CardTitle>
              <CardDescription>
                Created {confirmResult.assignment_count} assignment{confirmResult.assignment_count === 1 ? '' : 's'}.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              <p className="text-sm text-muted-foreground">
                Assignment IDs: {confirmResult.created_assignment_ids.length ? confirmResult.created_assignment_ids.join(', ') : 'none returned'}
              </p>
              {confirmResult.skipped_item_ids.length ? (
                <p className="text-sm text-muted-foreground">Skipped rows: {confirmResult.skipped_item_ids.join(', ')}</p>
              ) : null}
              <Button type="button" onClick={onClose}>
                Back to assignments
              </Button>
            </CardContent>
          </Card>
        ) : null}
      </CardContent>
    </Card>
  )
}

function SummaryCards({ draft }: { draft: AssignmentImportSession }) {
  return (
    <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
      <Card size="sm">
        <CardHeader>
          <CardDescription>Total rows</CardDescription>
          <CardTitle>{draft.summary.total}</CardTitle>
        </CardHeader>
      </Card>
      <Card size="sm">
        <CardHeader>
          <CardDescription>Ready</CardDescription>
          <CardTitle>{draft.summary.ready}</CardTitle>
        </CardHeader>
      </Card>
      <Card size="sm">
        <CardHeader>
          <CardDescription>Need answers</CardDescription>
          <CardTitle>{draft.summary.needs_clarification}</CardTitle>
        </CardHeader>
      </Card>
      <Card size="sm">
        <CardHeader>
          <CardDescription>Need fixes</CardDescription>
          <CardTitle>{draft.summary.invalid}</CardTitle>
        </CardHeader>
      </Card>
    </div>
  )
}
