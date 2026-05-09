import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { ChevronLeft, ChevronRight, Paperclip, ShieldCheck, UserCheck } from 'lucide-react'
import { api } from '@/lib/api'
import type {
  AttendanceHoursSummary,
  AttendanceRecord,
  AttendanceStatus,
  AttendanceSummary,
  SchoolYear,
  Student,
} from '@/types/api'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { EmptyState } from '@/components/common/EmptyState'
import { ErrorState } from '@/components/common/ErrorState'
import { LoadingState } from '@/components/common/LoadingState'
import { PullToRefresh } from '@/components/common/PullToRefresh'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Textarea } from '@/components/ui/textarea'

const statusOptions: AttendanceStatus[] = ['present', 'absent', 'tardy', 'excused']
const monthNames = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December']

type DailyDraft = {
  status: AttendanceStatus
  instructional_hours: string
  check_in_time: string
  check_out_time: string
  notes: string
}

function toLocalDate(value: string) {
  const [year, month, day] = value.split('-').map(Number)
  return new Date(year, month - 1, day)
}

function monthKeyFromDate(value: string) {
  return value.slice(0, 7)
}

function startOfMonth(monthKey: string) {
  const [year, month] = monthKey.split('-').map(Number)
  return new Date(year, month - 1, 1)
}

function addMonths(monthKey: string, delta: number) {
  const current = startOfMonth(monthKey)
  current.setMonth(current.getMonth() + delta)
  return `${current.getFullYear()}-${String(current.getMonth() + 1).padStart(2, '0')}`
}

function monthBounds(monthKey: string) {
  const start = startOfMonth(monthKey)
  const end = new Date(start.getFullYear(), start.getMonth() + 1, 0)
  const format = (value: Date) =>
    `${value.getFullYear()}-${String(value.getMonth() + 1).padStart(2, '0')}-${String(value.getDate()).padStart(2, '0')}`
  return { start: format(start), end: format(end), label: `${monthNames[start.getMonth()]} ${start.getFullYear()}` }
}

function emptyDailyDraft(record?: AttendanceRecord): DailyDraft {
  return {
    status: record?.status || 'present',
    instructional_hours: record?.instructional_hours || '0.00',
    check_in_time: record?.check_in_time?.slice(0, 5) || '',
    check_out_time: record?.check_out_time?.slice(0, 5) || '',
    notes: record?.notes || '',
  }
}

function statusBadgeVariant(status: AttendanceStatus) {
  if (status === 'absent') return 'destructive'
  if (status === 'excused') return 'secondary'
  return 'outline'
}

function statusDayClasses(status: AttendanceStatus) {
  if (status === 'present') return 'border-emerald-500 bg-emerald-100 text-emerald-800'
  if (status === 'tardy') return 'border-amber-500 bg-amber-100 text-amber-900'
  if (status === 'excused') return 'border-sky-500 bg-sky-100 text-sky-900'
  return 'border-rose-500 bg-rose-100 text-rose-900'
}

