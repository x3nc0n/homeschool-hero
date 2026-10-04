import { useCallback, useEffect, useMemo, useState } from 'react'
import { ChevronLeft, ChevronRight, UserCheck } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { api } from '@/lib/api'
import type { AttendanceRecord, AttendanceStateProfile, AttendanceStateProfileProgress, AttendanceSummary, SchoolYear, Student } from '@/types/api'
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
import { Textarea } from '@/components/ui/textarea'

interface DailyDraft {
  is_instructional_day: boolean
  instructional_hours: string
  notes: string
}

function localDateString(date: Date) {
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`
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

function monthBounds(monthKey: string, locale: string) {
  const start = startOfMonth(monthKey)
  const end = new Date(start.getFullYear(), start.getMonth() + 1, 0)
  return {
    start: localDateString(start),
    end: localDateString(end),
    label: new Intl.DateTimeFormat(locale, { month: 'long', year: 'numeric' }).format(start),
  }
}

function emptyDailyDraft(record?: AttendanceRecord): DailyDraft {
  return {
    is_instructional_day: record?.is_instructional_day ?? false,
    instructional_hours: record?.instructional_hours ?? '',
    notes: record?.notes ?? '',
  }
}

function formatCount(value: number | string | null | undefined, locale: string) {
  const numericValue = typeof value === 'number' ? value : Number(value ?? 0)
  return new Intl.NumberFormat(locale, { maximumFractionDigits: 2 }).format(Number.isFinite(numericValue) ? numericValue : 0)
}

function ProfileProgress({
  progress,
  instructionalDays,
  totalHours,
  locale,
  t,
}: {
  progress: AttendanceStateProfileProgress
  instructionalDays: number
  totalHours: string | null
  locale: string
  t: (key: string, options?: Record<string, unknown>) => string
}) {
  const hasDayRequirement = progress.required_days != null
  const hasHourRequirement = progress.required_hours != null
  const daysRemaining = Math.max(0, progress.days_remaining ?? (progress.required_days ?? 0) - instructionalDays)
  const parsedHours = Number(totalHours ?? 0)
  const completedHours = Number.isFinite(parsedHours) ? parsedHours : 0
  const parsedHoursRemaining = Number(progress.hours_remaining)
  const hoursRemaining = Math.max(
    0,
    progress.hours_remaining != null && Number.isFinite(parsedHoursRemaining)
      ? parsedHoursRemaining
      : (progress.required_hours ?? 0) - completedHours,
  )
  const dayPercent = progress.required_days
    ? Math.min(100, (instructionalDays / progress.required_days) * 100)
    : 100
  const hourPercent = progress.required_hours
    ? Math.min(100, (completedHours / progress.required_hours) * 100)
    : 100

  return (
    <Card>
      <CardHeader>
        <CardTitle>{t('attendance.progress.title')}</CardTitle>
        <CardDescription>{t('attendance.progress.description')}</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {hasDayRequirement && progress.required_days === 0 ? (
          <p className="text-sm text-muted-foreground">{t('attendance.progress.zeroDays')}</p>
        ) : null}
        {hasDayRequirement && progress.required_days !== 0 ? (
          <div className="space-y-2">
            <div className="flex flex-wrap items-center justify-between gap-2 text-sm">
              <span>{t('attendance.progress.days', { completed: formatCount(instructionalDays, locale), required: formatCount(progress.required_days, locale) })}</span>
              <span className="text-muted-foreground">
                {daysRemaining ? t('attendance.progress.daysRemaining', { count: formatCount(daysRemaining, locale) }) : t('attendance.progress.daysComplete')}
              </span>
            </div>
            <div
              role="progressbar"
              aria-label={t('attendance.progress.days', { completed: formatCount(instructionalDays, locale), required: formatCount(progress.required_days, locale) })}
              aria-valuemin={0}
              aria-valuemax={progress.required_days ?? undefined}
              aria-valuenow={Math.min(instructionalDays, progress.required_days ?? 0)}
              className="h-2 overflow-hidden rounded-full bg-muted"
            >
              <div className="h-full rounded-full bg-primary transition-[width]" style={{ width: `${dayPercent}%` }} />
            </div>
          </div>
        ) : null}
        {hasHourRequirement && progress.required_hours === 0 ? (
          <p className="text-sm text-muted-foreground">{t('attendance.progress.zeroHours')}</p>
        ) : null}
        {hasHourRequirement && progress.required_hours !== 0 ? (
          <div className="space-y-2">
            <div className="flex flex-wrap items-center justify-between gap-2 text-sm">
              <span>{t('attendance.progress.hours', { completed: formatCount(totalHours, locale), required: formatCount(progress.required_hours, locale) })}</span>
              <span className="text-muted-foreground">
                {hoursRemaining ? t('attendance.progress.hoursRemaining', { count: formatCount(hoursRemaining, locale) }) : t('attendance.progress.hoursComplete')}
              </span>
            </div>
            <div
              role="progressbar"
              aria-label={t('attendance.progress.hours', { completed: formatCount(totalHours, locale), required: formatCount(progress.required_hours, locale) })}
              aria-valuemin={0}
              aria-valuemax={progress.required_hours ?? undefined}
              aria-valuenow={Math.min(completedHours, progress.required_hours ?? 0)}
              className="h-2 overflow-hidden rounded-full bg-muted"
            >
              <div className="h-full rounded-full bg-primary transition-[width]" style={{ width: `${hourPercent}%` }} />
            </div>
          </div>
        ) : null}
        {!hasDayRequirement && !hasHourRequirement ? (
          <p className="text-sm text-muted-foreground">{t('attendance.progress.none')}</p>
        ) : null}
      </CardContent>
    </Card>
  )
}

export function AttendancePage() {
  const { t, i18n } = useTranslation()
  const today = localDateString(new Date())
  const locale = i18n.resolvedLanguage || i18n.language
  const [students, setStudents] = useState<Student[]>([])
  const [schoolYears, setSchoolYears] = useState<SchoolYear[]>([])
  const [attendanceRecords, setAttendanceRecords] = useState<AttendanceRecord[]>([])
  const [summary, setSummary] = useState<AttendanceSummary | null>(null)
  const [stateProfile, setStateProfile] = useState<AttendanceStateProfile | null>(null)
  const [selectedDate, setSelectedDate] = useState(today)
  const [selectedMonth, setSelectedMonth] = useState(today.slice(0, 7))
  const [selectedStudentId, setSelectedStudentId] = useState<number | null>(null)
  const [selectedSchoolYearId, setSelectedSchoolYearId] = useState<number | null>(null)
  const [dailyDrafts, setDailyDrafts] = useState<Record<number, DailyDraft>>({})
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [statusMessage, setStatusMessage] = useState('')

  const selectedStudent = useMemo(
    () => students.find((student) => student.id === selectedStudentId) || null,
    [selectedStudentId, students],
  )
  const monthRange = useMemo(() => monthBounds(selectedMonth, locale), [locale, selectedMonth])
  const progress = summary?.state_profile_progress ?? null
  const showHours = stateProfile?.show_hours_ui ?? (progress?.required_hours != null && progress.required_hours > 0)
  const hasApplicableMinimum = progress && (progress.required_days != null || progress.required_hours != null)

  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const [studentData, schoolYearData, records, profiles, familyState] = await Promise.all([
        api.listStudents(),
        api.listSchoolYears(),
        api.listAttendance({ date_from: monthRange.start, date_to: monthRange.end }),
        api.listAttendanceStateProfiles(),
        api.getFamilyComplianceState(),
      ])
      const resolvedStudentId =
        selectedStudentId && studentData.some((student) => student.id === selectedStudentId)
          ? selectedStudentId
          : studentData[0]?.id ?? null
      const resolvedSchoolYearId =
        selectedSchoolYearId && schoolYearData.some((schoolYear) => schoolYear.id === selectedSchoolYearId)
          ? selectedSchoolYearId
          : schoolYearData.find((schoolYear) => schoolYear.is_active)?.id ?? schoolYearData[0]?.id ?? null
      const summaryData = resolvedStudentId && resolvedSchoolYearId
        ? await api.getAttendanceSummary(resolvedStudentId, 'year', resolvedSchoolYearId)
        : null

      setStudents(studentData)
      setSchoolYears(schoolYearData)
      setAttendanceRecords(records)
      setStateProfile(
        profiles.find((profile) => profile.state_code === familyState?.state_code) ?? null,
      )
      setSelectedStudentId(resolvedStudentId)
      setSelectedSchoolYearId(resolvedSchoolYearId)
      setSummary(summaryData)
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : t('attendance.errors.load'))
    } finally {
      setLoading(false)
    }
  }, [monthRange.end, monthRange.start, selectedSchoolYearId, selectedStudentId, t])

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

  const recordsByDate = useMemo(
    () => attendanceRecords
      .filter((record) => record.student_id === selectedStudentId)
      .reduce<Record<string, AttendanceRecord>>((accumulator, record) => {
        accumulator[record.date] = record
        return accumulator
      }, {}),
    [attendanceRecords, selectedStudentId],
  )
  const monthGrid = useMemo(() => {
    const firstDay = startOfMonth(selectedMonth)
    const start = new Date(firstDay)
    start.setDate(1 - firstDay.getDay())
    return Array.from({ length: 42 }, (_, index) => {
      const current = new Date(start)
      current.setDate(start.getDate() + index)
      const key = localDateString(current)
      return { key, inMonth: monthKeyFromDate(key) === selectedMonth, record: recordsByDate[key] }
    })
  }, [recordsByDate, selectedMonth])

  const updateDailyDraft = (studentId: number, patch: Partial<DailyDraft>) => {
    setDailyDrafts((current) => ({
      ...current,
      [studentId]: { ...current[studentId], ...patch },
    }))
  }

  const saveDailyAttendance = async () => {
    if (!students.length) return
    setSaving(true)
    setError('')
    setStatusMessage('')
    try {
      await api.recordDailyAttendance({
        date: selectedDate,
        records: students.map((student) => {
          const draft = dailyDrafts[student.id] ?? emptyDailyDraft()
          return {
            student_id: student.id,
            is_instructional_day: draft.is_instructional_day,
            instructional_hours: showHours ? draft.instructional_hours || null : undefined,
            notes: draft.notes || null,
          }
        }),
      })
      setStatusMessage(t('attendance.messages.saved'))
      await load()
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : t('attendance.errors.save'))
    } finally {
      setSaving(false)
    }
  }

  if (loading) return <LoadingState message={t('attendance.loading')} />
  if (error) return <ErrorState message={error} onRetry={() => void load()} />
  if (!students.length) {
    return <EmptyState title={t('attendance.students.emptyTitle')} description={t('attendance.students.emptyDescription')} />
  }

  return (
    <PullToRefresh onRefresh={load}>
      <div className="space-y-4">
        {statusMessage ? (
          <div role="status" aria-live="polite" className="rounded-md border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-900">
            {statusMessage}
          </div>
        ) : null}

        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          <Card>
            <CardHeader>
              <CardDescription>{t('attendance.summary.title')}</CardDescription>
              <CardTitle>{selectedStudent?.name || '—'}</CardTitle>
            </CardHeader>
          </Card>
          <Card>
            <CardHeader>
              <CardDescription>{t('attendance.summary.instructionalDays')}</CardDescription>
              <CardTitle>{formatCount(summary?.instructional_days, locale)}</CardTitle>
            </CardHeader>
          </Card>
          <Card>
            <CardHeader>
              <CardDescription>{t('attendance.summary.nonInstructionalDays')}</CardDescription>
              <CardTitle>{formatCount(summary?.non_instructional_days, locale)}</CardTitle>
            </CardHeader>
          </Card>
          {showHours ? (
            <Card>
              <CardHeader>
                <CardDescription>{t('attendance.summary.totalHours')}</CardDescription>
                <CardTitle>{formatCount(summary?.total_hours, locale)}</CardTitle>
              </CardHeader>
            </Card>
          ) : null}
        </div>

        <div className="grid gap-4 xl:grid-cols-[1.2fr_0.8fr]">
          <Card>
            <CardHeader>
              <CardTitle>{t('attendance.title')}</CardTitle>
              <CardDescription>{t('attendance.description')}</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex flex-col gap-3 sm:flex-row sm:flex-wrap sm:items-end">
                <div className="w-full space-y-2 sm:w-auto">
                  <Label htmlFor="attendance-date">{t('attendance.date')}</Label>
                  <Input
                    id="attendance-date"
                    type="date"
                    value={selectedDate}
                    onChange={(event) => {
                      const nextDate = event.target.value
                      setSelectedDate(nextDate)
                      if (nextDate) setSelectedMonth(monthKeyFromDate(nextDate))
                    }}
                  />
                </div>
                <Button className="w-full sm:w-auto" onClick={() => void saveDailyAttendance()} disabled={saving}>
                  <UserCheck className="mr-2 h-4 w-4" aria-hidden="true" />
                  {saving ? t('attendance.saving') : t('attendance.saveDay')}
                </Button>
              </div>

              <div className="space-y-3">
                {students.map((student) => {
                  const draft = dailyDrafts[student.id] ?? emptyDailyDraft()
                  const hoursId = `attendance-hours-${student.id}`
                  const notesId = `attendance-notes-${student.id}`
                  return (
                    <div key={student.id} className="rounded-lg border p-4">
                      <div className="flex flex-wrap items-center justify-between gap-3">
                        <h3 className="font-medium">{student.name}</h3>
                        <Badge variant={draft.is_instructional_day ? 'default' : 'secondary'}>
                          {draft.is_instructional_day ? t('attendance.instructional') : t('attendance.nonInstructional')}
                        </Badge>
                      </div>
                      <label className="mt-3 flex min-h-11 cursor-pointer items-center gap-3 rounded-md border px-3 py-2">
                        <input
                          type="checkbox"
                          checked={draft.is_instructional_day}
                          aria-label={t('attendance.instructionalDayFor', { student: student.name })}
                          onChange={(event) => updateDailyDraft(student.id, { is_instructional_day: event.target.checked })}
                          className="h-5 w-5 accent-primary"
                        />
                        <span className="font-medium">{t('attendance.instructionalDay')}</span>
                      </label>
                      <div className={`mt-3 grid gap-3 ${showHours ? 'sm:grid-cols-2' : ''}`}>
                        {showHours ? (
                          <div className="space-y-2">
                            <Label htmlFor={hoursId}>{t('attendance.hours')}</Label>
                            <Input
                              id={hoursId}
                              type="number"
                              min="0"
                              step="0.25"
                              inputMode="decimal"
                              value={draft.instructional_hours}
                              onChange={(event) => updateDailyDraft(student.id, { instructional_hours: event.target.value })}
                            />
                            <p className="text-xs text-muted-foreground">{t('attendance.optionalHours')}</p>
                          </div>
                        ) : null}
                        <div className="space-y-2">
                          <Label htmlFor={notesId}>{t('attendance.notes')}</Label>
                          <Textarea
                            id={notesId}
                            value={draft.notes}
                            placeholder={t('attendance.optionalNote')}
                            onChange={(event) => updateDailyDraft(student.id, { notes: event.target.value })}
                          />
                        </div>
                      </div>
                    </div>
                  )
                })}
              </div>
            </CardContent>
          </Card>

          <div className="space-y-4">
            <Card>
              <CardHeader>
                <CardTitle>{t('attendance.schoolYear')}</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="space-y-2">
                  <Label htmlFor="attendance-student">{t('attendance.student')}</Label>
                  <Select value={selectedStudentId ? String(selectedStudentId) : undefined} onValueChange={(value) => setSelectedStudentId(Number(value))}>
                    <SelectTrigger id="attendance-student">
                      <SelectValue placeholder={t('attendance.selectStudent')} />
                    </SelectTrigger>
                    <SelectContent>
                      {students.map((student) => (
                        <SelectItem key={student.id} value={String(student.id)}>{student.name}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-2">
                  <Label htmlFor="attendance-school-year">{t('attendance.schoolYear')}</Label>
                  <Select
                    value={selectedSchoolYearId ? String(selectedSchoolYearId) : undefined}
                    onValueChange={(value) => setSelectedSchoolYearId(Number(value))}
                  >
                    <SelectTrigger id="attendance-school-year">
                      <SelectValue placeholder={t('attendance.selectSchoolYear')} />
                    </SelectTrigger>
                    <SelectContent>
                      {schoolYears.map((schoolYear) => (
                        <SelectItem key={schoolYear.id} value={String(schoolYear.id)}>{schoolYear.name}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              </CardContent>
            </Card>

            {hasApplicableMinimum ? (
              <ProfileProgress
                progress={progress}
                instructionalDays={summary?.instructional_days ?? 0}
                totalHours={summary?.total_hours ?? null}
                locale={locale}
                t={t}
              />
            ) : null}
            {!selectedSchoolYearId ? (
              <p className="rounded-md border p-3 text-sm text-muted-foreground">{t('attendance.progress.noSchoolYear')}</p>
            ) : null}
          </div>
        </div>

        <Card>
          <CardHeader>
            <CardTitle>{t('attendance.calendar.title')}</CardTitle>
            <CardDescription>{t('attendance.calendar.description')}</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex items-center justify-between gap-3">
              <Button variant="outline" size="sm" aria-label={t('attendance.calendar.previous')} onClick={() => setSelectedMonth((current) => addMonths(current, -1))}>
                <ChevronLeft className="mr-2 h-4 w-4" aria-hidden="true" />
                {t('attendance.calendar.previous')}
              </Button>
              <p className="font-medium" aria-live="polite">{monthRange.label}</p>
              <Button variant="outline" size="sm" aria-label={t('attendance.calendar.next')} onClick={() => setSelectedMonth((current) => addMonths(current, 1))}>
                {t('attendance.calendar.next')}
                <ChevronRight className="ml-2 h-4 w-4" aria-hidden="true" />
              </Button>
            </div>

            <div className="grid grid-cols-7 gap-2 text-center text-xs font-medium text-muted-foreground" aria-hidden="true">
              {(t('attendance.weekdays', { returnObjects: true }) as string[]).map((day) => <div key={day}>{day}</div>)}
            </div>
            <div className="grid grid-cols-7 gap-2">
              {monthGrid.map((cell) => {
                const dayState = cell.record
                  ? cell.record.is_instructional_day
                    ? t('attendance.calendar.instructional')
                    : t('attendance.calendar.nonInstructional')
                  : t('attendance.calendar.noRecord')
                const calendarLabel = `${cell.key}: ${dayState}`
                const calendarClass = cell.record
                  ? cell.record.is_instructional_day
                    ? 'border-emerald-500 bg-emerald-100 text-emerald-900'
                    : 'border-slate-300 bg-slate-100 text-slate-700'
                  : ''
                return (
                  <div
                    key={cell.key}
                    aria-label={calendarLabel}
                    className={`min-h-[76px] rounded-md border p-2 text-xs ${cell.inMonth ? 'bg-card' : 'bg-muted/50 text-muted-foreground'} ${calendarClass}`}
                  >
                    <div className="flex items-center justify-between gap-1">
                      <span className="font-medium">{Number(cell.key.slice(-2))}</span>
                      {cell.record ? (
                        <Badge variant={cell.record.is_instructional_day ? 'default' : 'secondary'}>
                          {cell.record.is_instructional_day ? t('attendance.instructional') : t('attendance.nonInstructional')}
                        </Badge>
                      ) : null}
                    </div>
                    {cell.record?.instructional_hours ? (
                      <p className="mt-2">{t('attendance.calendar.hours', { hours: formatCount(cell.record.instructional_hours, locale) })}</p>
                    ) : null}
                  </div>
                )
              })}
            </div>
          </CardContent>
        </Card>
      </div>
    </PullToRefresh>
  )
}
