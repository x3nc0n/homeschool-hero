import { useCallback, useEffect, useMemo, useState } from 'react'
import { Pencil, Plus, Trash2 } from 'lucide-react'
import { useSearchParams } from 'react-router-dom'
import { api } from '@/lib/api'
import type {
  Assignment,
  AssignmentCategory,
  AssignmentStatus,
  AssignmentTargetStatus,
  GradingPeriod,
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

const assignmentStatuses: AssignmentStatus[] = ['pending', 'complete', 'graded']
const targetStatuses: AssignmentTargetStatus[] = ['assigned', 'submitted', 'graded', 'excused']
const categories: AssignmentCategory[] = ['homework', 'quiz', 'test', 'project', 'other']
const recurrences = ['none', 'daily', 'weekly'] as const

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
  return value ? new Date(value).toLocaleDateString() : 'TBD'
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
  const { canManageCurriculum } = useAuth()
  const [assignments, setAssignments] = useState<Assignment[]>([])
  const [subjects, setSubjects] = useState<Subject[]>([])
  const [students, setStudents] = useState<Student[]>([])
  const [gradingPeriods, setGradingPeriods] = useState<GradingPeriod[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [editing, setEditing] = useState<Assignment | null>(null)
  const [page, setPage] = useState(1)
  const [totalPages, setTotalPages] = useState(0)
  const [total, setTotal] = useState(0)
  const [form, setForm] = useState<AssignmentForm>(emptyForm())
  const [targets, setTargets] = useState<Record<string, TargetDraft>>({})
  const [filters, setFilters] = useState({
    q: searchParams.get('q') || searchParams.get('search') || '',
    category: 'all',
    grading_period_id: 'all',
    subject_id: searchParams.get('subject_id') || 'all',
    student_id: 'all',
    status: 'all',
    due_from: '',
    due_to: '',
    sort: 'due-asc',
  })

  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const schoolYears = await api.listSchoolYears()
      const schoolYearDetails = await Promise.all(schoolYears.map((year) => api.getSchoolYear(year.id)))
      const allGradingPeriods = schoolYearDetails.flatMap((year) =>
        year.terms.flatMap((term) => term.grading_periods),
      )
      const [assignmentData, subjectData, studentData] = await Promise.all([
        api.listAssignments({
          q: filters.q || undefined,
          category: filters.category as AssignmentCategory | 'all',
          grading_period_id: filters.grading_period_id === 'all' ? undefined : Number(filters.grading_period_id),
          subject_id: filters.subject_id === 'all' ? undefined : Number(filters.subject_id),
          student_id: filters.student_id === 'all' ? undefined : Number(filters.student_id),
          status: filters.status as AssignmentStatus | AssignmentTargetStatus | 'all',
          due_from: filters.due_from || undefined,
          due_to: filters.due_to || undefined,
          page,
          page_size: 10,
        }),
        api.listSubjects(),
        api.listStudents(),
      ])
      setAssignments(assignmentData.items)
      setTotal(assignmentData.total)
      setTotalPages(assignmentData.total_pages)
      setSubjects(subjectData)
      setStudents(studentData)
      setGradingPeriods(allGradingPeriods)
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : 'Unable to load assignments')
    } finally {
      setLoading(false)
    }
  }, [filters, page])

  useEffect(() => {
    void load()
  }, [load])

  useEffect(() => {
    const params = new URLSearchParams()
    Object.entries(filters).forEach(([key, value]) => {
      if (!value || value === 'all') return
      params.set(key === 'q' ? 'search' : key, value)
    })
    params.set('page', String(page))
    setSearchParams(params, { replace: true })
  }, [filters, page, setSearchParams])

  const resetForm = () => {
    setEditing(null)
    setForm(emptyForm())
    setTargets({})
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

    if (editing) {
      await api.updateAssignment(editing.id, payload)
    } else {
      await api.createAssignment(payload)
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
    const items = [...assignmentsWithDetails]
    switch (filters.sort) {
      case 'due-desc':
        return items.sort(
          (a, b) =>
            new Date(b.due_date || 0).getTime() - new Date(a.due_date || 0).getTime(),
        )
      case 'title':
        return items.sort((a, b) => a.title.localeCompare(b.title))
      default:
        return items.sort(
          (a, b) =>
            new Date(a.due_date || '9999-12-31').getTime() - new Date(b.due_date || '9999-12-31').getTime(),
        )
    }
  }, [assignmentsWithDetails, filters.sort])

  if (loading) return <LoadingState message="Loading assignments…" />
  if (error) return <ErrorState message={error} onRetry={() => void load()} />

  return (
    <div className="space-y-4">
      {canManageCurriculum ? (
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
            <div className="flex flex-wrap gap-2">
              <Button onClick={() => void save()}>
                <Plus className="mr-2 h-4 w-4" />
                {editing ? 'Update' : 'Create'} assignment
              </Button>
              {editing ? (
                <Button variant="outline" onClick={resetForm}>
                  Cancel edit
                </Button>
              ) : null}
            </div>
          </CardContent>
        </Card>
      ) : null}

      <Card>
        <CardHeader>
          <CardTitle>Assignment list</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-8">
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
              <Select value={filters.student_id} onValueChange={(value) => { setFilters((prev) => ({ ...prev, student_id: value })); setPage(1) }}>
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
            <div className="space-y-2">
              <Label>Due from</Label>
              <Input type="date" value={filters.due_from} onChange={(event) => { setFilters((prev) => ({ ...prev, due_from: event.target.value })); setPage(1) }} />
            </div>
            <div className="space-y-2">
              <Label>Due to</Label>
              <Input type="date" value={filters.due_to} onChange={(event) => { setFilters((prev) => ({ ...prev, due_to: event.target.value })); setPage(1) }} />
            </div>
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

          {sortedAssignments.length ? (
            <>
              <div className="space-y-2">
                {sortedAssignments.map((assignment) => (
                  <div key={assignment.id} className="rounded-lg border p-3">
                    <div className="flex flex-wrap items-start justify-between gap-2">
                      <div>
                        <p className="font-semibold">{assignment.title}</p>
                        <p className="text-xs text-muted-foreground">
                          {assignment.subjectName} • {assignment.gradingPeriodName} • Due {formatDateLabel(assignment.due_date)}
                        </p>
                        <p className="mt-1 text-xs text-muted-foreground">
                          {assignment.category} • Weight {assignment.weight} • Max {assignment.max_score}
                        </p>
                      </div>
                      <Badge variant="secondary">{assignment.status}</Badge>
                    </div>
                    {assignment.description ? <p className="mt-2 text-sm text-muted-foreground">{assignment.description}</p> : null}
                    {assignment.targets.length ? (
                      <div className="mt-3 space-y-2">
                        <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Per-student status</p>
                        {assignment.targets.map((target) => (
                          <div key={target.id} className="flex flex-wrap items-center justify-between gap-2 rounded-md bg-muted/40 p-2 text-sm">
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
                          onClick={() => {
                            setEditing(assignment)
                            setForm({
                              title: assignment.title,
                              description: assignment.description || '',
                              due_date: assignment.due_date?.slice(0, 10) || '',
                              status: assignment.status,
                              subject_id: assignment.subject_id ? String(assignment.subject_id) : '',
                              category: assignment.category,
                              grading_period_id: assignment.grading_period_id ? String(assignment.grading_period_id) : 'none',
                              weight: String(assignment.weight),
                              max_score: String(assignment.max_score),
                              recurrence: assignment.recurrence,
                              recurrence_end_date: assignment.recurrence_end_date || '',
                              rubric_description: assignment.rubric_description || '',
                              attachments: assignment.attachments.join('\n'),
                            })
                            setTargets(normalizeTargetMap(assignment))
                          }}
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
                  </div>
                ))}
              </div>
              <div className="flex items-center justify-between">
                <p className="text-sm text-muted-foreground">
                  {total} assignments • Page {page} of {Math.max(totalPages, 1)}
                </p>
                <div className="space-x-2">
                  <Button variant="outline" disabled={page <= 1} onClick={() => setPage((current) => Math.max(current - 1, 1))}>
                    Previous
                  </Button>
                  <Button variant="outline" disabled={totalPages > 0 ? page >= totalPages : true} onClick={() => setPage((current) => current + 1)}>
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
