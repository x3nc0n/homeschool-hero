import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { CalendarRange, Pencil, Trash2 } from 'lucide-react'
import { useSearchParams } from 'react-router-dom'
import { api } from '@/lib/api'
import type {
  CurriculumPackageDetail,
  LessonPlan,
  LessonPlanStatus,
  PacingStatusItem,
  PacingTarget,
  SchoolYear,
  Student,
  Subject,
} from '@/types/api'
import { useAuth } from '@/context/AuthContext'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { EmptyState } from '@/components/common/EmptyState'
import { ErrorState } from '@/components/common/ErrorState'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { LoadingState } from '@/components/common/LoadingState'
import { Textarea } from '@/components/ui/textarea'
import { BulkAssignmentImportWizard } from '@/components/features/BulkAssignmentImportWizard'
import { PlanningCalendar, PlanningCalendarToolbar, PlanningEntry, usePlanningCalendar } from '@/components/features/PlanningCalendar'
import { addSchoolDays, schoolDate, schoolDateLabel } from '@/lib/planning-calendar'

const selectClassName = 'h-10 w-full rounded-md border border-input bg-background px-3 text-sm'
const lessonStatuses: LessonPlanStatus[] = ['planned', 'in_progress', 'completed', 'skipped', 'rescheduled']

type LessonPlanForm = {
  package_id: string
  curriculum_lesson_id: string
  target_date: string
  estimated_duration_minutes: string
  status: LessonPlanStatus
  notes: string
}

type GenerateForm = {
  package_id: string
  start_date: string
  default_duration_minutes: string
  overwrite_existing: boolean
}

type PacingForm = {
  curriculum_unit_id: string
  target_start_date: string
  target_end_date: string
}

function toInputDate(value = new Date()) {
  return schoolDate(value)
}

function emptyLessonPlanForm(date = toInputDate()): LessonPlanForm {
  return {
    package_id: '',
    curriculum_lesson_id: '',
    target_date: date,
    estimated_duration_minutes: '',
    status: 'planned',
    notes: '',
  }
}

function emptyGenerateForm(date = toInputDate()): GenerateForm {
  return {
    package_id: '',
    start_date: date,
    default_duration_minutes: '',
    overwrite_existing: false,
  }
}

function emptyPacingForm(date = toInputDate()): PacingForm {
  return {
    curriculum_unit_id: '',
    target_start_date: date,
    target_end_date: date,
  }
}

function formatDateLabel(value?: string | null) {
  return value ? schoolDateLabel(value) : 'TBD'
}

function statusVariant(status: string): 'default' | 'secondary' | 'outline' | 'destructive' {
  if (status === 'completed' || status === 'ahead') return 'secondary'
  if (status === 'skipped' || status === 'behind') return 'destructive'
  if (status === 'rescheduled') return 'outline'
  return 'default'
}

