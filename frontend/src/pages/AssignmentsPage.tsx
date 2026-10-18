import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { FileText, Pencil, Plus, Trash2 } from 'lucide-react'
import { useSearchParams } from 'react-router-dom'
import { api } from '@/lib/api'
import type {
  Assignment,
  AssignmentCategory,
  AssignmentStatus,
  AssignmentTargetStatus,
  AnswerKeyQuestion,
  GradingPeriod,
  SchoolYear,
  Student,
  Subject,
} from '@/types/api'
import { useAuth } from '@/context/AuthContext'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Textarea } from '@/components/ui/textarea'
import { Badge } from '@/components/ui/badge'
import { EmptyState } from '@/components/common/EmptyState'
import { LoadingState } from '@/components/common/LoadingState'
import { ErrorState } from '@/components/common/ErrorState'
import { BulkAssignmentImportWizard } from '@/components/features/BulkAssignmentImportWizard'
import { PlanningCalendar, PlanningCalendarToolbar, PlanningEntry, usePlanningCalendar } from '@/components/features/PlanningCalendar'
import { assignmentDates, assignmentIsOverdue, fetchEveryPage, schoolDate, schoolDateLabel } from '@/lib/planning-calendar'

const assignmentStatuses: AssignmentStatus[] = ['pending', 'complete', 'graded']
const targetStatuses: AssignmentTargetStatus[] = ['assigned', 'submitted', 'graded', 'excused']
const categories: AssignmentCategory[] = ['homework', 'quiz', 'test', 'project', 'participation', 'extra_credit', 'other']
const recurrences = ['none', 'daily', 'weekly'] as const
const emptyAnswerKeyQuestion = (): AnswerKeyQuestion => ({
  question_number: '',
  correct_answer: '',
  points: 1,
  partial_credit_rules: '',
})

type TargetDraft = {
  due_date: string
  status: AssignmentTargetStatus
}

type AssignmentForm = {
  title: string
  description: string
  due_date: string
  status: AssignmentStatus
  subject_id: string
  category: AssignmentCategory
  grading_period_id: string
  weight: string
  max_score: string
  recurrence: (typeof recurrences)[number]
  recurrence_end_date: string
  rubric_description: string
  attachments: string
}

const emptyForm = (): AssignmentForm => ({
  title: '',
  description: '',
  due_date: '',
  status: 'pending',
  subject_id: '',
  category: 'homework',
  grading_period_id: 'none',
  weight: '1',
  max_score: '100',
  recurrence: 'none',
  recurrence_end_date: '',
  rubric_description: '',
  attachments: '',
})

function formatDateLabel(value?: string | null) {
  return value ? schoolDateLabel(value.slice(0, 10)) : 'TBD'
}

function normalizeTargetMap(assignment: Assignment): Record<string, TargetDraft> {
  return Object.fromEntries(
    assignment.targets.map((target) => [
      String(target.student_id),
      {
        due_date: target.due_date?.slice(0, 10) || assignment.due_date?.slice(0, 10) || '',
        status: target.status,
      },
    ]),
  )
}

