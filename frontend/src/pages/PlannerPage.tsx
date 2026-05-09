import { useCallback, useEffect, useMemo, useState } from 'react'
import { Pencil, Plus, Trash2 } from 'lucide-react'
import { api } from '@/lib/api'
import type {
  AgendaItem,
  DailyAgenda,
  Schedule,
  ScheduleBlock,
  ScheduleDetail,
  ScheduleOverrideType,
  SchoolYear,
  Student,
  Subject,
  WeeklyAgenda,
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

const dayLabels = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
const selectClassName = 'h-10 w-full rounded-md border border-input bg-background px-3 text-sm'
const weekDaysShort = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
const slotMinutes = 30

type ScheduleForm = {
  name: string
  school_year_id: string
}

type BlockForm = {
  subject_id: string
  day_of_week: string
  start_time: string
  end_time: string
  location: string
  notes: string
}

type OverrideForm = {
  date: string
  override_type: ScheduleOverrideType
  original_block_id: string
  subject_id: string
  start_time: string
  end_time: string
  reason: string
}

type GridCell = AgendaItem & { span: number }

type WeekGrid = {
  slots: number[]
  startMap: Record<string, Record<number, GridCell>>
  coveredMap: Record<string, Set<number>>
}

function toInputDate(value = new Date()) {
  const year = value.getFullYear()
  const month = String(value.getMonth() + 1).padStart(2, '0')
  const day = String(value.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

function shiftDate(value: string, days: number) {
  const next = new Date(`${value}T12:00:00`)
  next.setDate(next.getDate() + days)
  return toInputDate(next)
}

function shiftWeek(value: string, weeks: number) {
  return shiftDate(value, weeks * 7)
}

function formatDisplayDate(value: string) {
  return new Date(`${value}T12:00:00`).toLocaleDateString(undefined, {
    weekday: 'short',
    month: 'short',
    day: 'numeric',
  })
}

function formatLongDate(value: string) {
  return new Date(`${value}T12:00:00`).toLocaleDateString(undefined, {
    weekday: 'long',
    month: 'long',
    day: 'numeric',
    year: 'numeric',
  })
}

function normalizeTime(value?: string | null) {
  return value ? value.slice(0, 5) : ''
}

function timeToMinutes(value: string) {
  const [hours, minutes] = value.split(':').map(Number)
  return hours * 60 + minutes
}

function minutesToLabel(totalMinutes: number) {
  const hours = Math.floor(totalMinutes / 60)
  const minutes = totalMinutes % 60
  return new Date(2000, 0, 1, hours, minutes).toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' })
}

function emptyScheduleForm(defaultSchoolYearId = ''): ScheduleForm {
  return { name: '', school_year_id: defaultSchoolYearId }
}

function emptyBlockForm(): BlockForm {
  return { subject_id: '', day_of_week: '0', start_time: '09:00', end_time: '10:00', location: '', notes: '' }
}

function emptyOverrideForm(date = toInputDate()): OverrideForm {
  return {
    date,
    override_type: 'add',
    original_block_id: '',
    subject_id: '',
    start_time: '13:00',
    end_time: '14:00',
    reason: '',
  }
}

function buildWeekGrid(week: WeeklyAgenda | null): WeekGrid {
  if (!week || !week.days.length) {
    return { slots: [], startMap: {}, coveredMap: {} }
  }

  const allItems = week.days.flatMap((day) => day.items)
  const earliest = allItems.length ? Math.min(...allItems.map((item) => timeToMinutes(normalizeTime(item.start_time)))) : 8 * 60
  const latest = allItems.length ? Math.max(...allItems.map((item) => timeToMinutes(normalizeTime(item.end_time)))) : 16 * 60
  const minSlot = Math.max(0, Math.floor(earliest / slotMinutes) * slotMinutes)
  const maxSlot = Math.min(24 * 60, Math.ceil(latest / slotMinutes) * slotMinutes + slotMinutes)
  const slots: number[] = []
  for (let minute = minSlot; minute < maxSlot; minute += slotMinutes) {
    slots.push(minute)
  }

  const startMap: Record<string, Record<number, GridCell>> = {}
  const coveredMap: Record<string, Set<number>> = {}

  week.days.forEach((day) => {
    startMap[day.date] = {}
    coveredMap[day.date] = new Set<number>()
    day.items.forEach((item) => {
      const startIndex = Math.max(0, Math.floor((timeToMinutes(normalizeTime(item.start_time)) - minSlot) / slotMinutes))
      const duration = Math.max(slotMinutes, timeToMinutes(normalizeTime(item.end_time)) - timeToMinutes(normalizeTime(item.start_time)))
      const span = Math.max(1, Math.ceil(duration / slotMinutes))
      startMap[day.date][startIndex] = { ...item, span }
      for (let offset = 1; offset < span; offset += 1) {
        coveredMap[day.date].add(startIndex + offset)
      }
    })
  })

  return { slots, startMap, coveredMap }
}

export function PlannerPage() {
  const { canManageCurriculum, studentId: scopedStudentId } = useAuth()
  const [students, setStudents] = useState<Student[]>([])
  const [subjects, setSubjects] = useState<Subject[]>([])
  const [schoolYears, setSchoolYears] = useState<SchoolYear[]>([])
  const [schedules, setSchedules] = useState<Schedule[]>([])
  const [selectedStudentId, setSelectedStudentId] = useState('')
  const [selectedScheduleId, setSelectedScheduleId] = useState('')
  const [selectedSchedule, setSelectedSchedule] = useState<ScheduleDetail | null>(null)
  const [dailyAgenda, setDailyAgenda] = useState<DailyAgenda | null>(null)
  const [weeklyAgenda, setWeeklyAgenda] = useState<WeeklyAgenda | null>(null)
  const [selectedDate, setSelectedDate] = useState(toInputDate())
  const [referenceLoading, setReferenceLoading] = useState(true)
  const [sectionLoading, setSectionLoading] = useState(false)
  const [error, setError] = useState('')
  const [actionError, setActionError] = useState('')
  const [successMessage, setSuccessMessage] = useState('')
  const [editingScheduleId, setEditingScheduleId] = useState<number | null>(null)
  const [editingBlockId, setEditingBlockId] = useState<number | null>(null)
  const [scheduleForm, setScheduleForm] = useState<ScheduleForm>(emptyScheduleForm())
  const [blockForm, setBlockForm] = useState<BlockForm>(emptyBlockForm())
  const [overrideForm, setOverrideForm] = useState<OverrideForm>(emptyOverrideForm())

  const defaultSchoolYearId = useMemo(
    () => String(schoolYears.find((schoolYear) => schoolYear.is_active)?.id ?? schoolYears[0]?.id ?? ''),
    [schoolYears],
  )

  const selectedStudent = useMemo(
    () => students.find((student) => String(student.id) === selectedStudentId) ?? null,
    [selectedStudentId, students],
  )

  const blockLookup = useMemo(() => {
    const map = new Map<number, ScheduleBlock>()
    selectedSchedule?.blocks.forEach((block) => map.set(block.id, block))
    return map
  }, [selectedSchedule])

  const weekGrid = useMemo(() => buildWeekGrid(weeklyAgenda), [weeklyAgenda])

  const loadReferenceData = useCallback(async () => {
    const [studentData, subjectData, schoolYearData] = await Promise.all([
      api.listStudents(),
      api.listSubjects(),
      api.listSchoolYears(),
    ])
    setStudents(studentData)
    setSubjects(subjectData)
    setSchoolYears(schoolYearData)
    const preferredStudentId = scopedStudentId ? String(scopedStudentId) : ''
    const nextStudentId =
      (preferredStudentId && studentData.some((student) => String(student.id) === preferredStudentId) && preferredStudentId) ||
      (studentData[0] ? String(studentData[0].id) : '')
    setSelectedStudentId((current) =>
      current && studentData.some((student) => String(student.id) === current) ? current : nextStudentId,
    )
  }, [scopedStudentId])

  const loadSchedules = useCallback(async (studentValue: string, preferredScheduleId?: string) => {
    if (!studentValue) {
      setSchedules([])
      setSelectedScheduleId('')
      setSelectedSchedule(null)
      return
    }
    const scheduleData = await api.listSchedules(Number(studentValue))
    setSchedules(scheduleData)
    setSelectedScheduleId((current) => {
      const desired = preferredScheduleId ?? current
      if (desired && scheduleData.some((schedule) => String(schedule.id) === desired)) {
        return desired
      }
      return scheduleData[0] ? String(scheduleData[0].id) : ''
    })
  }, [])

  const loadScheduleDetail = useCallback(async (scheduleValue: string) => {
    if (!scheduleValue) {
      setSelectedSchedule(null)
      return
    }
    setSelectedSchedule(await api.getSchedule(Number(scheduleValue)))
  }, [])

  const loadAgendaViews = useCallback(async (studentValue: string, dateValue: string) => {
    if (!studentValue) {
      setDailyAgenda(null)
      setWeeklyAgenda(null)
      return
    }
    const [daily, weekly] = await Promise.all([
      api.getDailyAgenda(Number(studentValue), dateValue),
      api.getWeeklyAgenda(Number(studentValue), dateValue),
    ])
    setDailyAgenda(daily)
    setWeeklyAgenda(weekly)
  }, [])

  const refreshPlanner = useCallback(
    async (preferredScheduleId?: string) => {
      if (!selectedStudentId) return
      setSectionLoading(true)
      try {
        await Promise.all([loadSchedules(selectedStudentId, preferredScheduleId), loadAgendaViews(selectedStudentId, selectedDate)])
      } finally {
        setSectionLoading(false)
      }
    },
    [loadAgendaViews, loadSchedules, selectedDate, selectedStudentId],
  )

  useEffect(() => {
    let cancelled = false
    setReferenceLoading(true)
    setError('')
    void loadReferenceData()
      .catch((loadError) => {
        if (!cancelled) {
          setError(loadError instanceof Error ? loadError.message : 'Unable to load planner data')
        }
      })
      .finally(() => {
        if (!cancelled) {
          setReferenceLoading(false)
        }
      })
    return () => {
      cancelled = true
    }
  }, [loadReferenceData])

  useEffect(() => {
    if (!defaultSchoolYearId || scheduleForm.school_year_id) return
    setScheduleForm((current) => ({ ...current, school_year_id: defaultSchoolYearId }))
  }, [defaultSchoolYearId, scheduleForm.school_year_id])

  useEffect(() => {
    if (!selectedStudentId) {
      setSchedules([])
      setSelectedScheduleId('')
      setSelectedSchedule(null)
      setDailyAgenda(null)
      setWeeklyAgenda(null)
      return
    }
    let cancelled = false
    setSectionLoading(true)
    setError('')
    void Promise.all([loadSchedules(selectedStudentId), loadAgendaViews(selectedStudentId, selectedDate)])
      .catch((loadError) => {
        if (!cancelled) {
          setError(loadError instanceof Error ? loadError.message : 'Unable to load planner view')
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
  }, [loadAgendaViews, loadSchedules, selectedDate, selectedStudentId])

  useEffect(() => {
    if (!selectedScheduleId) {
      setSelectedSchedule(null)
      return
    }
    let cancelled = false
    void loadScheduleDetail(selectedScheduleId).catch((loadError) => {
      if (!cancelled) {
        setError(loadError instanceof Error ? loadError.message : 'Unable to load schedule details')
      }
    })
    return () => {
      cancelled = true
    }
  }, [loadScheduleDetail, selectedScheduleId])

  useEffect(() => {
    setOverrideForm((current) => ({ ...current, date: selectedDate }))
  }, [selectedDate])

  const resetScheduleForm = useCallback(() => {
    setEditingScheduleId(null)
    setScheduleForm(emptyScheduleForm(defaultSchoolYearId))
  }, [defaultSchoolYearId])

  const resetBlockForm = useCallback(() => {
    setEditingBlockId(null)
    setBlockForm(emptyBlockForm())
  }, [])

  const resetOverrideForm = useCallback(() => {
    setOverrideForm(emptyOverrideForm(selectedDate))
  }, [selectedDate])

  const handleActionError = (actionFailure: unknown, fallback: string) => {
    setActionError(actionFailure instanceof Error ? actionFailure.message : fallback)
    setSuccessMessage('')
  }

  const handleSaveSchedule = async () => {
    if (!selectedStudentId || !scheduleForm.name.trim() || !scheduleForm.school_year_id) return
    setActionError('')
    try {
      let scheduleId = editingScheduleId ? String(editingScheduleId) : ''
      if (editingScheduleId) {
        await api.updateSchedule(editingScheduleId, {
          student_id: Number(selectedStudentId),
          school_year_id: Number(scheduleForm.school_year_id),
          name: scheduleForm.name.trim(),
        })
      } else {
        const created = await api.createSchedule({
          student_id: Number(selectedStudentId),
          school_year_id: Number(scheduleForm.school_year_id),
          name: scheduleForm.name.trim(),
        })
        scheduleId = String(created.id)
      }
      await refreshPlanner(scheduleId)
      resetScheduleForm()
      setSuccessMessage(editingScheduleId ? 'Schedule updated.' : 'Schedule created.')
    } catch (actionFailure) {
      handleActionError(actionFailure, 'Unable to save schedule')
    }
  }

  const handleDeleteSchedule = async (scheduleId: number) => {
    setActionError('')
    try {
      await api.deleteSchedule(scheduleId)
      const remaining = schedules.filter((schedule) => schedule.id !== scheduleId)
      await refreshPlanner(remaining[0] ? String(remaining[0].id) : '')
      if (editingScheduleId === scheduleId) {
        resetScheduleForm()
      }
      setSuccessMessage('Schedule deleted.')
    } catch (actionFailure) {
      handleActionError(actionFailure, 'Unable to delete schedule')
    }
  }

  const handleSaveBlock = async () => {
    if (!selectedScheduleId || !blockForm.subject_id || !blockForm.start_time || !blockForm.end_time) return
    setActionError('')
    try {
      const payload = {
        subject_id: Number(blockForm.subject_id),
        day_of_week: Number(blockForm.day_of_week),
        start_time: blockForm.start_time,
        end_time: blockForm.end_time,
        location: blockForm.location.trim() || undefined,
        notes: blockForm.notes.trim() || undefined,
      }
      if (editingBlockId) {
        await api.updateScheduleBlock(editingBlockId, payload)
      } else {
        await api.createScheduleBlock(Number(selectedScheduleId), payload)
      }
      await refreshPlanner(selectedScheduleId)
      resetBlockForm()
      setSuccessMessage(editingBlockId ? 'Schedule block updated.' : 'Schedule block added.')
    } catch (actionFailure) {
      handleActionError(actionFailure, 'Unable to save schedule block')
    }
  }

  const handleDeleteBlock = async (blockId: number) => {
    setActionError('')
    try {
      await api.deleteScheduleBlock(blockId)
      await refreshPlanner(selectedScheduleId)
      if (editingBlockId === blockId) {
        resetBlockForm()
      }
      setSuccessMessage('Schedule block deleted.')
    } catch (actionFailure) {
      handleActionError(actionFailure, 'Unable to delete schedule block')
    }
  }

  const handleSaveOverride = async () => {
    if (!selectedScheduleId || !overrideForm.date || !overrideForm.reason.trim()) return
    if (overrideForm.override_type !== 'cancel' && (!overrideForm.subject_id || !overrideForm.start_time || !overrideForm.end_time)) return
    if (overrideForm.override_type !== 'add' && !overrideForm.original_block_id) return
    setActionError('')
    try {
      await api.createScheduleOverride({
        schedule_id: Number(selectedScheduleId),
        date: overrideForm.date,
        original_block_id: overrideForm.original_block_id ? Number(overrideForm.original_block_id) : undefined,
        override_type: overrideForm.override_type,
        subject_id: overrideForm.override_type === 'cancel' ? undefined : Number(overrideForm.subject_id),
        start_time: overrideForm.override_type === 'cancel' ? undefined : overrideForm.start_time,
        end_time: overrideForm.override_type === 'cancel' ? undefined : overrideForm.end_time,
        reason: overrideForm.reason.trim(),
      })
      await refreshPlanner(selectedScheduleId)
      resetOverrideForm()
      setSuccessMessage('Override saved.')
    } catch (actionFailure) {
      handleActionError(actionFailure, 'Unable to save override')
    }
  }

  const handleDeleteOverride = async (overrideId: number) => {
    setActionError('')
    try {
      await api.deleteScheduleOverride(overrideId)
      await refreshPlanner(selectedScheduleId)
      setSuccessMessage('Override deleted.')
    } catch (actionFailure) {
      handleActionError(actionFailure, 'Unable to delete override')
    }
  }

  if (referenceLoading) {
    return <LoadingState message="Loading planner..." />
  }

  if (error && !students.length) {
    return <ErrorState message={error} onRetry={() => void loadReferenceData()} />
  }

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <CardTitle>Planner</CardTitle>
          <CardDescription>Build recurring weekly schedules, then layer one-off daily changes for each student.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {actionError ? <div className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">{actionError}</div> : null}
          {successMessage ? <div className="rounded-md border border-emerald-500/30 bg-emerald-500/10 px-3 py-2 text-sm text-emerald-700">{successMessage}</div> : null}
          {error && students.length ? <div className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">{error}</div> : null}
          <div className="grid gap-4 md:grid-cols-3">
            <div className="space-y-2">
              <Label>Student</Label>
              <select
                className={selectClassName}
                disabled={Boolean(scopedStudentId)}
                value={selectedStudentId}
                onChange={(event) => setSelectedStudentId(event.target.value)}
              >
                {students.map((student) => (
                  <option key={student.id} value={String(student.id)}>
                    {student.name}
                  </option>
                ))}
              </select>
            </div>
            <div className="space-y-2">
              <Label>Planner date</Label>
              <Input type="date" value={selectedDate} onChange={(event) => setSelectedDate(event.target.value)} />
            </div>
            <div className="space-y-2">
              <Label>Selected schedule</Label>
              <select className={selectClassName} value={selectedScheduleId} onChange={(event) => setSelectedScheduleId(event.target.value)}>
                {schedules.length ? (
                  schedules.map((schedule) => (
                    <option key={schedule.id} value={String(schedule.id)}>
                      {schedule.name} - {schedule.school_year.name}
                    </option>
                  ))
                ) : (
                  <option value="">No schedules</option>
                )}
              </select>
            </div>
          </div>
          {selectedStudent ? (
            <div className="text-sm text-muted-foreground">
              Showing planner data for <span className="font-medium text-foreground">{selectedStudent.name}</span>
              {sectionLoading ? ' - refreshing...' : ''}
            </div>
          ) : null}
        </CardContent>
      </Card>

      <div className="grid gap-4 xl:grid-cols-[1.1fr_0.9fr]">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between gap-4">
            <div>
              <CardTitle>Weekly schedule grid</CardTitle>
              <CardDescription>
                Week of {weeklyAgenda ? formatLongDate(weeklyAgenda.week_start) : formatLongDate(selectedDate)}
              </CardDescription>
            </div>
            <div className="flex gap-2">
              <Button variant="outline" size="sm" onClick={() => setSelectedDate((current) => shiftWeek(current, -1))}>
                Previous week
              </Button>
              <Button variant="outline" size="sm" onClick={() => setSelectedDate((current) => shiftWeek(current, 1))}>
                Next week
              </Button>
            </div>
          </CardHeader>
          <CardContent>
            {weeklyAgenda && weekGrid.slots.length ? (
              <div className="overflow-x-auto">
                <table className="w-full min-w-[880px] border-collapse text-sm">
                  <thead>
                    <tr>
                      <th className="w-24 border px-2 py-2 text-left">Time</th>
                      {weeklyAgenda.days.map((day, index) => (
                        <th key={day.date} className="border px-2 py-2 text-left">
                          <div className="font-medium">{weekDaysShort[index]}</div>
                          <div className="text-xs text-muted-foreground">{formatDisplayDate(day.date)}</div>
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {weekGrid.slots.map((slot, slotIndex) => (
                      <tr key={slot}>
                        <td className="border px-2 py-2 align-top text-xs text-muted-foreground">{minutesToLabel(slot)}</td>
                        {weeklyAgenda.days.map((day) => {
                          const cell = weekGrid.startMap[day.date]?.[slotIndex]
                          if (cell) {
                            return (
                              <td key={`${day.date}-${slotIndex}`} rowSpan={cell.span} className="border bg-muted/30 p-2 align-top">
                                <div className="space-y-1">
                                  <div className="flex items-center justify-between gap-2">
                                    <span className="font-medium">{cell.subject_name}</span>
                                    <Badge variant={cell.source === 'override' ? 'default' : 'secondary'}>{cell.source}</Badge>
                                  </div>
                                  <div className="text-xs text-muted-foreground">
                                    {normalizeTime(cell.start_time)}-{normalizeTime(cell.end_time)}
                                  </div>
                                  {cell.location ? <div className="text-xs text-muted-foreground">{cell.location}</div> : null}
                                  {cell.reason ? <div className="text-xs">{cell.reason}</div> : null}
                                </div>
                              </td>
                            )
                          }
                          if (weekGrid.coveredMap[day.date]?.has(slotIndex)) {
                            return null
                          }
                          return <td key={`${day.date}-${slotIndex}`} className="h-14 border align-top" />
                        })}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <EmptyState title="No schedule this week" description="Create recurring blocks or add overrides to populate the weekly planner." />
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between gap-4">
            <div>
              <CardTitle>Daily agenda</CardTitle>
              <CardDescription>{formatLongDate(selectedDate)}</CardDescription>
            </div>
            <div className="flex gap-2">
              <Button variant="outline" size="sm" onClick={() => setSelectedDate((current) => shiftDate(current, -1))}>
                Previous day
              </Button>
              <Button variant="outline" size="sm" onClick={() => setSelectedDate((current) => shiftDate(current, 1))}>
                Next day
              </Button>
            </div>
          </CardHeader>
          <CardContent>
            {dailyAgenda?.items.length ? (
              <div className="space-y-3">
                {dailyAgenda.items.map((item) => (
                  <div key={`${item.source}-${item.override_id ?? item.block_id ?? item.subject_id}`} className="rounded-lg border p-3">
                    <div className="flex items-center justify-between gap-2">
                      <div>
                        <div className="font-medium">{item.subject_name}</div>
                        <div className="text-xs text-muted-foreground">
                          {normalizeTime(item.start_time)}-{normalizeTime(item.end_time)} - {item.schedule_name}
                        </div>
                      </div>
                      <Badge variant={item.source === 'override' ? 'default' : 'secondary'}>
                        {item.override_type || item.source}
                      </Badge>
                    </div>
                    {item.location ? <div className="mt-2 text-sm text-muted-foreground">Location: {item.location}</div> : null}
                    {item.notes ? <div className="mt-1 text-sm text-muted-foreground">{item.notes}</div> : null}
                    {item.reason ? <div className="mt-1 text-sm">Reason: {item.reason}</div> : null}
                  </div>
                ))}
              </div>
            ) : (
              <EmptyState title="No agenda items" description="This student has no scheduled blocks for the selected day." />
            )}
          </CardContent>
        </Card>
      </div>

      <div className="grid gap-4 xl:grid-cols-[0.95fr_1.05fr]">
        <Card>
          <CardHeader>
            <CardTitle>Schedules</CardTitle>
            <CardDescription>Choose a schedule for this student, or create another school-year plan.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {schedules.length ? (
              <div className="space-y-2">
                {schedules.map((schedule) => (
                  <div
                    key={schedule.id}
                    className={`rounded-lg border p-3 ${String(schedule.id) === selectedScheduleId ? 'border-primary bg-primary/5' : ''}`}
                  >
                    <div className="flex flex-wrap items-start justify-between gap-2">
                      <div>
                        <div className="font-medium">{schedule.name}</div>
                        <div className="text-xs text-muted-foreground">{schedule.school_year.name}</div>
                      </div>
                      <div className="flex gap-2">
                        <Button size="sm" variant="outline" onClick={() => setSelectedScheduleId(String(schedule.id))}>
                          Open
                        </Button>
                        {canManageCurriculum ? (
                          <>
                            <Button
                              size="sm"
                              variant="outline"
                              onClick={() => {
                                setEditingScheduleId(schedule.id)
                                setScheduleForm({ name: schedule.name, school_year_id: String(schedule.school_year_id) })
                                setSelectedScheduleId(String(schedule.id))
                              }}
                            >
                              <Pencil className="mr-2 h-3.5 w-3.5" />
                              Edit
                            </Button>
                            <Button size="sm" variant="destructive" onClick={() => void handleDeleteSchedule(schedule.id)}>
                              <Trash2 className="mr-2 h-3.5 w-3.5" />
                              Delete
                            </Button>
                          </>
                        ) : null}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <EmptyState title="No schedules yet" description="Create a default weekly schedule for this student to start planning." />
            )}

            {canManageCurriculum ? (
              <div className="space-y-3 rounded-lg border p-4">
                <div className="text-sm font-medium">{editingScheduleId ? 'Edit schedule' : 'Create schedule'}</div>
                <div className="space-y-2">
                  <Label>Schedule name</Label>
                  <Input value={scheduleForm.name} onChange={(event) => setScheduleForm((current) => ({ ...current, name: event.target.value }))} />
                </div>
                <div className="space-y-2">
                  <Label>School year</Label>
                  <select
                    className={selectClassName}
                    value={scheduleForm.school_year_id}
                    onChange={(event) => setScheduleForm((current) => ({ ...current, school_year_id: event.target.value }))}
                  >
                    {schoolYears.map((schoolYear) => (
                      <option key={schoolYear.id} value={String(schoolYear.id)}>
                        {schoolYear.name}
                      </option>
                    ))}
                  </select>
                </div>
                <div className="flex gap-2">
                  <Button onClick={() => void handleSaveSchedule()}>
                    <Plus className="mr-2 h-4 w-4" />
                    {editingScheduleId ? 'Update schedule' : 'Create schedule'}
                  </Button>
                  {editingScheduleId ? (
                    <Button variant="outline" onClick={resetScheduleForm}>
                      Cancel edit
                    </Button>
                  ) : null}
                </div>
              </div>
            ) : null}
          </CardContent>
        </Card>

        <div className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Weekly blocks</CardTitle>
              <CardDescription>{selectedSchedule ? `${selectedSchedule.name} recurring plan` : 'Select a schedule to edit blocks.'}</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {canManageCurriculum ? (
                <div className="grid gap-4 rounded-lg border p-4 md:grid-cols-2">
                  <div className="space-y-2">
                    <Label>Subject</Label>
                    <select
                      className={selectClassName}
                      value={blockForm.subject_id}
                      onChange={(event) => setBlockForm((current) => ({ ...current, subject_id: event.target.value }))}
                    >
                      <option value="">Select subject</option>
                      {subjects.map((subject) => (
                        <option key={subject.id} value={String(subject.id)}>
                          {subject.name}
                        </option>
                      ))}
                    </select>
                  </div>
                  <div className="space-y-2">
                    <Label>Day</Label>
                    <select
                      className={selectClassName}
                      value={blockForm.day_of_week}
                      onChange={(event) => setBlockForm((current) => ({ ...current, day_of_week: event.target.value }))}
                    >
                      {dayLabels.map((label, index) => (
                        <option key={label} value={String(index)}>
                          {label}
                        </option>
                      ))}
                    </select>
                  </div>
                  <div className="space-y-2">
                    <Label>Start</Label>
                    <Input type="time" value={blockForm.start_time} onChange={(event) => setBlockForm((current) => ({ ...current, start_time: event.target.value }))} />
                  </div>
                  <div className="space-y-2">
                    <Label>End</Label>
                    <Input type="time" value={blockForm.end_time} onChange={(event) => setBlockForm((current) => ({ ...current, end_time: event.target.value }))} />
                  </div>
                  <div className="space-y-2">
                    <Label>Location</Label>
                    <Input value={blockForm.location} onChange={(event) => setBlockForm((current) => ({ ...current, location: event.target.value }))} />
                  </div>
                  <div className="space-y-2">
                    <Label>Notes</Label>
                    <Textarea value={blockForm.notes} onChange={(event) => setBlockForm((current) => ({ ...current, notes: event.target.value }))} />
                  </div>
                  <div className="md:col-span-2 flex gap-2">
                    <Button disabled={!selectedScheduleId} onClick={() => void handleSaveBlock()}>
                      <Plus className="mr-2 h-4 w-4" />
                      {editingBlockId ? 'Update block' : 'Add block'}
                    </Button>
                    {editingBlockId ? (
                      <Button variant="outline" onClick={resetBlockForm}>
                        Cancel edit
                      </Button>
                    ) : null}
                  </div>
                </div>
              ) : null}

              {selectedSchedule?.blocks.length ? (
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b text-left">
                        <th className="py-2 pr-2">Day</th>
                        <th className="py-2 pr-2">Time</th>
                        <th className="py-2 pr-2">Subject</th>
                        <th className="py-2 pr-2">Location</th>
                        <th className="py-2 pr-2">Notes</th>
                        {canManageCurriculum ? <th className="py-2">Actions</th> : null}
                      </tr>
                    </thead>
                    <tbody>
                      {selectedSchedule.blocks.map((block) => (
                        <tr key={block.id} className="border-b last:border-0">
                          <td className="py-2 pr-2">{dayLabels[block.day_of_week]}</td>
                          <td className="py-2 pr-2">{normalizeTime(block.start_time)}-{normalizeTime(block.end_time)}</td>
                          <td className="py-2 pr-2">{block.subject.name}</td>
                          <td className="py-2 pr-2">{block.location || '-'}</td>
                          <td className="py-2 pr-2 text-muted-foreground">{block.notes || '-'}</td>
                          {canManageCurriculum ? (
                            <td className="py-2">
                              <div className="flex gap-2">
                                <Button
                                  size="sm"
                                  variant="outline"
                                  onClick={() => {
                                    setEditingBlockId(block.id)
                                    setBlockForm({
                                      subject_id: String(block.subject_id),
                                      day_of_week: String(block.day_of_week),
                                      start_time: normalizeTime(block.start_time),
                                      end_time: normalizeTime(block.end_time),
                                      location: block.location || '',
                                      notes: block.notes || '',
                                    })
                                  }}
                                >
                                  <Pencil className="mr-2 h-3.5 w-3.5" />
                                  Edit
                                </Button>
                                <Button size="sm" variant="destructive" onClick={() => void handleDeleteBlock(block.id)}>
                                  <Trash2 className="mr-2 h-3.5 w-3.5" />
                                  Delete
                                </Button>
                              </div>
                            </td>
                          ) : null}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <EmptyState title="No recurring blocks" description="Add a few weekly blocks to build the planner grid." />
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>One-off overrides</CardTitle>
              <CardDescription>Cancel, reschedule, or add a block for a specific date.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {canManageCurriculum ? (
                <div className="grid gap-4 rounded-lg border p-4 md:grid-cols-2">
                  <div className="space-y-2">
                    <Label>Date</Label>
                    <Input type="date" value={overrideForm.date} onChange={(event) => setOverrideForm((current) => ({ ...current, date: event.target.value }))} />
                  </div>
                  <div className="space-y-2">
                    <Label>Override type</Label>
                    <select
                      className={selectClassName}
                      value={overrideForm.override_type}
                      onChange={(event) => setOverrideForm((current) => ({ ...current, override_type: event.target.value as ScheduleOverrideType }))}
                    >
                      <option value="add">Add</option>
                      <option value="cancel">Cancel</option>
                      <option value="reschedule">Reschedule</option>
                    </select>
                  </div>
                  <div className="space-y-2">
                    <Label>Original block</Label>
                    <select
                      className={selectClassName}
                      value={overrideForm.original_block_id}
                      onChange={(event) => setOverrideForm((current) => ({ ...current, original_block_id: event.target.value }))}
                    >
                      <option value="">Select block</option>
                      {selectedSchedule?.blocks.map((block) => (
                        <option key={block.id} value={String(block.id)}>
                          {dayLabels[block.day_of_week]} - {block.subject.name} - {normalizeTime(block.start_time)}-{normalizeTime(block.end_time)}
                        </option>
                      ))}
                    </select>
                  </div>
                  {overrideForm.override_type !== 'cancel' ? (
                    <>
                      <div className="space-y-2">
                        <Label>Subject</Label>
                        <select
                          className={selectClassName}
                          value={overrideForm.subject_id}
                          onChange={(event) => setOverrideForm((current) => ({ ...current, subject_id: event.target.value }))}
                        >
                          <option value="">Select subject</option>
                          {subjects.map((subject) => (
                            <option key={subject.id} value={String(subject.id)}>
                              {subject.name}
                            </option>
                          ))}
                        </select>
                      </div>
                      <div className="space-y-2">
                        <Label>Start</Label>
                        <Input type="time" value={overrideForm.start_time} onChange={(event) => setOverrideForm((current) => ({ ...current, start_time: event.target.value }))} />
                      </div>
                      <div className="space-y-2">
                        <Label>End</Label>
                        <Input type="time" value={overrideForm.end_time} onChange={(event) => setOverrideForm((current) => ({ ...current, end_time: event.target.value }))} />
                      </div>
                    </>
                  ) : null}
                  <div className="space-y-2 md:col-span-2">
                    <Label>Reason</Label>
                    <Textarea value={overrideForm.reason} onChange={(event) => setOverrideForm((current) => ({ ...current, reason: event.target.value }))} />
                  </div>
                  <div className="md:col-span-2 flex gap-2">
                    <Button disabled={!selectedScheduleId} onClick={() => void handleSaveOverride()}>
                      <Plus className="mr-2 h-4 w-4" />
                      Save override
                    </Button>
                    <Button variant="outline" onClick={resetOverrideForm}>
                      Reset form
                    </Button>
                  </div>
                </div>
              ) : null}

              {selectedSchedule?.overrides.length ? (
                <div className="space-y-2">
                  {selectedSchedule.overrides.map((override) => {
                    const originalBlock = override.original_block_id ? blockLookup.get(override.original_block_id) : null
                    const subjectName = override.subject?.name || originalBlock?.subject.name || 'Custom block'
                    return (
                      <div key={override.id} className="rounded-lg border p-3">
                        <div className="flex flex-wrap items-start justify-between gap-2">
                          <div>
                            <div className="font-medium">{formatDisplayDate(override.date)} - {subjectName}</div>
                            <div className="text-xs text-muted-foreground">
                              {override.override_type}
                              {override.start_time && override.end_time ? ` - ${normalizeTime(override.start_time)}-${normalizeTime(override.end_time)}` : ''}
                            </div>
                          </div>
                          {canManageCurriculum ? (
                            <Button size="sm" variant="destructive" onClick={() => void handleDeleteOverride(override.id)}>
                              <Trash2 className="mr-2 h-3.5 w-3.5" />
                              Delete
                            </Button>
                          ) : null}
                        </div>
                        <div className="mt-2 text-sm text-muted-foreground">{override.reason}</div>
                      </div>
                    )
                  })}
                </div>
              ) : (
                <EmptyState title="No overrides yet" description="Use overrides for field trips, cancellations, or special events." />
              )}
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  )
}