export function LessonPlansPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const navigation = usePlanningCalendar()
  const { date, view, scope, range, page: historyPage, setPage: setHistoryPage } = navigation
  const planningSequence = useRef(0)
  const { canManageCurriculum, studentId: scopedStudentId } = useAuth()
  const [students, setStudents] = useState<Student[]>([])
  const [subjects, setSubjects] = useState<Subject[]>([])
  const [schoolYears, setSchoolYears] = useState<SchoolYear[]>([])
  const [packages, setPackages] = useState<CurriculumPackageDetail[]>([])
  const [lessonPlans, setLessonPlans] = useState<LessonPlan[]>([])
  const [pacingTargets, setPacingTargets] = useState<PacingTarget[]>([])
  const [pacingItems, setPacingItems] = useState<PacingStatusItem[]>([])
  const [selectedStudentId, setSelectedStudentId] = useState(scopedStudentId ? String(scopedStudentId) : searchParams.get('student_id') || '')
  const [selectedSchoolYearId, setSelectedSchoolYearId] = useState(searchParams.get('school_year_id') || '')
  const [selectedSubjectId, setSelectedSubjectId] = useState(searchParams.get('subject_id') || 'all')
  const [query, setQuery] = useState(searchParams.get('search') || searchParams.get('q') || '')
  const [status, setStatus] = useState(searchParams.get('status') || 'all')
  const [tool, setTool] = useState<'lesson' | 'generate' | 'pacing' | null>(null)
  const [showWeeklyImport, setShowWeeklyImport] = useState(false)
  const [loading, setLoading] = useState(true)
  const [sectionLoading, setSectionLoading] = useState(false)
  const [error, setError] = useState('')
  const [actionError, setActionError] = useState('')
  const [successMessage, setSuccessMessage] = useState('')
  const [editingLessonPlanId, setEditingLessonPlanId] = useState<number | null>(null)
  const [editingPacingTargetId, setEditingPacingTargetId] = useState<number | null>(null)
  const [selectedLessonPlanIds, setSelectedLessonPlanIds] = useState<number[]>([])
  const [lessonPlanForm, setLessonPlanForm] = useState<LessonPlanForm>(emptyLessonPlanForm())
  const [generateForm, setGenerateForm] = useState<GenerateForm>(emptyGenerateForm())
  const [pacingForm, setPacingForm] = useState<PacingForm>(emptyPacingForm())
  const [bulkRescheduleDate, setBulkRescheduleDate] = useState(toInputDate())

  const filteredPackages = useMemo(
    () =>
      packages.filter(
        (pkg) =>
          (!selectedSchoolYearId || selectedSchoolYearId === 'all' || pkg.school_year_id === Number(selectedSchoolYearId)) &&
          (selectedSubjectId === 'all' || pkg.subject_id === Number(selectedSubjectId)),
      ),
    [packages, selectedSchoolYearId, selectedSubjectId],
  )

  const lessonOptions = useMemo(() => {
    const packageFilterId = Number(lessonPlanForm.package_id || 0)
    return filteredPackages
      .filter((pkg) => !packageFilterId || pkg.id === packageFilterId)
      .flatMap((pkg) =>
        pkg.units.flatMap((unit) =>
          unit.lessons.map((lesson) => ({
            id: lesson.id,
            label: `${pkg.name} · ${unit.name} · ${lesson.name}`,
            duration: lesson.estimated_duration_minutes,
            package_id: pkg.id,
          })),
        ),
      )
  }, [filteredPackages, lessonPlanForm.package_id])

  const unitOptions = useMemo(
    () =>
      filteredPackages.flatMap((pkg) =>
        pkg.units.map((unit) => ({
          id: unit.id,
          label: `${pkg.name} · ${unit.name}`,
        })),
      ),
    [filteredPackages],
  )

  useEffect(() => {
    setSearchParams((current) => {
      const next = new URLSearchParams(current)
      if (!next.has('scope')) next.set('scope', scope)
      const values = { student_id: selectedStudentId, school_year_id: selectedSchoolYearId, subject_id: selectedSubjectId, search: query, status }
      Object.entries(values).forEach(([key, value]) => {
        if (value && (value !== 'all' || key === 'school_year_id')) next.set(key, value)
        else next.delete(key)
      })
      return next
    }, { replace: true })
  }, [selectedStudentId, selectedSchoolYearId, selectedSubjectId, query, status, scope, setSearchParams])

  const loadReferenceData = useCallback(async () => {
    const [studentData, subjectData, schoolYearData] = await Promise.all([
      api.listStudents(),
      api.listSubjects(),
      api.listSchoolYears(),
    ])
    const packageGroups = await Promise.all(schoolYearData.map((schoolYear) => api.listCurriculumPackages(schoolYear.id)))
    const packageData = packageGroups.flat()

    setStudents(studentData)
    setSubjects(subjectData)
    setSchoolYears(schoolYearData)
    setPackages(packageData)

    const defaultStudentId =
      (scopedStudentId && studentData.some((student) => student.id === scopedStudentId) && String(scopedStudentId)) ||
      (studentData[0] ? String(studentData[0].id) : '')
    const defaultSchoolYearId =
      String(schoolYearData.find((schoolYear) => schoolYear.is_active)?.id ?? schoolYearData[0]?.id ?? '')

    setSelectedStudentId((current) => scopedStudentId ? String(scopedStudentId) : current || defaultStudentId)
    setSelectedSchoolYearId((current) => current || defaultSchoolYearId)
    setGenerateForm((current) => ({
      ...current,
      package_id: current.package_id || (packageData[0] ? String(packageData[0].id) : ''),
    }))
  }, [scopedStudentId])

  const loadLessonPlanningData = useCallback(async () => {
    const sequence = ++planningSequence.current
    if (!selectedStudentId) {
      setLessonPlans([])
      setPacingTargets([])
      setPacingItems([])
      return
    }

    const subjectId = selectedSubjectId === 'all' ? undefined : Number(selectedSubjectId)
    const [lessonPlanData, pacingTargetData, pacingData] = await Promise.all([
      api.listLessonPlans({
        student_id: Number(selectedStudentId),
        school_year_id: selectedSchoolYearId && selectedSchoolYearId !== 'all' ? Number(selectedSchoolYearId) : undefined,
        subject_id: subjectId,
        status: status as LessonPlanStatus | 'all',
        start_date: scope === 'calendar' ? range.start : undefined,
        end_date: scope === 'calendar' ? range.end : scope === 'overdue' ? addSchoolDays(schoolDate(), -1) : undefined,
      }),
      api.listPacingTargets({ student_id: Number(selectedStudentId), subject_id: subjectId }),
      api.getPacingStatus(Number(selectedStudentId), subjectId),
    ])

    if (sequence !== planningSequence.current) return
    setLessonPlans(lessonPlanData)
    setPacingTargets(pacingTargetData)
    setPacingItems(pacingData.items)
    setSelectedLessonPlanIds((current) => current.filter((id) => lessonPlanData.some((lessonPlan) => lessonPlan.id === id)))
  }, [selectedSchoolYearId, selectedStudentId, selectedSubjectId, status, scope, range.start, range.end])

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError('')
    void loadReferenceData()
      .catch((loadError) => {
        if (!cancelled) {
          setError(loadError instanceof Error ? loadError.message : 'Unable to load lesson planning data')
        }
      })
      .finally(() => {
        if (!cancelled) {
          setLoading(false)
        }
      })
    return () => {
      cancelled = true
    }
  }, [loadReferenceData])

  useEffect(() => {
    if (!selectedStudentId) return
    let cancelled = false
    setSectionLoading(true)
    setError('')
    void loadLessonPlanningData()
      .catch((loadError) => {
        if (!cancelled) {
          setError(loadError instanceof Error ? loadError.message : 'Unable to load lesson plans')
        }
      })
      .finally(() => {
        if (!cancelled) {
          setSectionLoading(false)
        }
      })
    return () => {
      cancelled = true
    }
  }, [loadLessonPlanningData, selectedStudentId])

  const resetLessonPlanForm = () => {
    setEditingLessonPlanId(null)
    setLessonPlanForm(emptyLessonPlanForm())
    setTool(null)
  }

  const resetPacingForm = () => {
    setEditingPacingTargetId(null)
    setPacingForm(emptyPacingForm())
    setTool(null)
  }

  const handleActionError = (actionFailure: unknown, fallback: string) => {
    setActionError(actionFailure instanceof Error ? actionFailure.message : fallback)
    setSuccessMessage('')
  }

  const refreshPage = async () => {
    setSectionLoading(true)
    try {
      await loadLessonPlanningData()
    } finally {
      setSectionLoading(false)
    }
  }

  const toggleSelection = (lessonPlanId: number) => {
    setSelectedLessonPlanIds((current) =>
      current.includes(lessonPlanId) ? current.filter((id) => id !== lessonPlanId) : [...current, lessonPlanId],
    )
  }

  const handleSaveLessonPlan = async () => {
    if (!selectedStudentId || !selectedSchoolYearId || !lessonPlanForm.curriculum_lesson_id || !lessonPlanForm.target_date) return
    setActionError('')
    const schoolYearId = selectedSchoolYearId === 'all'
      ? packages.find((pkg) => pkg.id === Number(lessonPlanForm.package_id))?.school_year_id
      : Number(selectedSchoolYearId)
    if (!schoolYearId) {
      setActionError('Choose a curriculum package and school year before saving.')
      return
    }
    try {
      const payload = {
        curriculum_lesson_id: Number(lessonPlanForm.curriculum_lesson_id),
        student_id: Number(selectedStudentId),
        school_year_id: schoolYearId,
        target_date: lessonPlanForm.target_date,
        estimated_duration_minutes: lessonPlanForm.estimated_duration_minutes
          ? Number(lessonPlanForm.estimated_duration_minutes)
          : undefined,
        status: lessonPlanForm.status,
        notes: lessonPlanForm.notes || undefined,
      }
      if (editingLessonPlanId) {
        await api.updateLessonPlan(editingLessonPlanId, payload)
        setSuccessMessage('Lesson plan updated.')
      } else {
        await api.createLessonPlan(payload)
        setSuccessMessage('Lesson plan created.')
      }
      resetLessonPlanForm()
      await refreshPage()
    } catch (actionFailure) {
      handleActionError(actionFailure, 'Unable to save lesson plan')
    }
  }

  const handleGenerateLessonPlans = async () => {
    if (!selectedStudentId || !generateForm.package_id) return
    setActionError('')
    try {
      await api.generateLessonPlans({
        package_id: Number(generateForm.package_id),
        student_id: Number(selectedStudentId),
        school_year_id: selectedSchoolYearId && selectedSchoolYearId !== 'all' ? Number(selectedSchoolYearId) : undefined,
        start_date: generateForm.start_date || undefined,
        default_duration_minutes: generateForm.default_duration_minutes ? Number(generateForm.default_duration_minutes) : undefined,
        overwrite_existing: generateForm.overwrite_existing,
      })
      setSuccessMessage('Lesson plans generated from curriculum package.')
      await refreshPage()
    } catch (actionFailure) {
      handleActionError(actionFailure, 'Unable to generate lesson plans')
    }
  }

  const handleBulkStatusUpdate = async (statusValue: LessonPlanStatus) => {
    if (!selectedLessonPlanIds.length) return
    setActionError('')
    try {
      await api.bulkUpdateLessonPlans({
        lesson_plan_ids: selectedLessonPlanIds,
        status: statusValue,
        target_date: statusValue === 'rescheduled' ? bulkRescheduleDate : undefined,
      })
      setSelectedLessonPlanIds([])
      setSuccessMessage(statusValue === 'rescheduled' ? 'Lesson plans rescheduled.' : 'Lesson plans updated.')
      await refreshPage()
    } catch (actionFailure) {
      handleActionError(actionFailure, 'Unable to update lesson plans')
    }
  }

  const handleSingleStatusUpdate = async (lessonPlanId: number, statusValue: LessonPlanStatus) => {
    setActionError('')
    try {
      await api.bulkUpdateLessonPlans({ lesson_plan_ids: [lessonPlanId], status: statusValue })
      setSuccessMessage('Lesson plan updated.')
      await refreshPage()
    } catch (actionFailure) {
      handleActionError(actionFailure, 'Unable to update lesson plan')
    }
  }

  const handleGenerateAssignments = async (lessonPlanIds: number[]) => {
    if (!lessonPlanIds.length) return
    setActionError('')
    try {
      await api.generateAssignmentsFromLessonPlans({ lesson_plan_ids: lessonPlanIds })
      setSuccessMessage('Assignments generated from lesson plans.')
      await refreshPage()
    } catch (actionFailure) {
      handleActionError(actionFailure, 'Unable to generate assignments')
    }
  }

  const handleDeleteLessonPlan = async (lessonPlanId: number) => {
    setActionError('')
    try {
      await api.deleteLessonPlan(lessonPlanId)
      if (editingLessonPlanId === lessonPlanId) {
        resetLessonPlanForm()
      }
      setSuccessMessage('Lesson plan deleted.')
      await refreshPage()
    } catch (actionFailure) {
      handleActionError(actionFailure, 'Unable to delete lesson plan')
    }
  }

  const handleSavePacingTarget = async () => {
    if (!selectedStudentId || !pacingForm.curriculum_unit_id || !pacingForm.target_start_date || !pacingForm.target_end_date) return
    setActionError('')
    try {
      const payload = {
        curriculum_unit_id: Number(pacingForm.curriculum_unit_id),
        student_id: Number(selectedStudentId),
        target_start_date: pacingForm.target_start_date,
        target_end_date: pacingForm.target_end_date,
      }
      if (editingPacingTargetId) {
        await api.updatePacingTarget(editingPacingTargetId, payload)
        setSuccessMessage('Pacing target updated.')
      } else {
        await api.createPacingTarget(payload)
        setSuccessMessage('Pacing target created.')
      }
      resetPacingForm()
      await refreshPage()
    } catch (actionFailure) {
      handleActionError(actionFailure, 'Unable to save pacing target')
    }
  }

  const handleDeletePacingTarget = async (pacingTargetId: number) => {
    setActionError('')
    try {
      await api.deletePacingTarget(pacingTargetId)
      if (editingPacingTargetId === pacingTargetId) {
        resetPacingForm()
      }
      setSuccessMessage('Pacing target deleted.')
      await refreshPage()
    } catch (actionFailure) {
      handleActionError(actionFailure, 'Unable to delete pacing target')
    }
  }

  const loadLessonPlanForEdit = (lessonPlan: LessonPlan) => {
    setTool('lesson')
    setShowWeeklyImport(false)
    setEditingLessonPlanId(lessonPlan.id)
    setLessonPlanForm({
      package_id: String(lessonPlan.curriculum_lesson.unit.package.id),
      curriculum_lesson_id: String(lessonPlan.curriculum_lesson_id),
      target_date: lessonPlan.target_date,
      estimated_duration_minutes: lessonPlan.estimated_duration_minutes ? String(lessonPlan.estimated_duration_minutes) : '',
      status: lessonPlan.status,
      notes: lessonPlan.notes || '',
    })
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }

  const loadPacingTargetForEdit = (pacingTarget: PacingTarget) => {
    setTool('pacing')
    setShowWeeklyImport(false)
    setEditingPacingTargetId(pacingTarget.id)
    setPacingForm({
      curriculum_unit_id: String(pacingTarget.curriculum_unit_id),
      target_start_date: pacingTarget.target_start_date,
      target_end_date: pacingTarget.target_end_date,
    })
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }

  const visibleLessons = useMemo(() => lessonPlans.filter((lesson) => {
    if (scope === 'undated' && lesson.target_date) return false
    if (scope === 'overdue' && (['completed', 'skipped'].includes(lesson.status) || !lesson.target_date || lesson.target_date >= schoolDate())) return false
    const text = `${lesson.curriculum_lesson.name} ${lesson.curriculum_lesson.unit.name} ${lesson.curriculum_lesson.unit.package.name} ${lesson.notes || ''}`
    return !query || text.toLocaleLowerCase().includes(query.toLocaleLowerCase())
  }).sort((a, b) => a.target_date.localeCompare(b.target_date) || a.curriculum_lesson.name.localeCompare(b.curriculum_lesson.name) || a.id - b.id),
  [lessonPlans, query, scope])
  const historyPages = Math.max(1, Math.ceil(visibleLessons.length / 10))
  const visibleHistoryPage = Math.min(historyPage, historyPages)
  const lessonEntry = (lesson: LessonPlan) => ({
    id: lesson.id, date: lesson.target_date, title: lesson.curriculum_lesson.name,
    subtitle: `${lesson.curriculum_lesson.unit.package.name} · ${lesson.status}`,
    details: <>
      <p className="text-xs text-muted-foreground">{lesson.curriculum_lesson.unit.name} · {formatDateLabel(lesson.target_date)}</p>
      <p className="text-xs text-muted-foreground">{lesson.estimated_duration_minutes || lesson.curriculum_lesson.estimated_duration_minutes || 0} minutes · {lesson.curriculum_lesson.resources.length} resources · {lesson.assignment_ids.length ? 'assignment ready' : 'no assignment yet'}</p>
      {lesson.notes ? <p className="text-sm">{lesson.notes}</p> : null}
      {canManageCurriculum ? <div className="flex flex-wrap items-center gap-2">
        <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={selectedLessonPlanIds.includes(lesson.id)} onChange={() => toggleSelection(lesson.id)} />Select lesson</label>
        <Button variant="secondary" size="sm" onClick={() => void handleSingleStatusUpdate(lesson.id, 'completed')}>Complete</Button>
        <Button variant="outline" size="sm" onClick={() => void handleSingleStatusUpdate(lesson.id, 'skipped')}>Skip</Button>
        <Button variant="outline" size="sm" onClick={() => void handleGenerateAssignments([lesson.id])}>Generate assignment</Button>
        <Button variant="outline" size="sm" onClick={() => loadLessonPlanForEdit(lesson)}><Pencil className="mr-1 h-3.5 w-3.5" />Edit</Button>
        <Button variant="outline" size="sm" onClick={() => void handleDeleteLessonPlan(lesson.id)}><Trash2 className="mr-1 h-3.5 w-3.5" />Delete</Button>
      </div> : null}
    </>,
  })

  if (loading) return <LoadingState message="Loading lesson plans…" />
  if (error) return <ErrorState message={error} onRetry={() => void loadReferenceData()} />

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <CardTitle>Lesson plans and pacing guides</CardTitle>
          <CardDescription>Build lesson sequences by student, monitor pace, and turn plans into assignments.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <PlanningCalendarToolbar navigation={navigation} />
          {canManageCurriculum ? <div className="flex flex-wrap gap-2">
            <Button onClick={() => { setShowWeeklyImport(true); setTool(null) }}>Plan week</Button>
            <Button variant="outline" onClick={() => { setTool('lesson'); setEditingLessonPlanId(null); setLessonPlanForm(emptyLessonPlanForm(date)); setShowWeeklyImport(false) }}>Add lesson plan</Button>
            <Button variant="outline" onClick={() => { setTool('generate'); setGenerateForm((current) => ({ ...current, start_date: date })); setShowWeeklyImport(false) }}>Generate from curriculum</Button>
            <Button variant="outline" onClick={() => { setTool('pacing'); setShowWeeklyImport(false) }}>Add pacing target</Button>
            {tool ? <Button variant="ghost" onClick={() => setTool(null)}>Close form</Button> : null}
          </div> : null}
          <div className="grid gap-4 md:grid-cols-3">
          <div className="space-y-2">
            <Label>Student</Label>
            <select aria-label="Student" disabled={Boolean(scopedStudentId)} className={selectClassName} value={selectedStudentId} onChange={(event) => { setSelectedStudentId(event.target.value); setHistoryPage(1) }}>
              {students.map((student) => (
                <option key={student.id} value={student.id}>
                  {student.name}
                </option>
              ))}
            </select>
          </div>
          <div className="space-y-2">
            <Label>School year</Label>
            <select aria-label="School year" className={selectClassName} value={selectedSchoolYearId} onChange={(event) => { setSelectedSchoolYearId(event.target.value); setHistoryPage(1) }}>
              <option value="all">All school years</option>
              {schoolYears.map((schoolYear) => (
                <option key={schoolYear.id} value={schoolYear.id}>
                  {schoolYear.name}
                </option>
              ))}
            </select>
          </div>
          <div className="space-y-2">
            <Label>Subject</Label>
            <select aria-label="Subject" className={selectClassName} value={selectedSubjectId} onChange={(event) => { setSelectedSubjectId(event.target.value); setHistoryPage(1) }}>
              <option value="all">All subjects</option>
              {subjects.map((subject) => (
                <option key={subject.id} value={subject.id}>
                  {subject.name}
                </option>
              ))}
            </select>
          </div>
          </div>
          <details>
            <summary className="cursor-pointer text-sm font-medium">Search and advanced filters</summary>
            <div className="mt-3 grid gap-3 md:grid-cols-2">
              <label htmlFor="lesson-search" className="space-y-2 text-sm">Search<Input id="lesson-search" value={query} onChange={(event) => { setQuery(event.target.value); setHistoryPage(1) }} placeholder="Lesson, unit, curriculum, or notes" /></label>
              <label className="space-y-2 text-sm">Status<select className={selectClassName} value={status} onChange={(event) => { setStatus(event.target.value); setHistoryPage(1) }}>
                <option value="all">All statuses</option>
                {lessonStatuses.map((value) => <option key={value} value={value}>{value}</option>)}
              </select></label>
            </div>
          </details>
        </CardContent>
      </Card>
      {canManageCurriculum && showWeeklyImport ? <BulkAssignmentImportWizard
        planningMode="weekly" initialDate={date} initialStudentId={selectedStudentId ? Number(selectedStudentId) : undefined}
        initialSchoolYearId={selectedSchoolYearId && selectedSchoolYearId !== 'all' ? Number(selectedSchoolYearId) : undefined}
        subjects={subjects} students={students} schoolYears={schoolYears} gradingPeriods={[]}
        onClose={() => setShowWeeklyImport(false)} onImported={() => void refreshPage()} /> : null}

      {(successMessage || actionError) && (
        <Card>
          <CardContent className="pt-6">
            {successMessage ? <p className="text-sm text-emerald-700">{successMessage}</p> : null}
            {actionError ? <p className="text-sm text-destructive">{actionError}</p> : null}
          </CardContent>
        </Card>
      )}

      {canManageCurriculum && tool ? (
        <div>
          {tool === 'generate' ? <Card>
            <CardHeader>
              <CardTitle>Generate from curriculum</CardTitle>
              <CardDescription>Auto-place lessons on scheduled instructional days.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="space-y-2">
                <Label>Curriculum package</Label>
                <select
                  className={selectClassName}
                  value={generateForm.package_id}
                  onChange={(event) => setGenerateForm((current) => ({ ...current, package_id: event.target.value }))}
                >
                  <option value="">Select a package</option>
                  {filteredPackages.map((pkg) => (
                    <option key={pkg.id} value={pkg.id}>
                      {pkg.name}
                    </option>
                  ))}
                </select>
              </div>
              <div className="grid gap-3 md:grid-cols-2">
                <div className="space-y-2">
                  <Label>Start date</Label>
                  <Input
                    type="date"
                    value={generateForm.start_date}
                    onChange={(event) => setGenerateForm((current) => ({ ...current, start_date: event.target.value }))}
                  />
                </div>
                <div className="space-y-2">
                  <Label>Default duration</Label>
                  <Input
                    type="number"
                    min="1"
                    value={generateForm.default_duration_minutes}
                    onChange={(event) =>
                      setGenerateForm((current) => ({ ...current, default_duration_minutes: event.target.value }))
                    }
                  />
                </div>
              </div>
              <label className="flex items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  checked={generateForm.overwrite_existing}
                  onChange={(event) =>
                    setGenerateForm((current) => ({ ...current, overwrite_existing: event.target.checked }))
                  }
                />
                Replace existing lesson plans for this package
              </label>
              <Button className="w-full" onClick={() => void handleGenerateLessonPlans()}>
                <CalendarRange className="mr-2 h-4 w-4" />
                Generate lesson plans
              </Button>
            </CardContent>
          </Card> : null}

          {tool === 'lesson' ? <Card>
            <CardHeader>
              <CardTitle>{editingLessonPlanId ? 'Edit lesson plan' : 'Add lesson plan'}</CardTitle>
              <CardDescription>Manually schedule or adjust a single curriculum lesson.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="space-y-2">
                <Label>Package</Label>
                <select
                  className={selectClassName}
                  value={lessonPlanForm.package_id}
                  onChange={(event) =>
                    setLessonPlanForm((current) => ({
                      ...current,
                      package_id: event.target.value,
                      curriculum_lesson_id: '',
                    }))
                  }
                >
                  <option value="">Select a package</option>
                  {filteredPackages.map((pkg) => (
                    <option key={pkg.id} value={pkg.id}>
                      {pkg.name}
                    </option>
                  ))}
                </select>
              </div>
              <div className="space-y-2">
                <Label>Lesson</Label>
                <select
                  className={selectClassName}
                  value={lessonPlanForm.curriculum_lesson_id}
                  onChange={(event) => {
                    const selected = lessonOptions.find((lesson) => String(lesson.id) === event.target.value)
                    setLessonPlanForm((current) => ({
                      ...current,
                      curriculum_lesson_id: event.target.value,
                      package_id: selected ? String(selected.package_id) : current.package_id,
                      estimated_duration_minutes:
                        current.estimated_duration_minutes || (selected?.duration ? String(selected.duration) : ''),
                    }))
                  }}
                >
                  <option value="">Select a lesson</option>
                  {lessonOptions.map((lesson) => (
                    <option key={lesson.id} value={lesson.id}>
                      {lesson.label}
                    </option>
                  ))}
                </select>
              </div>
              <div className="grid gap-3 md:grid-cols-2">
                <div className="space-y-2">
                  <Label>Target date</Label>
                  <Input
                    type="date"
                    value={lessonPlanForm.target_date}
                    onChange={(event) => setLessonPlanForm((current) => ({ ...current, target_date: event.target.value }))}
                  />
                </div>
                <div className="space-y-2">
                  <Label>Duration (minutes)</Label>
                  <Input
                    type="number"
                    min="1"
                    value={lessonPlanForm.estimated_duration_minutes}
                    onChange={(event) =>
                      setLessonPlanForm((current) => ({ ...current, estimated_duration_minutes: event.target.value }))
                    }
                  />
                </div>
              </div>
              <div className="space-y-2">
                <Label>Status</Label>
                <select
                  className={selectClassName}
                  value={lessonPlanForm.status}
                  onChange={(event) =>
                    setLessonPlanForm((current) => ({ ...current, status: event.target.value as LessonPlanStatus }))
                  }
                >
                  {lessonStatuses.map((status) => (
                    <option key={status} value={status}>
                      {status}
                    </option>
                  ))}
                </select>
              </div>
              <div className="space-y-2">
                <Label>Notes</Label>
                <Textarea
                  value={lessonPlanForm.notes}
                  onChange={(event) => setLessonPlanForm((current) => ({ ...current, notes: event.target.value }))}
                />
              </div>
              <div className="flex gap-2">
                <Button className="flex-1" onClick={() => void handleSaveLessonPlan()}>
                  {editingLessonPlanId ? 'Update lesson plan' : 'Create lesson plan'}
                </Button>
                {editingLessonPlanId ? (
                  <Button variant="outline" onClick={resetLessonPlanForm}>
                    Cancel
                  </Button>
                ) : null}
              </div>
            </CardContent>
          </Card> : null}

          {tool === 'pacing' ? <Card>
            <CardHeader>
              <CardTitle>{editingPacingTargetId ? 'Edit pacing target' : 'Add pacing target'}</CardTitle>
              <CardDescription>Set the target window for each unit to drive pace indicators.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="space-y-2">
                <Label>Unit</Label>
                <select
                  className={selectClassName}
                  value={pacingForm.curriculum_unit_id}
                  onChange={(event) => setPacingForm((current) => ({ ...current, curriculum_unit_id: event.target.value }))}
                >
                  <option value="">Select a unit</option>
                  {unitOptions.map((unit) => (
                    <option key={unit.id} value={unit.id}>
                      {unit.label}
                    </option>
                  ))}
                </select>
              </div>
              <div className="grid gap-3 md:grid-cols-2">
                <div className="space-y-2">
                  <Label>Target start</Label>
                  <Input
                    type="date"
                    value={pacingForm.target_start_date}
                    onChange={(event) => setPacingForm((current) => ({ ...current, target_start_date: event.target.value }))}
                  />
                </div>
                <div className="space-y-2">
                  <Label>Target end</Label>
                  <Input
                    type="date"
                    value={pacingForm.target_end_date}
                    onChange={(event) => setPacingForm((current) => ({ ...current, target_end_date: event.target.value }))}
                  />
                </div>
              </div>
              <div className="flex gap-2">
                <Button className="flex-1" onClick={() => void handleSavePacingTarget()}>
                  {editingPacingTargetId ? 'Update pacing target' : 'Create pacing target'}
                </Button>
                {editingPacingTargetId ? (
                  <Button variant="outline" onClick={resetPacingForm}>
                    Cancel
                  </Button>
                ) : null}
              </div>
            </CardContent>
          </Card> : null}
        </div>
      ) : null}

      {canManageCurriculum && selectedLessonPlanIds.length ? (
        <Card>
          <CardHeader>
            <CardTitle>Bulk actions</CardTitle>
            <CardDescription>{selectedLessonPlanIds.length} lesson plan(s) selected.</CardDescription>
          </CardHeader>
          <CardContent className="flex flex-wrap items-end gap-3">
            <Button variant="secondary" onClick={() => void handleBulkStatusUpdate('completed')}>
              Mark complete
            </Button>
            <Button variant="outline" onClick={() => void handleBulkStatusUpdate('skipped')}>
              Skip
            </Button>
            <div className="space-y-2">
              <Label>Reschedule to</Label>
              <Input type="date" value={bulkRescheduleDate} onChange={(event) => setBulkRescheduleDate(event.target.value)} />
            </div>
            <Button variant="outline" onClick={() => void handleBulkStatusUpdate('rescheduled')}>
              Reschedule
            </Button>
            <Button onClick={() => void handleGenerateAssignments(selectedLessonPlanIds)}>Generate assignments</Button>
          </CardContent>
        </Card>
      ) : null}

      <div className="space-y-4">
        <Card>
          <CardHeader>
            <CardTitle>Planned lessons</CardTitle>
            <CardDescription>
              {sectionLoading ? 'Refreshing…' : `${visibleLessons.length} lesson plan(s) for ${students.find((student) => String(student.id) === selectedStudentId)?.name || 'this student'}.`}
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {scope === 'calendar' ? <PlanningCalendar date={date} view={view} entries={visibleLessons.map(lessonEntry)} /> : visibleLessons.length ? (
              <div className="space-y-3">
                {visibleLessons.slice((visibleHistoryPage - 1) * 10, visibleHistoryPage * 10).map((lesson) =>
                  <PlanningEntry key={lesson.id} entry={lessonEntry(lesson)} />)}
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <p className="text-sm text-muted-foreground">{visibleLessons.length} lessons · Page {visibleHistoryPage} of {historyPages}</p>
                  <div className="flex gap-2">
                    <Button variant="outline" disabled={visibleHistoryPage <= 1} onClick={() => setHistoryPage(visibleHistoryPage - 1)}>Previous</Button>
                    <Button variant="outline" disabled={visibleHistoryPage >= historyPages} onClick={() => setHistoryPage(visibleHistoryPage + 1)}>Next</Button>
                  </div>
                </div>
              </div>
            ) : (
              <EmptyState title="No lesson plans yet" description="Generate a sequence from curriculum or add a lesson manually." />
            )}
          </CardContent>
        </Card>

        <details className="rounded-lg border p-4">
          <summary className="cursor-pointer font-medium">Pacing status and targets</summary>
        <div className="mt-4 grid gap-4 xl:grid-cols-2">
          <Card>
            <CardHeader>
              <CardTitle>Pacing status</CardTitle>
              <CardDescription>Ahead, on-track, and behind indicators per unit.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              {pacingItems.length ? (
                pacingItems.map((item) => (
                  <div key={item.pacing_target_id} className="rounded-lg border p-3">
                    <div className="flex items-center justify-between gap-3">
                      <div>
                        <p className="font-medium">{item.unit_name}</p>
                        <p className="text-sm text-muted-foreground">{item.package_name}</p>
                      </div>
                      <Badge variant={statusVariant(item.status)}>{item.status.replace('_', ' ')}</Badge>
                    </div>
                    <div className="mt-2 text-sm text-muted-foreground">
                      {formatDateLabel(item.target_start_date)} → {formatDateLabel(item.target_end_date)}
                    </div>
                    <div className="mt-2 text-sm">
                      {item.completed_lessons} of {item.total_lessons} lessons finished · {item.remaining_lessons} remaining
                    </div>
                  </div>
                ))
              ) : (
                <p className="text-sm text-muted-foreground">No pacing targets defined for the current filters.</p>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Pacing targets</CardTitle>
              <CardDescription>Adjust target windows or review actual completion dates.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              {pacingTargets.length ? (
                pacingTargets.map((target) => (
                  <div key={target.id} className="rounded-lg border p-3">
                    <div className="flex items-center justify-between gap-3">
                      <div>
                        <p className="font-medium">{target.curriculum_unit.name}</p>
                        <p className="text-sm text-muted-foreground">{target.curriculum_unit.package.name}</p>
                      </div>
                      {target.actual_completion_date ? <Badge variant="secondary">Completed {formatDateLabel(target.actual_completion_date)}</Badge> : null}
                    </div>
                    <p className="mt-2 text-sm text-muted-foreground">
                      {formatDateLabel(target.target_start_date)} → {formatDateLabel(target.target_end_date)}
                    </p>
                    {canManageCurriculum ? (
                      <div className="mt-3 flex gap-2">
                        <Button variant="outline" size="sm" onClick={() => loadPacingTargetForEdit(target)}>
                          <Pencil className="mr-1 h-3.5 w-3.5" />
                          Edit
                        </Button>
                        <Button variant="outline" size="sm" onClick={() => void handleDeletePacingTarget(target.id)}>
                          <Trash2 className="mr-1 h-3.5 w-3.5" />
                          Delete
                        </Button>
                      </div>
                    ) : null}
                  </div>
                ))
              ) : (
                <p className="text-sm text-muted-foreground">No pacing targets yet.</p>
              )}
            </CardContent>
          </Card>
        </div>
        </details>
      </div>
    </div>
  )
}