export function AssignmentsPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const navigation = usePlanningCalendar()
  const { date, view, scope, range, page, setPage } = navigation
  const loadSequence = useRef(0)
  const { canManageCurriculum, studentId: scopedStudentId } = useAuth()
  const [assignments, setAssignments] = useState<Assignment[]>([])
  const [subjects, setSubjects] = useState<Subject[]>([])
  const [students, setStudents] = useState<Student[]>([])
  const [gradingPeriods, setGradingPeriods] = useState<GradingPeriod[]>([])
  const [schoolYears, setSchoolYears] = useState<SchoolYear[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [editing, setEditing] = useState<Assignment | null>(null)
  const [form, setForm] = useState<AssignmentForm>(emptyForm())
  const [targets, setTargets] = useState<Record<string, TargetDraft>>({})
  const [answerKeyQuestions, setAnswerKeyQuestions] = useState<AnswerKeyQuestion[]>([])
  const [showBulkImport, setShowBulkImport] = useState(false)
  const [weeklyImport, setWeeklyImport] = useState(false)
  const [showForm, setShowForm] = useState(false)
  const [filters, setFilters] = useState({
    q: searchParams.get('q') || searchParams.get('search') || '',
    category: searchParams.get('category') || 'all',
    grading_period_id: searchParams.get('grading_period_id') || 'all',
    subject_id: searchParams.get('subject_id') || 'all',
    student_id: scopedStudentId ? String(scopedStudentId) : searchParams.get('student_id') || 'all',
    status: searchParams.get('status') || 'all',
    due_from: searchParams.get('due_from') || '',
    due_to: searchParams.get('due_to') || '',
    sort: searchParams.get('sort') || 'due-asc',
  })
  const [hasLoaded, setHasLoaded] = useState(false)

  const load = useCallback(async () => {
    const sequence = ++loadSequence.current
    setLoading(true)
    setError('')
    try {
      const years = await api.listSchoolYears()
      const schoolYearDetails = await Promise.all(years.map((year) => api.getSchoolYear(year.id)))
      const allGradingPeriods = schoolYearDetails.flatMap((year) =>
        year.terms.flatMap((term) => term.grading_periods),
      )
      const [assignmentData, subjectData, studentData] = await Promise.all([
        fetchEveryPage((assignmentPage) => api.listAssignments({
          q: filters.q || undefined,
          category: filters.category as AssignmentCategory | 'all',
          grading_period_id: filters.grading_period_id === 'all' ? undefined : Number(filters.grading_period_id),
          subject_id: filters.subject_id === 'all' ? undefined : Number(filters.subject_id),
          student_id: scopedStudentId || (filters.student_id === 'all' ? undefined : Number(filters.student_id)),
          status: filters.status as AssignmentStatus | AssignmentTargetStatus | 'all',
          due_from: scope === 'calendar' ? range.start : scope === 'all' ? filters.due_from || undefined : undefined,
          due_to: scope === 'calendar' ? range.end : scope === 'overdue' ? schoolDate() : scope === 'all' ? filters.due_to || undefined : undefined,
          page: assignmentPage,
          page_size: 100,
        })),
        api.listSubjects(),
        api.listStudents(),
      ])
      if (sequence !== loadSequence.current) return
      setHasLoaded(true)
      setSchoolYears(years)
      setAssignments(assignmentData)
      setSubjects(subjectData)
      setStudents(studentData)
      setGradingPeriods(allGradingPeriods)
    } catch (loadError) {
      if (sequence === loadSequence.current) setError(loadError instanceof Error ? loadError.message : 'Unable to load assignments')
    } finally {
      if (sequence === loadSequence.current) setLoading(false)
    }
  }, [filters, scope, range.start, range.end, scopedStudentId])

  useEffect(() => {
    void load()
  }, [load])

  useEffect(() => {
    setSearchParams((current) => {
      const params = new URLSearchParams(current)
      if (!params.has('scope')) params.set('scope', scope)
      Object.entries(filters).forEach(([key, value]) => {
        params.delete(key)
        if (key === 'q') params.delete('search')
        if (value && value !== 'all') params.set(key === 'q' ? 'search' : key, value)
      })
      return params
    }, { replace: true })
  }, [filters, scope, setSearchParams])

  const resetForm = () => {
    setEditing(null)
    setForm(emptyForm())
    setTargets({})
    setAnswerKeyQuestions([])
    setShowForm(false)
  }

  const toggleStudent = (studentId: number) => {
    const key = String(studentId)
    setTargets((current) => {
      if (current[key]) {
        const next = { ...current }
        delete next[key]
        return next
      }
      return {
        ...current,
        [key]: {
          due_date: form.due_date,
          status: 'assigned',
        },
      }
    })
  }

  const save = async () => {
    if (!canManageCurriculum) return
    const targetEntries = Object.entries(targets).map(([studentId, target]) => ({
      student_id: Number(studentId),
      due_date: target.due_date || form.due_date || undefined,
      status: target.status,
    }))
    const attachmentItems = form.attachments
      .split('\n')
      .map((value) => value.trim())
      .filter(Boolean)
    const payload = {
      title: form.title,
      description: form.description,
      due_date: form.due_date || undefined,
      status: form.status,
      subject_id: form.subject_id ? Number(form.subject_id) : undefined,
      category: form.category,
      grading_period_id: form.grading_period_id !== 'none' ? Number(form.grading_period_id) : undefined,
      weight: Number(form.weight),
      max_score: Number(form.max_score),
      recurrence: form.recurrence,
      recurrence_end_date: form.recurrence === 'none' ? undefined : form.recurrence_end_date || undefined,
      rubric_description: form.rubric_description || undefined,
      attachments: attachmentItems,
      targets: targetEntries.length ? targetEntries : undefined,
    }

    const savedAssignment = editing
      ? await api.updateAssignment(editing.id, payload)
      : await api.createAssignment(payload)
    if (answerKeyQuestions.length || editing?.answer_key) {
      await api.upsertAnswerKey(savedAssignment.id, {
        questions: answerKeyQuestions
          .filter((question) => question.question_number.trim() && question.correct_answer.trim())
          .map((question) => ({
            ...question,
            partial_credit_rules: question.partial_credit_rules?.trim() || undefined,
          })),
      })
    }

    resetForm()
    setPage(1)
    await load()
  }

  const assignmentsWithDetails = useMemo(
    () =>
      assignments.map((assignment) => ({
        ...assignment,
        subjectName:
          assignment.subject?.name || subjects.find((subject) => subject.id === assignment.subject_id)?.name || 'Unassigned',
        gradingPeriodName:
          assignment.grading_period?.name ||
          gradingPeriods.find((gradingPeriod) => gradingPeriod.id === assignment.grading_period_id)?.name ||
          'No grading period',
      })),
    [assignments, gradingPeriods, subjects],
  )

  const sortedAssignments = useMemo(() => {
    const studentId = scopedStudentId || (filters.student_id === 'all' ? undefined : Number(filters.student_id))
    const dueDates = (assignment: Assignment) => assignmentDates(assignment, studentId)
    const effectiveDue = (assignment: Assignment) => dueDates(assignment).filter(Boolean).sort()[0] || '9999-12-31'
    const items = assignmentsWithDetails.filter((assignment) => {
      if (scope === 'undated') return dueDates(assignment).includes('')
      if (scope !== 'overdue') return true
      return assignmentIsOverdue(assignment, schoolDate(), studentId)
    })
    switch (filters.sort) {
      case 'due-desc':
        return items.sort(
          (a, b) =>
            effectiveDue(b).localeCompare(effectiveDue(a)) || a.id - b.id,
        )
      case 'title':
        return items.sort((a, b) => a.title.localeCompare(b.title) || a.id - b.id)
      default:
        return items.sort(
          (a, b) =>
            effectiveDue(a).localeCompare(effectiveDue(b)) || a.id - b.id,
        )
    }
  }, [assignmentsWithDetails, filters.sort, filters.student_id, scope, scopedStudentId])

  const total = sortedAssignments.length
  const totalPages = Math.ceil(total / 10)
  const visiblePage = Math.min(page, Math.max(totalPages, 1))
  const pagedAssignments = sortedAssignments.slice((visiblePage - 1) * 10, visiblePage * 10)

  const editAssignment = (assignment: Assignment) => {
    setEditing(assignment)
    setShowForm(true)
    setForm({
      title: assignment.title, description: assignment.description || '',
      due_date: assignment.due_date?.slice(0, 10) || '', status: assignment.status,
      subject_id: assignment.subject_id ? String(assignment.subject_id) : '', category: assignment.category,
      grading_period_id: assignment.grading_period_id ? String(assignment.grading_period_id) : 'none',
      weight: String(assignment.weight), max_score: String(assignment.max_score), recurrence: assignment.recurrence,
      recurrence_end_date: assignment.recurrence_end_date || '', rubric_description: assignment.rubric_description || '',
      attachments: assignment.attachments.join('\n'),
    })
    setTargets(normalizeTargetMap(assignment))
    setAnswerKeyQuestions(assignment.answer_key?.questions || [])
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }

  const calendarEntries = sortedAssignments.flatMap((assignment) => {
    const relevantTargets = assignment.targets.filter((target) =>
      (!scopedStudentId && filters.student_id === 'all' || target.student_id === (scopedStudentId || Number(filters.student_id))) &&
      (!targetStatuses.includes(filters.status as AssignmentTargetStatus) || target.status === filters.status))
    const dates = assignmentDates(assignment,
      scopedStudentId || (filters.student_id === 'all' ? undefined : Number(filters.student_id)),
      targetStatuses.includes(filters.status as AssignmentTargetStatus) ? filters.status as AssignmentTargetStatus : undefined)
    return dates.filter((day) => day >= range.start && day <= range.end).map((day) => ({
      id: `${assignment.id}-${day}`, date: day, title: assignment.title,
      subtitle: `${assignment.subjectName} · ${assignment.status}`,
      details: <>
        <p>{assignment.description || 'No instructions provided.'}</p>
        <p className="text-xs text-muted-foreground">{assignment.category} · Max {assignment.max_score} · Weight {assignment.weight} · {assignment.gradingPeriodName}</p>
        {relevantTargets.map((target) => <p key={`${assignment.id}-${target.student_id}`} className="text-xs">
          {target.student?.name || students.find((student) => student.id === target.student_id)?.name || `Student #${target.student_id}`}
          {' · '}{target.status} · Due {formatDateLabel(target.due_date || assignment.due_date)}
        </p>)}
        {canManageCurriculum ? <div className="flex flex-wrap gap-2">
          <Button size="sm" variant="outline" onClick={() => editAssignment(assignment)}>Edit assignment</Button>
          <Button size="sm" variant="destructive" onClick={() => void api.deleteAssignment(assignment.id).then(load)}>Delete</Button>
        </div> : null}
      </>,
    }))
  })

  if (loading && !hasLoaded) return <LoadingState message="Loading assignments…" />
  if (error) return <ErrorState message={error} onRetry={() => void load()} />

  return (
    <div className="space-y-4">
      {loading ? <p role="status" className="text-sm text-muted-foreground">Refreshing assignments…</p> : null}
      <Card>
        <CardHeader><CardTitle>Assignments</CardTitle></CardHeader>
        <CardContent className="space-y-4">
          <PlanningCalendarToolbar navigation={navigation} />
          {canManageCurriculum ? <div className="flex flex-wrap gap-2">
            <Button onClick={() => { setWeeklyImport(true); setShowBulkImport(true); setShowForm(false) }}>Plan week</Button>
            <Button variant="outline" onClick={() => { resetForm(); setForm({ ...emptyForm(), due_date: date }); setShowForm(true); setShowBulkImport(false) }}>Create assignment</Button>
            <Button variant="outline" onClick={() => { setWeeklyImport(false); setShowBulkImport(true); setShowForm(false) }}><FileText className="mr-2 h-4 w-4" />Import assignments</Button>
          </div> : null}
        </CardContent>
      </Card>
      {canManageCurriculum ? (
        <>
          {showBulkImport ? (
            <BulkAssignmentImportWizard
              subjects={subjects}
              students={students}
              gradingPeriods={gradingPeriods}
              schoolYears={schoolYears}
              planningMode={weeklyImport ? 'weekly' : undefined}
              initialDate={date}
              initialStudentId={scopedStudentId || (filters.student_id === 'all' ? undefined : Number(filters.student_id))}
              initialSchoolYearId={schoolYears.find((year) => year.is_active)?.id}
              onClose={() => setShowBulkImport(false)}
              onImported={() => void load()}
            />
          ) : null}
        </>
      ) : null}

      {canManageCurriculum && showForm ? (
        <Card>
          <CardHeader>
            <CardTitle>{editing ? 'Edit assignment' : 'Create assignment'}</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid gap-4 md:grid-cols-2">
              <div className="space-y-2">
                <Label>Title</Label>
                <Input value={form.title} onChange={(event) => setForm((prev) => ({ ...prev, title: event.target.value }))} />
              </div>
              <div className="space-y-2">
                <Label>Subject</Label>
                <Select value={form.subject_id} onValueChange={(value) => setForm((prev) => ({ ...prev, subject_id: value }))}>
                  <SelectTrigger>
                    <SelectValue placeholder="Select subject" />
                  </SelectTrigger>
                  <SelectContent>
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
                  value={form.due_date}
                  onChange={(event) => setForm((prev) => ({ ...prev, due_date: event.target.value }))}
                />
              </div>
              <div className="space-y-2">
                <Label>Status</Label>
                <Select value={form.status} onValueChange={(value: AssignmentStatus) => setForm((prev) => ({ ...prev, status: value }))}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {assignmentStatuses.map((status) => (
                      <SelectItem key={status} value={status}>
                        {status}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label>Category</Label>
                <Select value={form.category} onValueChange={(value: AssignmentCategory) => setForm((prev) => ({ ...prev, category: value }))}>
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
              </div>
              <div className="space-y-2">
                <Label>Grading period</Label>
                <Select
                  value={form.grading_period_id}
                  onValueChange={(value) => setForm((prev) => ({ ...prev, grading_period_id: value }))}
                >
                  <SelectTrigger>
                    <SelectValue placeholder="Optional grading period" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="none">No grading period</SelectItem>
                    {gradingPeriods.map((gradingPeriod) => (
                      <SelectItem key={gradingPeriod.id} value={String(gradingPeriod.id)}>
                        {gradingPeriod.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label>Weight</Label>
                <Input value={form.weight} type="number" min="0" step="0.1" onChange={(event) => setForm((prev) => ({ ...prev, weight: event.target.value }))} />
              </div>
              <div className="space-y-2">
                <Label>Max score</Label>
                <Input value={form.max_score} type="number" min="1" step="0.5" onChange={(event) => setForm((prev) => ({ ...prev, max_score: event.target.value }))} />
              </div>
              <div className="space-y-2">
                <Label>Recurrence</Label>
                <Select value={form.recurrence} onValueChange={(value: (typeof recurrences)[number]) => setForm((prev) => ({ ...prev, recurrence: value }))}>
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
              </div>
              <div className="space-y-2">
                <Label>Recurrence end</Label>
                <Input
                  type="date"
                  value={form.recurrence_end_date}
                  disabled={form.recurrence === 'none'}
                  onChange={(event) => setForm((prev) => ({ ...prev, recurrence_end_date: event.target.value }))}
                />
              </div>
            </div>
            <div className="space-y-2">
              <Label>Description</Label>
              <Textarea value={form.description} onChange={(event) => setForm((prev) => ({ ...prev, description: event.target.value }))} />
            </div>
            <div className="space-y-2">
              <Label>Rubric description</Label>
              <Textarea
                value={form.rubric_description}
                onChange={(event) => setForm((prev) => ({ ...prev, rubric_description: event.target.value }))}
              />
            </div>
            <div className="space-y-2">
              <Label>Attachments (one path per line)</Label>
              <Textarea value={form.attachments} onChange={(event) => setForm((prev) => ({ ...prev, attachments: event.target.value }))} />
            </div>
            <div className="space-y-3 rounded-lg border p-3">
              <div>
                <p className="font-medium">Assign students</p>
                <p className="text-sm text-muted-foreground">Pick one or more students and optionally customize each due date.</p>
              </div>
              <div className="grid gap-2 md:grid-cols-2">
                {students.map((student) => (
                  <label key={student.id} className="flex items-center gap-2 rounded-md border p-2 text-sm">
                    <input type="checkbox" checked={Boolean(targets[String(student.id)])} onChange={() => toggleStudent(student.id)} />
                    <span>{student.name}</span>
                  </label>
                ))}
              </div>
              {Object.entries(targets).length ? (
                <div className="space-y-2">
                  {Object.entries(targets).map(([studentId, target]) => {
                    const studentName = students.find((student) => String(student.id) === studentId)?.name || `Student #${studentId}`
                    return (
                      <div key={studentId} className="grid gap-3 rounded-md bg-muted/40 p-3 md:grid-cols-[1fr_180px_180px]">
                        <div className="self-center font-medium">{studentName}</div>
                        <Input
                          type="date"
                          value={target.due_date}
                          onChange={(event) =>
                            setTargets((current) => ({
                              ...current,
                              [studentId]: { ...current[studentId], due_date: event.target.value },
                            }))
                          }
                        />
                        <Select
                          value={target.status}
                          onValueChange={(value: AssignmentTargetStatus) =>
                            setTargets((current) => ({
                              ...current,
                              [studentId]: { ...current[studentId], status: value },
                            }))
                          }
                        >
                          <SelectTrigger>
                            <SelectValue />
                          </SelectTrigger>
                          <SelectContent>
                            {targetStatuses.map((status) => (
                              <SelectItem key={status} value={status}>
                                {status}
                              </SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                      </div>
                    )
                  })}
                </div>
              ) : null}
            </div>
            <div className="space-y-3 rounded-lg border p-3">
              <div className="flex items-center justify-between gap-2">
                <div>
                  <p className="font-medium">Answer key</p>
                  <p className="text-sm text-muted-foreground">Add question-by-question scoring rules for semi-automatic grading.</p>
                </div>
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={() => setAnswerKeyQuestions((current) => [...current, emptyAnswerKeyQuestion()])}
                >
                  <Plus className="mr-2 h-3.5 w-3.5" />
                  Add question
                </Button>
              </div>
              {answerKeyQuestions.length ? (
                <div className="space-y-3">
                  {answerKeyQuestions.map((question, index) => (
                    <div key={`${question.question_number}-${index}`} className="grid gap-3 rounded-md bg-muted/40 p-3 md:grid-cols-[120px_1fr_120px]">
                      <Input
                        placeholder="Q#"
                        value={question.question_number}
                        onChange={(event) =>
                          setAnswerKeyQuestions((current) =>
                            current.map((item, itemIndex) =>
                              itemIndex === index ? { ...item, question_number: event.target.value } : item,
                            ),
                          )
                        }
                      />
                      <Input
                        placeholder="Correct answer"
                        value={question.correct_answer}
                        onChange={(event) =>
                          setAnswerKeyQuestions((current) =>
                            current.map((item, itemIndex) =>
                              itemIndex === index ? { ...item, correct_answer: event.target.value } : item,
                            ),
                          )
                        }
                      />
                      <Input
                        type="number"
                        min="0"
                        step="0.5"
                        value={question.points}
                        onChange={(event) =>
                          setAnswerKeyQuestions((current) =>
                            current.map((item, itemIndex) =>
                              itemIndex === index ? { ...item, points: Number(event.target.value || 0) } : item,
                            ),
                          )
                        }
                      />
                      <Textarea
                        className="md:col-span-2"
                        placeholder="Optional partial credit rule (for example: 50% for equivalent fraction)"
                        value={question.partial_credit_rules || ''}
                        onChange={(event) =>
                          setAnswerKeyQuestions((current) =>
                            current.map((item, itemIndex) =>
                              itemIndex === index ? { ...item, partial_credit_rules: event.target.value } : item,
                            ),
                          )
                        }
                      />
                      <div className="flex items-start justify-end">
                        <Button
                          type="button"
                          variant="ghost"
                          size="sm"
                          onClick={() => setAnswerKeyQuestions((current) => current.filter((_, itemIndex) => itemIndex !== index))}
                        >
                          <Trash2 className="mr-2 h-3.5 w-3.5" />
                          Remove
                        </Button>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-sm text-muted-foreground">No answer key yet. Add one to enable confidence-based auto-grading.</p>
              )}
            </div>
            <div className="flex flex-wrap gap-2">
              <Button onClick={() => void save()}>
                <Plus className="mr-2 h-4 w-4" />
                {editing ? 'Update' : 'Create'} assignment
              </Button>
              <Button variant="outline" onClick={resetForm}>Cancel</Button>
            </div>
          </CardContent>
        </Card>
      ) : null}

      <Card>
        <CardHeader>
          <CardTitle>{scope === 'calendar' ? 'Scheduled assignments' : 'Assignment history'}</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <details>
          <summary className="cursor-pointer text-sm font-medium">Search and filters</summary>
          <div className="mt-3 grid gap-4 md:grid-cols-2 xl:grid-cols-4">
            <div className="space-y-2 xl:col-span-2">
              <Label>Search</Label>
              <Input value={filters.q} onChange={(event) => { setFilters((prev) => ({ ...prev, q: event.target.value })); setPage(1) }} placeholder="Assignment title, note, or subject" />
            </div>
            <div className="space-y-2">
              <Label>Category</Label>
              <Select value={filters.category} onValueChange={(value) => { setFilters((prev) => ({ ...prev, category: value })); setPage(1) }}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All categories</SelectItem>
                  {categories.map((category) => (
                    <SelectItem key={category} value={category}>
                      {category}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label>Grading period</Label>
              <Select value={filters.grading_period_id} onValueChange={(value) => { setFilters((prev) => ({ ...prev, grading_period_id: value })); setPage(1) }}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All periods</SelectItem>
                  {gradingPeriods.map((gradingPeriod) => (
                    <SelectItem key={gradingPeriod.id} value={String(gradingPeriod.id)}>
                      {gradingPeriod.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label>Subject</Label>
              <Select value={filters.subject_id} onValueChange={(value) => { setFilters((prev) => ({ ...prev, subject_id: value })); setPage(1) }}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All subjects</SelectItem>
                  {subjects.map((subject) => (
                    <SelectItem key={subject.id} value={String(subject.id)}>
                      {subject.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label>Student</Label>
              <Select disabled={Boolean(scopedStudentId)} value={filters.student_id} onValueChange={(value) => { setFilters((prev) => ({ ...prev, student_id: value })); setPage(1) }}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All students</SelectItem>
                  {students.map((student) => (
                    <SelectItem key={student.id} value={String(student.id)}>
                      {student.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label>Status</Label>
              <Select value={filters.status} onValueChange={(value) => { setFilters((prev) => ({ ...prev, status: value })); setPage(1) }}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All statuses</SelectItem>
                  {assignmentStatuses.map((status) => (
                    <SelectItem key={status} value={status}>
                      Overall: {status}
                    </SelectItem>
                  ))}
                  {targetStatuses.map((status) => (
                    <SelectItem key={status} value={status}>
                      Student: {status}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            {scope === 'all' ? <div className="space-y-2">
              <Label>Due from</Label>
              <Input type="date" value={filters.due_from} onChange={(event) => { setFilters((prev) => ({ ...prev, due_from: event.target.value })); setPage(1) }} />
            </div> : null}
            {scope === 'all' ? <div className="space-y-2">
              <Label>Due to</Label>
              <Input type="date" value={filters.due_to} onChange={(event) => { setFilters((prev) => ({ ...prev, due_to: event.target.value })); setPage(1) }} />
            </div> : null}
            <div className="space-y-2">
              <Label>Sort</Label>
              <Select value={filters.sort} onValueChange={(value) => setFilters((prev) => ({ ...prev, sort: value }))}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="due-asc">Due date ↑</SelectItem>
                  <SelectItem value="due-desc">Due date ↓</SelectItem>
                  <SelectItem value="title">Title</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>
          </details>

          {scope === 'calendar' ? <PlanningCalendar date={date} view={view} entries={calendarEntries} /> : sortedAssignments.length ? (
            <>
              <div className="space-y-2">
                {pagedAssignments.map((assignment) => (
                  <PlanningEntry key={assignment.id} entry={{ id: assignment.id, date: '', title: assignment.title,
                    subtitle: `${assignment.subjectName} · Due ${formatDateLabel(assignment.due_date)} · ${assignment.status}`,
                    details: <div className="rounded-lg p-1">
                    <div className="flex flex-wrap items-start justify-between gap-2">
                      <div>
                        <p className="font-semibold">{assignment.title}</p>
                        <p className="text-xs text-muted-foreground">
                          {assignment.subjectName} • {assignment.gradingPeriodName} • Due {formatDateLabel(assignment.due_date)}
                        </p>
                        <p className="mt-1 text-xs text-muted-foreground">
                          {assignment.category} • Weight {assignment.weight} • Max {assignment.max_score}
                        </p>
                        <p className="mt-1 text-xs text-muted-foreground">
                          {assignment.answer_key?.questions?.length
                            ? `${assignment.answer_key.questions.length} answer key question(s)`
                            : 'No answer key'}
                        </p>
                      </div>
                      <Badge variant="secondary">{assignment.status}</Badge>
                    </div>
                    {assignment.description ? <p className="mt-2 text-sm text-muted-foreground">{assignment.description}</p> : null}
                    {assignment.targets.length ? (
                      <div className="mt-3 space-y-2">
                        <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Per-student status</p>
                        {assignment.targets.map((target) => (
                          <div key={`${assignment.id}-${target.student_id}`} className="flex flex-wrap items-center justify-between gap-2 rounded-md bg-muted/40 p-2 text-sm">
                            <div>
                              <p className="font-medium">{target.student?.name || `Student #${target.student_id}`}</p>
                              <p className="text-xs text-muted-foreground">Due {formatDateLabel(target.due_date)}</p>
                            </div>
                            <Badge variant="secondary">{target.status}</Badge>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <p className="mt-3 text-sm text-muted-foreground">Applies to all students with the overall due date.</p>
                    )}
                    {canManageCurriculum ? (
                      <div className="mt-3 flex flex-wrap gap-2">
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => editAssignment(assignment)}
                        >
                          <Pencil className="mr-2 h-3.5 w-3.5" />
                          Edit
                        </Button>
                        <Button size="sm" variant="destructive" onClick={() => void api.deleteAssignment(assignment.id).then(load)}>
                          <Trash2 className="mr-2 h-3.5 w-3.5" />
                          Delete
                        </Button>
                      </div>
                    ) : null}
                  </div> }} />
                ))}
              </div>
              <div className="flex items-center justify-between">
                <p className="text-sm text-muted-foreground">
                  {total} assignments • Page {visiblePage} of {Math.max(totalPages, 1)}
                </p>
                <div className="space-x-2">
                  <Button variant="outline" disabled={visiblePage <= 1} onClick={() => setPage(visiblePage - 1)}>
                    Previous
                  </Button>
                  <Button variant="outline" disabled={visiblePage >= totalPages} onClick={() => setPage(visiblePage + 1)}>
                    Next
                  </Button>
                </div>
              </div>
            </>
          ) : (
            <EmptyState title="No assignments yet" description="Create an assignment to begin collecting student work." />
          )}
        </CardContent>
      </Card>
    </div>
  )
}