export function AttendancePage() {
  const today = new Date().toISOString().slice(0, 10)
  const [students, setStudents] = useState<Student[]>([])
  const [schoolYears, setSchoolYears] = useState<SchoolYear[]>([])
  const [attendanceRecords, setAttendanceRecords] = useState<AttendanceRecord[]>([])
  const [summary, setSummary] = useState<AttendanceSummary | null>(null)
  const [hoursSummary, setHoursSummary] = useState<AttendanceHoursSummary | null>(null)
  const [selectedDate, setSelectedDate] = useState(today)
  const [selectedMonth, setSelectedMonth] = useState(today.slice(0, 7))
  const [selectedStudentId, setSelectedStudentId] = useState<number | null>(null)
  const [selectedSchoolYearId, setSelectedSchoolYearId] = useState<number | null>(null)
  const [dailyDrafts, setDailyDrafts] = useState<Record<number, DailyDraft>>({})
  const [hoursForm, setHoursForm] = useState({
    student_id: 0,
    date: today,
    instructional_hours: '4.00',
    check_in_time: '09:00',
    check_out_time: '13:00',
    notes: '',
  })
  const [excuseRecordId, setExcuseRecordId] = useState<number | null>(null)
  const [excuseReason, setExcuseReason] = useState('')
  const [excuseFile, setExcuseFile] = useState<File | null>(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [statusMessage, setStatusMessage] = useState('')
  const touchStartX = useRef<Record<number, number>>({})

  const selectedStudent = useMemo(
    () => students.find((student) => student.id === selectedStudentId) || null,
    [selectedStudentId, students],
  )
  const monthRange = useMemo(() => monthBounds(selectedMonth), [selectedMonth])

  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const [studentData, schoolYearData] = await Promise.all([api.listStudents(), api.listSchoolYears()])
      const resolvedStudentId =
        selectedStudentId && studentData.some((student) => student.id === selectedStudentId)
          ? selectedStudentId
          : studentData[0]?.id || null
      const resolvedSchoolYearId =
        selectedSchoolYearId && schoolYearData.some((schoolYear) => schoolYear.id === selectedSchoolYearId)
          ? selectedSchoolYearId
          : schoolYearData.find((schoolYear) => schoolYear.is_active)?.id || schoolYearData[0]?.id || null

      setStudents(studentData)
      setSchoolYears(schoolYearData)
      setSelectedStudentId(resolvedStudentId)
      setSelectedSchoolYearId(resolvedSchoolYearId)
      setHoursForm((current) => ({ ...current, student_id: current.student_id || resolvedStudentId || 0 }))

      const records = await api.listAttendance({ date_from: monthRange.start, date_to: monthRange.end })
      setAttendanceRecords(records)

      if (resolvedStudentId) {
        const [summaryData, hoursData] = await Promise.all([
          api.getAttendanceSummary(resolvedStudentId, 'term', resolvedSchoolYearId || undefined),
          resolvedSchoolYearId ? api.getAttendanceHours(resolvedStudentId, resolvedSchoolYearId) : Promise.resolve(null),
        ])
        setSummary(summaryData)
        setHoursSummary(hoursData)
      } else {
        setSummary(null)
        setHoursSummary(null)
      }
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : 'Unable to load attendance')
    } finally {
      setLoading(false)
    }
  }, [monthRange.end, monthRange.start, selectedSchoolYearId, selectedStudentId])

  useEffect(() => {
    void load()
  }, [load])

  useEffect(() => {
    const nextDrafts: Record<number, DailyDraft> = {}
    students.forEach((student) => {
      const record = attendanceRecords.find((item) => item.student_id === student.id && item.date === selectedDate)
      nextDrafts[student.id] = emptyDailyDraft(record)
    })
    setDailyDrafts(nextDrafts)
  }, [attendanceRecords, selectedDate, students])

  const calendarRecords = useMemo(
    () => attendanceRecords.filter((record) => record.student_id === selectedStudentId),
    [attendanceRecords, selectedStudentId],
  )
  const recordsByDate = useMemo(
    () =>
      calendarRecords.reduce<Record<string, AttendanceRecord[]>>((accumulator, record) => {
        accumulator[record.date] = [...(accumulator[record.date] || []), record]
        return accumulator
      }, {}),
    [calendarRecords],
  )
  const monthGrid = useMemo(() => {
    const firstDay = startOfMonth(selectedMonth)
    const start = new Date(firstDay)
    start.setDate(1 - firstDay.getDay())
    return Array.from({ length: 42 }, (_, index) => {
      const current = new Date(start)
      current.setDate(start.getDate() + index)
      const key = `${current.getFullYear()}-${String(current.getMonth() + 1).padStart(2, '0')}-${String(current.getDate()).padStart(2, '0')}`
      return { key, inMonth: monthKeyFromDate(key) === selectedMonth, records: recordsByDate[key] || [] }
    })
  }, [recordsByDate, selectedMonth])

  const excuseCandidates = useMemo(
    () =>
      attendanceRecords
        .filter((record) => record.status !== 'present' || record.excuse)
        .sort((left, right) => right.date.localeCompare(left.date)),
    [attendanceRecords],
  )

  const saveDailyAttendance = async () => {
    if (!students.length) return
    setSaving(true)
    setStatusMessage('')
    try {
      await api.recordDailyAttendance({
        date: selectedDate,
        records: students.map((student) => ({
          student_id: student.id,
          status: dailyDrafts[student.id]?.status || 'present',
          instructional_hours: dailyDrafts[student.id]?.instructional_hours || '0.00',
          check_in_time: dailyDrafts[student.id]?.check_in_time || undefined,
          check_out_time: dailyDrafts[student.id]?.check_out_time || undefined,
          notes: dailyDrafts[student.id]?.notes || null,
        })),
      })
      setStatusMessage('Daily attendance saved.')
      await load()
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : 'Unable to save attendance')
    } finally {
      setSaving(false)
    }
  }

  const saveHours = async () => {
    if (!hoursForm.student_id) return
    setSaving(true)
    setStatusMessage('')
    try {
      await api.logInstructionalHours({
        ...hoursForm,
        check_in_time: hoursForm.check_in_time || null,
        check_out_time: hoursForm.check_out_time || null,
        notes: hoursForm.notes || null,
      })
      setStatusMessage('Instructional hours logged.')
      await load()
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : 'Unable to log instructional hours')
    } finally {
      setSaving(false)
    }
  }

  const saveExcuse = async () => {
    if (!excuseRecordId || !excuseReason.trim()) return
    setSaving(true)
    setStatusMessage('')
    try {
      const formData = new FormData()
      formData.append('attendance_record_id', String(excuseRecordId))
      formData.append('reason', excuseReason.trim())
      if (excuseFile) formData.append('document', excuseFile)
      await api.createAttendanceExcuse(formData)
      setExcuseReason('')
      setExcuseFile(null)
      setExcuseRecordId(null)
      setStatusMessage('Excuse saved.')
      await load()
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : 'Unable to save excuse')
    } finally {
      setSaving(false)
    }
  }

  const approveExcuse = async (excuseId: number) => {
    setSaving(true)
    setStatusMessage('')
    try {
      await api.approveAttendanceExcuse(excuseId)
      setStatusMessage('Excuse approved.')
      await load()
    } catch (approveError) {
      setError(approveError instanceof Error ? approveError.message : 'Unable to approve excuse')
    } finally {
      setSaving(false)
    }
  }

  const updateDailyDraft = (studentId: number, patch: Partial<DailyDraft>) => {
    setDailyDrafts((current) => ({
      ...current,
      [studentId]: { ...current[studentId], ...patch },
    }))
  }

  const applySwipeStatus = (studentId: number, status: AttendanceStatus) => {
    updateDailyDraft(studentId, { status })
    setStatusMessage(`Set ${students.find((student) => student.id === studentId)?.name || 'student'} to ${status}.`)
  }

  if (loading) return <LoadingState message="Loading attendance…" />
  if (error) return <ErrorState message={error} onRetry={() => void load()} />
  if (!students.length) {
    return <EmptyState title="No students yet" description="Add at least one student before tracking attendance." />
  }

  return (
    <PullToRefresh onRefresh={load}>
      <div className="space-y-4">
        {statusMessage ? (
          <div className="rounded-md border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-900">{statusMessage}</div>
        ) : null}

      <div className="grid gap-4 md:grid-cols-4">
        <Card>
          <CardHeader>
            <CardDescription>Selected student</CardDescription>
            <CardTitle>{selectedStudent?.name || '—'}</CardTitle>
          </CardHeader>
        </Card>
        <Card>
          <CardHeader>
            <CardDescription>Attendance rate</CardDescription>
            <CardTitle>{summary ? `${summary.attendance_rate.toFixed(1)}%` : '—'}</CardTitle>
          </CardHeader>
        </Card>
        <Card>
          <CardHeader>
            <CardDescription>Total hours</CardDescription>
            <CardTitle>{hoursSummary?.total_hours || '0.00'}</CardTitle>
          </CardHeader>
        </Card>
        <Card>
          <CardHeader>
            <CardDescription>Recorded days</CardDescription>
            <CardTitle>{hoursSummary?.recorded_days ?? 0}</CardTitle>
          </CardHeader>
        </Card>
      </div>

      <div className="grid gap-4 xl:grid-cols-[1.3fr_0.9fr]">
        <Card>
          <CardHeader>
            <CardTitle>Daily attendance</CardTitle>
            <CardDescription>Mark present, absent, tardy, or excused for every student on one date.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex flex-col gap-3 sm:flex-row sm:flex-wrap sm:items-end">
              <div className="w-full space-y-2 sm:w-auto">
                <Label>Date</Label>
                <Input type="date" value={selectedDate} onChange={(event) => setSelectedDate(event.target.value)} />
              </div>
              <Button className="w-full sm:w-auto" onClick={() => void saveDailyAttendance()} disabled={saving}>
                <UserCheck className="mr-2 h-4 w-4" />
                Save day
              </Button>
            </div>

            <div className="space-y-3 md:hidden">
              {students.map((student) => {
                const draft = dailyDrafts[student.id] || emptyDailyDraft()
                return (
                  <div
                    key={student.id}
                    className="rounded-lg border p-4"
                    onTouchStart={(event) => {
                      touchStartX.current[student.id] = event.changedTouches[0]?.clientX || 0
                    }}
                    onTouchEnd={(event) => {
                      const deltaX = (event.changedTouches[0]?.clientX || 0) - (touchStartX.current[student.id] || 0)
                      if (deltaX >= 60) applySwipeStatus(student.id, 'present')
                      if (deltaX <= -60) applySwipeStatus(student.id, 'absent')
                    }}
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <p className="font-medium">{student.name}</p>
                        <p className="text-xs text-muted-foreground">Swipe right for present, left for absent.</p>
                      </div>
                      <Badge variant={statusBadgeVariant(draft.status)}>{draft.status}</Badge>
                    </div>
                    <div className="mt-3 grid grid-cols-2 gap-2">
                      {statusOptions.map((status) => (
                        <Button
                          key={status}
                          type="button"
                          variant={draft.status === status ? 'default' : 'outline'}
                          className="capitalize"
                          onClick={() => updateDailyDraft(student.id, { status })}
                        >
                          {status}
                        </Button>
                      ))}
                    </div>
                    <div className="mt-3 grid gap-3">
                      <div className="grid grid-cols-2 gap-3">
                        <div className="space-y-2">
                          <Label>Hours</Label>
                          <Input value={draft.instructional_hours || '0.00'} onChange={(event) => updateDailyDraft(student.id, { instructional_hours: event.target.value })} />
                        </div>
                        <div className="space-y-2">
                          <Label>Check in</Label>
                          <Input type="time" value={draft.check_in_time || ''} onChange={(event) => updateDailyDraft(student.id, { check_in_time: event.target.value })} />
                        </div>
                      </div>
                      <div className="grid grid-cols-2 gap-3">
                        <div className="space-y-2">
                          <Label>Check out</Label>
                          <Input type="time" value={draft.check_out_time || ''} onChange={(event) => updateDailyDraft(student.id, { check_out_time: event.target.value })} />
                        </div>
                        <div className="space-y-2">
                          <Label>Notes</Label>
                          <Input value={draft.notes || ''} placeholder="Optional note" onChange={(event) => updateDailyDraft(student.id, { notes: event.target.value })} />
                        </div>
                      </div>
                    </div>
                  </div>
                )
              })}
            </div>

            <div className="hidden md:block">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Student</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead>Hours</TableHead>
                    <TableHead>Check in</TableHead>
                    <TableHead>Check out</TableHead>
                    <TableHead>Notes</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {students.map((student) => (
                    <TableRow key={student.id}>
                      <TableCell className="font-medium">{student.name}</TableCell>
                      <TableCell>
                        <Select value={dailyDrafts[student.id]?.status || 'present'} onValueChange={(value) => updateDailyDraft(student.id, { status: value as AttendanceStatus })}>
                          <SelectTrigger className="min-w-[130px]">
                            <SelectValue />
                          </SelectTrigger>
                          <SelectContent>
                            {statusOptions.map((status) => (
                              <SelectItem key={status} value={status}>
                                {status}
                              </SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                      </TableCell>
                      <TableCell>
                        <Input value={dailyDrafts[student.id]?.instructional_hours || '0.00'} onChange={(event) => updateDailyDraft(student.id, { instructional_hours: event.target.value })} />
                      </TableCell>
                      <TableCell>
                        <Input type="time" value={dailyDrafts[student.id]?.check_in_time || ''} onChange={(event) => updateDailyDraft(student.id, { check_in_time: event.target.value })} />
                      </TableCell>
                      <TableCell>
                        <Input type="time" value={dailyDrafts[student.id]?.check_out_time || ''} onChange={(event) => updateDailyDraft(student.id, { check_out_time: event.target.value })} />
                      </TableCell>
                      <TableCell>
                        <Input value={dailyDrafts[student.id]?.notes || ''} onChange={(event) => updateDailyDraft(student.id, { notes: event.target.value })} placeholder="Optional note" />
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Compliance snapshot</CardTitle>
            <CardDescription>Term-ready totals for the currently selected student and school year.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid gap-4 md:grid-cols-2">
              <div className="space-y-2">
                <Label>Student</Label>
                <Select value={selectedStudentId ? String(selectedStudentId) : undefined} onValueChange={(value) => setSelectedStudentId(Number(value))}>
                  <SelectTrigger>
                    <SelectValue placeholder="Select student" />
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
                <Label>School year</Label>
                <Select
                  value={selectedSchoolYearId ? String(selectedSchoolYearId) : undefined}
                  onValueChange={(value) => setSelectedSchoolYearId(Number(value))}
                >
                  <SelectTrigger>
                    <SelectValue placeholder="Select school year" />
                  </SelectTrigger>
                  <SelectContent>
                    {schoolYears.map((schoolYear) => (
                      <SelectItem key={schoolYear.id} value={String(schoolYear.id)}>
                        {schoolYear.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>

            <div className="grid gap-3 sm:grid-cols-2">
              <div className="rounded-md border p-3">
                <p className="text-xs uppercase text-muted-foreground">Present / tardy / excused</p>
                <p className="text-2xl font-semibold">{(summary?.present || 0) + (summary?.tardy || 0) + (summary?.excused || 0)}</p>
              </div>
              <div className="rounded-md border p-3">
                <p className="text-xs uppercase text-muted-foreground">Absent days</p>
                <p className="text-2xl font-semibold">{summary?.absent || 0}</p>
              </div>
            </div>

            <div className="space-y-2">
              <p className="text-sm font-medium">Term summary buckets</p>
              {summary?.buckets.length ? (
                <div className="space-y-2">
                  {summary.buckets.map((bucket) => (
                    <div key={`${bucket.label}-${bucket.start_date}`} className="rounded-md border p-3">
                      <div className="flex items-center justify-between gap-3">
                        <div>
                          <p className="font-medium">{bucket.label}</p>
                          <p className="text-xs text-muted-foreground">
                            {toLocalDate(bucket.start_date).toLocaleDateString()} – {toLocalDate(bucket.end_date).toLocaleDateString()}
                          </p>
                        </div>
                        <Badge variant="secondary">{bucket.attendance_rate.toFixed(1)}%</Badge>
                      </div>
                      <p className="mt-2 text-sm text-muted-foreground">
                        {bucket.total_records} days tracked · {bucket.total_hours} hours
                      </p>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-sm text-muted-foreground">No attendance records yet for this school year.</p>
              )}
            </div>
          </CardContent>
        </Card>
      </div>

      <div className="grid gap-4 xl:grid-cols-[1.1fr_0.9fr]">
        <Card>
          <CardHeader>
            <CardTitle>Attendance calendar</CardTitle>
            <CardDescription>Color-coded monthly view for the selected student.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex items-center justify-between gap-3">
              <Button variant="outline" size="sm" onClick={() => setSelectedMonth((current) => addMonths(current, -1))}>
                <ChevronLeft className="mr-2 h-4 w-4" />
                Previous
              </Button>
              <p className="font-medium">{monthRange.label}</p>
              <Button variant="outline" size="sm" onClick={() => setSelectedMonth((current) => addMonths(current, 1))}>
                Next
                <ChevronRight className="ml-2 h-4 w-4" />
              </Button>
            </div>

            <div className="grid grid-cols-7 gap-2 text-center text-xs font-medium text-muted-foreground">
              {['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'].map((day) => (
                <div key={day}>{day}</div>
              ))}
            </div>
            <div className="grid grid-cols-7 gap-2">
              {monthGrid.map((cell) => {
                const primaryRecord = cell.records[0]
                return (
                  <div
                    key={cell.key}
                    className={`min-h-[88px] rounded-md border p-2 text-xs ${cell.inMonth ? 'bg-card' : 'bg-muted/50 text-muted-foreground'} ${primaryRecord ? statusDayClasses(primaryRecord.status) : ''}`}
                  >
                    <div className="flex items-center justify-between">
                      <span className="font-medium">{cell.key.slice(-2)}</span>
                      {primaryRecord ? <Badge variant={statusBadgeVariant(primaryRecord.status)}>{primaryRecord.status}</Badge> : null}
                    </div>
                    {primaryRecord ? (
                      <div className="mt-2 space-y-1">
                        <p>{primaryRecord.instructional_hours} hrs</p>
                        {primaryRecord.excuse ? <p className="truncate">Excuse: {primaryRecord.excuse.reason}</p> : null}
                      </div>
                    ) : null}
                  </div>
                )
              })}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Hourly instructional log</CardTitle>
            <CardDescription>Track state-ready instructional time for a single student and date.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <Label>Student</Label>
              <Select value={hoursForm.student_id ? String(hoursForm.student_id) : undefined} onValueChange={(value) => setHoursForm((current) => ({ ...current, student_id: Number(value) }))}>
                <SelectTrigger>
                  <SelectValue placeholder="Select student" />
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
            <div className="grid gap-4 md:grid-cols-2">
              <div className="space-y-2">
                <Label>Date</Label>
                <Input type="date" value={hoursForm.date} onChange={(event) => setHoursForm((current) => ({ ...current, date: event.target.value }))} />
              </div>
              <div className="space-y-2">
                <Label>Hours</Label>
                <Input value={hoursForm.instructional_hours} onChange={(event) => setHoursForm((current) => ({ ...current, instructional_hours: event.target.value }))} />
              </div>
              <div className="space-y-2">
                <Label>Check in</Label>
                <Input type="time" value={hoursForm.check_in_time} onChange={(event) => setHoursForm((current) => ({ ...current, check_in_time: event.target.value }))} />
              </div>
              <div className="space-y-2">
                <Label>Check out</Label>
                <Input type="time" value={hoursForm.check_out_time} onChange={(event) => setHoursForm((current) => ({ ...current, check_out_time: event.target.value }))} />
              </div>
            </div>
            <div className="space-y-2">
              <Label>Notes</Label>
              <Textarea value={hoursForm.notes} onChange={(event) => setHoursForm((current) => ({ ...current, notes: event.target.value }))} placeholder="What instructional work was completed?" />
            </div>
            <Button onClick={() => void saveHours()} disabled={saving || !hoursForm.student_id}>
              Log hours
            </Button>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Excuse management</CardTitle>
          <CardDescription>Attach documents, approve excuses, and keep the audit trail complete.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-4 lg:grid-cols-[1fr_0.8fr]">
            <div className="space-y-4">
              <div className="space-y-2">
                <Label>Attendance record</Label>
                <Select value={excuseRecordId ? String(excuseRecordId) : undefined} onValueChange={(value) => setExcuseRecordId(Number(value))}>
                  <SelectTrigger>
                    <SelectValue placeholder="Select an absent, tardy, or excused record" />
                  </SelectTrigger>
                  <SelectContent>
                    {excuseCandidates.map((record) => (
                      <SelectItem key={record.id} value={String(record.id)}>
                        {record.student?.name || `Student ${record.student_id}`} · {record.date} · {record.status}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label>Reason</Label>
                <Textarea value={excuseReason} onChange={(event) => setExcuseReason(event.target.value)} placeholder="Doctor visit, family emergency, court filing, etc." />
              </div>
              <div className="space-y-2">
                <Label>Document</Label>
                <Input type="file" onChange={(event) => setExcuseFile(event.target.files?.[0] || null)} />
              </div>
              <Button onClick={() => void saveExcuse()} disabled={saving || !excuseRecordId || !excuseReason.trim()}>
                <Paperclip className="mr-2 h-4 w-4" />
                Save excuse
              </Button>
            </div>

            <div className="space-y-3">
              {excuseCandidates.filter((record) => record.excuse).length ? (
                excuseCandidates
                  .filter((record) => record.excuse)
                  .map((record) => (
                    <div key={record.id} className="rounded-md border p-3">
                      <div className="flex items-start justify-between gap-3">
                        <div>
                          <p className="font-medium">{record.student?.name || `Student ${record.student_id}`} · {record.date}</p>
                          <p className="text-sm text-muted-foreground">{record.excuse?.reason}</p>
                        </div>
                        <Badge variant={record.excuse?.approved_at ? 'secondary' : 'outline'}>
                          {record.excuse?.approved_at ? 'Approved' : 'Pending'}
                        </Badge>
                      </div>
                      <div className="mt-3 flex flex-wrap gap-2">
                        {record.excuse?.document_url ? (
                          <a href={record.excuse.document_url} className="inline-flex items-center rounded-md border px-3 py-1 text-sm hover:bg-muted" target="_blank" rel="noreferrer">
                            View document
                          </a>
                        ) : null}
                        {!record.excuse?.approved_at ? (
                          <Button size="sm" variant="outline" onClick={() => void approveExcuse(record.excuse!.id)} disabled={saving}>
                            <ShieldCheck className="mr-2 h-4 w-4" />
                            Approve
                          </Button>
                        ) : null}
                      </div>
                    </div>
                  ))
              ) : (
                <p className="text-sm text-muted-foreground">No excuses attached yet for the current month.</p>
              )}
            </div>
          </div>
        </CardContent>
      </Card>
      </div>
    </PullToRefresh>
  )
}
