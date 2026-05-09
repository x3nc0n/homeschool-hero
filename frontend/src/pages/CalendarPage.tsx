import { useEffect, useMemo, useState } from 'react'
import { Pencil, Plus, Trash2 } from 'lucide-react'
import { api } from '@/lib/api'
import type {
  CalendarEvent,
  CalendarEventType,
  InstructionalDayCount,
  SchoolYear,
  SchoolYearDetail,
  TermType,
} from '@/types/api'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { EmptyState } from '@/components/common/EmptyState'
import { ErrorState } from '@/components/common/ErrorState'
import { LoadingState } from '@/components/common/LoadingState'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Textarea } from '@/components/ui/textarea'
import { Badge } from '@/components/ui/badge'

const termTypeOptions: TermType[] = ['semester', 'quarter', 'trimester', 'custom']
const eventTypeOptions: CalendarEventType[] = ['holiday', 'closure', 'custom']
const monthNames = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December']

type SchoolYearForm = {
  name: string
  start_date: string
  end_date: string
  is_active: boolean
}

type TermForm = {
  name: string
  start_date: string
  end_date: string
  term_type: TermType
}

type GradingPeriodForm = {
  term_id: string
  name: string
  start_date: string
  end_date: string
}

type EventForm = {
  date: string
  event_type: CalendarEventType
  name: string
  is_instructional_day: boolean
  notes: string
}

function parseDateParts(value: string) {
  const [year, month, day] = value.split('-').map(Number)
  return { year, month, day }
}

function toLocalDate(value: string) {
  const { year, month, day } = parseDateParts(value)
  return new Date(year, month - 1, day)
}

function formatDateLabel(value: string) {
  return toLocalDate(value).toLocaleDateString(undefined, {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  })
}

function getMonthKey(value: string) {
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

function summarizeType(value: string) {
  return value
    .split('_')
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(' ')
}

function emptySchoolYearForm(): SchoolYearForm {
  return { name: '', start_date: '', end_date: '', is_active: false }
}

function emptyTermForm(): TermForm {
  return { name: '', start_date: '', end_date: '', term_type: 'semester' }
}

function emptyGradingPeriodForm(termId = ''): GradingPeriodForm {
  return { term_id: termId, name: '', start_date: '', end_date: '' }
}

function emptyEventForm(): EventForm {
  return { date: '', event_type: 'holiday', name: '', is_instructional_day: false, notes: '' }
}

export function CalendarPage() {
  const [schoolYears, setSchoolYears] = useState<SchoolYear[]>([])
  const [selectedSchoolYearId, setSelectedSchoolYearId] = useState<number | null>(null)
  const [selectedSchoolYear, setSelectedSchoolYear] = useState<SchoolYearDetail | null>(null)
  const [dayCount, setDayCount] = useState<InstructionalDayCount | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [editingSchoolYearId, setEditingSchoolYearId] = useState<number | null>(null)
  const [editingTermId, setEditingTermId] = useState<number | null>(null)
  const [editingGradingPeriodId, setEditingGradingPeriodId] = useState<number | null>(null)
  const [editingEventId, setEditingEventId] = useState<number | null>(null)
  const [schoolYearForm, setSchoolYearForm] = useState<SchoolYearForm>(emptySchoolYearForm)
  const [termForm, setTermForm] = useState<TermForm>(emptyTermForm)
  const [gradingPeriodForm, setGradingPeriodForm] = useState<GradingPeriodForm>(emptyGradingPeriodForm())
  const [eventForm, setEventForm] = useState<EventForm>(emptyEventForm)
  const [calendarMonth, setCalendarMonth] = useState('')

  const loadSchoolYears = async (preferredId?: number | null) => {
    const years = await api.listSchoolYears()
    setSchoolYears(years)
    const activeId = years.find((schoolYear) => schoolYear.is_active)?.id ?? years[0]?.id ?? null
    const nextId = preferredId && years.some((schoolYear) => schoolYear.id === preferredId) ? preferredId : activeId
    setSelectedSchoolYearId(nextId)
    return { years, nextId }
  }

  const loadDetail = async (schoolYearId: number | null) => {
    if (!schoolYearId) {
      setSelectedSchoolYear(null)
      setDayCount(null)
      setCalendarMonth('')
      return
    }
    const [detail, instructionalDays] = await Promise.all([api.getSchoolYear(schoolYearId), api.getInstructionalDays(schoolYearId)])
    setSelectedSchoolYear(detail)
    setDayCount(instructionalDays)
    setCalendarMonth((current) => current || getMonthKey(detail.start_date))
    setGradingPeriodForm((current) => ({
      ...current,
      term_id: current.term_id || (detail.terms[0] ? String(detail.terms[0].id) : ''),
    }))
  }

  const load = async (preferredId?: number | null) => {
    setLoading(true)
    setError('')
    try {
      const { nextId } = await loadSchoolYears(preferredId)
      await loadDetail(nextId)
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : 'Unable to load calendar')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void load()
  }, [])

  useEffect(() => {
    if (!selectedSchoolYearId) return
    if (loading) return
    void loadDetail(selectedSchoolYearId).catch((detailError) => {
      setError(detailError instanceof Error ? detailError.message : 'Unable to load school year details')
    })
  }, [loading, selectedSchoolYearId])

  const resetSchoolYearForm = () => {
    setEditingSchoolYearId(null)
    setSchoolYearForm(emptySchoolYearForm())
  }

  const resetTermForm = () => {
    setEditingTermId(null)
    setTermForm(emptyTermForm())
  }

  const resetGradingPeriodForm = () => {
    setEditingGradingPeriodId(null)
    setGradingPeriodForm(emptyGradingPeriodForm(selectedSchoolYear?.terms[0] ? String(selectedSchoolYear.terms[0].id) : ''))
  }

  const resetEventForm = () => {
    setEditingEventId(null)
    setEventForm(emptyEventForm())
  }

  const saveSchoolYear = async () => {
    const payload = {
      name: schoolYearForm.name.trim(),
      start_date: schoolYearForm.start_date,
      end_date: schoolYearForm.end_date,
      is_active: schoolYearForm.is_active,
    }
    if (!payload.name || !payload.start_date || !payload.end_date) return
    if (editingSchoolYearId) {
      await api.updateSchoolYear(editingSchoolYearId, payload)
      await load(editingSchoolYearId)
    } else {
      const created = await api.createSchoolYear(payload)
      await load(created.id)
    }
    resetSchoolYearForm()
  }

  const saveTerm = async () => {
    if (!selectedSchoolYearId || !termForm.name.trim() || !termForm.start_date || !termForm.end_date) return
    const payload = {
      name: termForm.name.trim(),
      start_date: termForm.start_date,
      end_date: termForm.end_date,
      term_type: termForm.term_type,
    }
    if (editingTermId) {
      await api.updateTerm(editingTermId, payload)
    } else {
      await api.createTerm({ ...payload, school_year_id: selectedSchoolYearId })
    }
    await load(selectedSchoolYearId)
    resetTermForm()
  }

  const saveGradingPeriod = async () => {
    if (!selectedSchoolYearId || !gradingPeriodForm.term_id || !gradingPeriodForm.name.trim() || !gradingPeriodForm.start_date || !gradingPeriodForm.end_date) return
    const payload = {
      name: gradingPeriodForm.name.trim(),
      start_date: gradingPeriodForm.start_date,
      end_date: gradingPeriodForm.end_date,
    }
    if (editingGradingPeriodId) {
      await api.updateGradingPeriod(editingGradingPeriodId, payload)
    } else {
      await api.createGradingPeriod({ ...payload, term_id: Number(gradingPeriodForm.term_id) })
    }
    await load(selectedSchoolYearId)
    resetGradingPeriodForm()
  }

  const saveEvent = async () => {
    if (!selectedSchoolYearId || !eventForm.date || !eventForm.name.trim()) return
    const payload = {
      date: eventForm.date,
      event_type: eventForm.event_type,
      name: eventForm.name.trim(),
      is_instructional_day: eventForm.is_instructional_day,
      notes: eventForm.notes.trim() || null,
    }
    if (editingEventId) {
      await api.updateCalendarEvent(editingEventId, payload)
    } else {
      await api.createCalendarEvent({ ...payload, school_year_id: selectedSchoolYearId })
    }
    await load(selectedSchoolYearId)
    resetEventForm()
  }

  const monthEvents = useMemo(() => {
    if (!selectedSchoolYear) return []
    return selectedSchoolYear.calendar_events.filter((event) => getMonthKey(event.date) === calendarMonth)
  }, [calendarMonth, selectedSchoolYear])

  const eventsByDate = useMemo(() => {
    return monthEvents.reduce<Record<string, CalendarEvent[]>>((accumulator, event) => {
      accumulator[event.date] = [...(accumulator[event.date] || []), event]
      return accumulator
    }, {})
  }, [monthEvents])

  const monthGrid = useMemo(() => {
    if (!calendarMonth) return []
    const firstDay = startOfMonth(calendarMonth)
    const start = new Date(firstDay)
    start.setDate(1 - firstDay.getDay())
    return Array.from({ length: 42 }, (_, index) => {
      const current = new Date(start)
      current.setDate(start.getDate() + index)
      const key = `${current.getFullYear()}-${String(current.getMonth() + 1).padStart(2, '0')}-${String(current.getDate()).padStart(2, '0')}`
      return {
        key,
        date: current,
        inMonth: getMonthKey(key) === calendarMonth,
        events: eventsByDate[key] || [],
      }
    })
  }, [calendarMonth, eventsByDate])

  if (loading) return <LoadingState message="Loading academic calendar…" />
  if (error) return <ErrorState message={error} onRetry={() => void load(selectedSchoolYearId)} />

  return (
    <div className="space-y-4">
      <div className="grid gap-4 xl:grid-cols-[1.1fr_0.9fr]">
        <Card>
          <CardHeader>
            <CardTitle>{editingSchoolYearId ? 'Edit school year' : 'Create school year'}</CardTitle>
            <CardDescription>Track academic years and choose which one is active for the family.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid gap-4 md:grid-cols-2">
              <div className="space-y-2 md:col-span-2">
                <Label>Name</Label>
                <Input
                  value={schoolYearForm.name}
                  onChange={(event) => setSchoolYearForm((current) => ({ ...current, name: event.target.value }))}
                  placeholder="2025-2026"
                />
              </div>
              <div className="space-y-2">
                <Label>Start date</Label>
                <Input
                  type="date"
                  value={schoolYearForm.start_date}
                  onChange={(event) => setSchoolYearForm((current) => ({ ...current, start_date: event.target.value }))}
                />
              </div>
              <div className="space-y-2">
                <Label>End date</Label>
                <Input
                  type="date"
                  value={schoolYearForm.end_date}
                  onChange={(event) => setSchoolYearForm((current) => ({ ...current, end_date: event.target.value }))}
                />
              </div>
            </div>
            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={schoolYearForm.is_active}
                onChange={(event) => setSchoolYearForm((current) => ({ ...current, is_active: event.target.checked }))}
              />
              Make this the active school year
            </label>
            <div className="flex flex-wrap gap-2">
              <Button onClick={() => void saveSchoolYear()}>
                <Plus className="mr-2 h-4 w-4" />
                {editingSchoolYearId ? 'Update' : 'Create'} school year
              </Button>
              {editingSchoolYearId ? (
                <Button variant="outline" onClick={resetSchoolYearForm}>
                  Cancel edit
                </Button>
              ) : null}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>School years</CardTitle>
            <CardDescription>Choose a school year to manage terms, grading periods, and holidays.</CardDescription>
          </CardHeader>
          <CardContent>
            {schoolYears.length ? (
              <div className="space-y-2">
                {schoolYears.map((schoolYear) => (
                  <div
                    key={schoolYear.id}
                    className={`rounded-lg border p-3 ${selectedSchoolYearId === schoolYear.id ? 'border-primary bg-primary/5' : ''}`}
                  >
                    <div className="flex flex-wrap items-start justify-between gap-2">
                      <button
                        type="button"
                        className="text-left"
                        onClick={() => {
                          setSelectedSchoolYearId(schoolYear.id)
                          setCalendarMonth(getMonthKey(schoolYear.start_date))
                        }}
                      >
                        <p className="font-semibold">{schoolYear.name}</p>
                        <p className="text-xs text-muted-foreground">
                          {formatDateLabel(schoolYear.start_date)} – {formatDateLabel(schoolYear.end_date)}
                        </p>
                      </button>
                      {schoolYear.is_active ? <Badge>Active</Badge> : <Badge variant="secondary">Inactive</Badge>}
                    </div>
                    <div className="mt-3 flex flex-wrap gap-2">
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => {
                          setEditingSchoolYearId(schoolYear.id)
                          setSchoolYearForm({
                            name: schoolYear.name,
                            start_date: schoolYear.start_date,
                            end_date: schoolYear.end_date,
                            is_active: schoolYear.is_active,
                          })
                        }}
                      >
                        <Pencil className="mr-2 h-3.5 w-3.5" />
                        Edit
                      </Button>
                      {!schoolYear.is_active ? (
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() =>
                            void api
                              .updateSchoolYear(schoolYear.id, {
                                name: schoolYear.name,
                                start_date: schoolYear.start_date,
                                end_date: schoolYear.end_date,
                                is_active: true,
                              })
                              .then(() => load(schoolYear.id))
                          }
                        >
                          Set active
                        </Button>
                      ) : null}
                      <Button size="sm" variant="destructive" onClick={() => void api.deleteSchoolYear(schoolYear.id).then(() => load())}>
                        <Trash2 className="mr-2 h-3.5 w-3.5" />
                        Delete
                      </Button>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <EmptyState title="No school years yet" description="Create your first school year to start organizing terms and holidays." />
            )}
          </CardContent>
        </Card>
      </div>

      {selectedSchoolYear ? (
        <>
          <div className="grid gap-4 md:grid-cols-4">
            <Card>
              <CardHeader>
                <CardDescription>Instructional days</CardDescription>
                <CardTitle>{dayCount?.instructional_days ?? 0}</CardTitle>
              </CardHeader>
            </Card>
            <Card>
              <CardHeader>
                <CardDescription>Weekday baseline</CardDescription>
                <CardTitle>{dayCount?.weekday_days ?? 0}</CardTitle>
              </CardHeader>
            </Card>
            <Card>
              <CardHeader>
                <CardDescription>Weekday holidays/closures</CardDescription>
                <CardTitle>{dayCount?.non_instructional_overrides ?? 0}</CardTitle>
              </CardHeader>
            </Card>
            <Card>
              <CardHeader>
                <CardDescription>Weekend instructional days</CardDescription>
                <CardTitle>{dayCount?.instructional_overrides ?? 0}</CardTitle>
              </CardHeader>
            </Card>
          </div>

          <div className="grid gap-4 xl:grid-cols-[1fr_1fr]">
            <Card>
              <CardHeader>
                <CardTitle>{editingTermId ? 'Edit term' : 'Add term'}</CardTitle>
                <CardDescription>Build semesters, quarters, trimesters, or custom terms inside {selectedSchoolYear.name}.</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="grid gap-4 md:grid-cols-2">
                  <div className="space-y-2 md:col-span-2">
                    <Label>Name</Label>
                    <Input value={termForm.name} onChange={(event) => setTermForm((current) => ({ ...current, name: event.target.value }))} />
                  </div>
                  <div className="space-y-2">
                    <Label>Start date</Label>
                    <Input
                      type="date"
                      value={termForm.start_date}
                      onChange={(event) => setTermForm((current) => ({ ...current, start_date: event.target.value }))}
                    />
                  </div>
                  <div className="space-y-2">
                    <Label>End date</Label>
                    <Input
                      type="date"
                      value={termForm.end_date}
                      onChange={(event) => setTermForm((current) => ({ ...current, end_date: event.target.value }))}
                    />
                  </div>
                  <div className="space-y-2">
                    <Label>Term type</Label>
                    <Select value={termForm.term_type} onValueChange={(value: TermType) => setTermForm((current) => ({ ...current, term_type: value }))}>
                      <SelectTrigger className="w-full">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {termTypeOptions.map((termType) => (
                          <SelectItem key={termType} value={termType}>
                            {summarizeType(termType)}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                </div>
                <div className="flex flex-wrap gap-2">
                  <Button onClick={() => void saveTerm()}>
                    <Plus className="mr-2 h-4 w-4" />
                    {editingTermId ? 'Update' : 'Add'} term
                  </Button>
                  {editingTermId ? (
                    <Button variant="outline" onClick={resetTermForm}>
                      Cancel edit
                    </Button>
                  ) : null}
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>{editingGradingPeriodId ? 'Edit grading period' : 'Add grading period'}</CardTitle>
                <CardDescription>Break a term into marking periods like Q1 or Midterm cycle.</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="grid gap-4 md:grid-cols-2">
                  <div className="space-y-2 md:col-span-2">
                    <Label>Term</Label>
                    <Select
                      value={gradingPeriodForm.term_id}
                      onValueChange={(value) => setGradingPeriodForm((current) => ({ ...current, term_id: value }))}
                    >
                      <SelectTrigger className="w-full">
                        <SelectValue placeholder="Select a term" />
                      </SelectTrigger>
                      <SelectContent>
                        {selectedSchoolYear.terms.map((term) => (
                          <SelectItem key={term.id} value={String(term.id)}>
                            {term.name}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                  <div className="space-y-2 md:col-span-2">
                    <Label>Name</Label>
                    <Input
                      value={gradingPeriodForm.name}
                      onChange={(event) => setGradingPeriodForm((current) => ({ ...current, name: event.target.value }))}
                    />
                  </div>
                  <div className="space-y-2">
                    <Label>Start date</Label>
                    <Input
                      type="date"
                      value={gradingPeriodForm.start_date}
                      onChange={(event) => setGradingPeriodForm((current) => ({ ...current, start_date: event.target.value }))}
                    />
                  </div>
                  <div className="space-y-2">
                    <Label>End date</Label>
                    <Input
                      type="date"
                      value={gradingPeriodForm.end_date}
                      onChange={(event) => setGradingPeriodForm((current) => ({ ...current, end_date: event.target.value }))}
                    />
                  </div>
                </div>
                <div className="flex flex-wrap gap-2">
                  <Button onClick={() => void saveGradingPeriod()}>
                    <Plus className="mr-2 h-4 w-4" />
                    {editingGradingPeriodId ? 'Update' : 'Add'} grading period
                  </Button>
                  {editingGradingPeriodId ? (
                    <Button variant="outline" onClick={resetGradingPeriodForm}>
                      Cancel edit
                    </Button>
                  ) : null}
                </div>
              </CardContent>
            </Card>
          </div>

          <div className="grid gap-4 xl:grid-cols-[1fr_1fr]">
            <Card>
              <CardHeader>
                <CardTitle>Terms and grading periods</CardTitle>
              </CardHeader>
              <CardContent>
                {selectedSchoolYear.terms.length ? (
                  <div className="space-y-3">
                    {selectedSchoolYear.terms.map((term) => (
                      <div key={term.id} className="rounded-lg border p-3">
                        <div className="flex flex-wrap items-start justify-between gap-2">
                          <div>
                            <p className="font-semibold">{term.name}</p>
                            <p className="text-xs text-muted-foreground">
                              {summarizeType(term.term_type)} • {formatDateLabel(term.start_date)} – {formatDateLabel(term.end_date)}
                            </p>
                          </div>
                          <div className="flex flex-wrap gap-2">
                            <Button
                              size="sm"
                              variant="outline"
                              onClick={() => {
                                setEditingTermId(term.id)
                                setTermForm({
                                  name: term.name,
                                  start_date: term.start_date,
                                  end_date: term.end_date,
                                  term_type: term.term_type,
                                })
                              }}
                            >
                              <Pencil className="mr-2 h-3.5 w-3.5" />
                              Edit
                            </Button>
                            <Button size="sm" variant="destructive" onClick={() => void api.deleteTerm(term.id).then(() => load(selectedSchoolYear.id))}>
                              <Trash2 className="mr-2 h-3.5 w-3.5" />
                              Delete
                            </Button>
                          </div>
                        </div>
                        {term.grading_periods.length ? (
                          <div className="mt-3 space-y-2">
                            {term.grading_periods.map((gradingPeriod) => (
                              <div key={gradingPeriod.id} className="flex flex-wrap items-center justify-between gap-2 rounded-md bg-muted/40 p-2 text-sm">
                                <div>
                                  <p className="font-medium">{gradingPeriod.name}</p>
                                  <p className="text-xs text-muted-foreground">
                                    {formatDateLabel(gradingPeriod.start_date)} – {formatDateLabel(gradingPeriod.end_date)}
                                  </p>
                                </div>
                                <div className="flex flex-wrap gap-2">
                                  <Button
                                    size="sm"
                                    variant="outline"
                                    onClick={() => {
                                      setEditingGradingPeriodId(gradingPeriod.id)
                                      setGradingPeriodForm({
                                        term_id: String(gradingPeriod.term_id),
                                        name: gradingPeriod.name,
                                        start_date: gradingPeriod.start_date,
                                        end_date: gradingPeriod.end_date,
                                      })
                                    }}
                                  >
                                    <Pencil className="mr-2 h-3.5 w-3.5" />
                                    Edit
                                  </Button>
                                  <Button
                                    size="sm"
                                    variant="destructive"
                                    onClick={() => void api.deleteGradingPeriod(gradingPeriod.id).then(() => load(selectedSchoolYear.id))}
                                  >
                                    <Trash2 className="mr-2 h-3.5 w-3.5" />
                                    Delete
                                  </Button>
                                </div>
                              </div>
                            ))}
                          </div>
                        ) : (
                          <p className="mt-3 text-sm text-muted-foreground">No grading periods yet.</p>
                        )}
                      </div>
                    ))}
                  </div>
                ) : (
                  <EmptyState title="No terms yet" description="Add a semester, quarter, or custom term to begin mapping the year." />
                )}
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>{editingEventId ? 'Edit calendar event' : 'Add calendar event'}</CardTitle>
                <CardDescription>Mark holidays, closures, or custom instructional days.</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="grid gap-4 md:grid-cols-2">
                  <div className="space-y-2">
                    <Label>Date</Label>
                    <Input type="date" value={eventForm.date} onChange={(event) => setEventForm((current) => ({ ...current, date: event.target.value }))} />
                  </div>
                  <div className="space-y-2">
                    <Label>Type</Label>
                    <Select
                      value={eventForm.event_type}
                      onValueChange={(value: CalendarEventType) => setEventForm((current) => ({ ...current, event_type: value }))}
                    >
                      <SelectTrigger className="w-full">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {eventTypeOptions.map((eventType) => (
                          <SelectItem key={eventType} value={eventType}>
                            {summarizeType(eventType)}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                  <div className="space-y-2 md:col-span-2">
                    <Label>Name</Label>
                    <Input value={eventForm.name} onChange={(event) => setEventForm((current) => ({ ...current, name: event.target.value }))} />
                  </div>
                  <div className="space-y-2 md:col-span-2">
                    <Label>Notes</Label>
                    <Textarea value={eventForm.notes} onChange={(event) => setEventForm((current) => ({ ...current, notes: event.target.value }))} />
                  </div>
                </div>
                <label className="flex items-center gap-2 text-sm">
                  <input
                    type="checkbox"
                    checked={eventForm.is_instructional_day}
                    onChange={(event) => setEventForm((current) => ({ ...current, is_instructional_day: event.target.checked }))}
                  />
                  Count this date as an instructional day
                </label>
                <div className="flex flex-wrap gap-2">
                  <Button onClick={() => void saveEvent()}>
                    <Plus className="mr-2 h-4 w-4" />
                    {editingEventId ? 'Update' : 'Add'} event
                  </Button>
                  {editingEventId ? (
                    <Button variant="outline" onClick={resetEventForm}>
                      Cancel edit
                    </Button>
                  ) : null}
                </div>
              </CardContent>
            </Card>
          </div>

          <div className="grid gap-4 xl:grid-cols-[1.15fr_0.85fr]">
            <Card>
              <CardHeader>
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div>
                    <CardTitle>Holiday and closure view</CardTitle>
                    <CardDescription>Month view for {selectedSchoolYear.name}</CardDescription>
                  </div>
                  {calendarMonth ? (
                    <div className="flex items-center gap-2">
                      <Button variant="outline" size="sm" onClick={() => setCalendarMonth((current) => addMonths(current, -1))}>
                        Prev
                      </Button>
                      <span className="min-w-32 text-center text-sm font-medium">
                        {monthNames[startOfMonth(calendarMonth).getMonth()]} {startOfMonth(calendarMonth).getFullYear()}
                      </span>
                      <Button variant="outline" size="sm" onClick={() => setCalendarMonth((current) => addMonths(current, 1))}>
                        Next
                      </Button>
                    </div>
                  ) : null}
                </div>
              </CardHeader>
              <CardContent>
                {calendarMonth ? (
                  <div className="grid grid-cols-7 gap-2 text-xs">
                    {['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'].map((weekday) => (
                      <div key={weekday} className="px-2 py-1 font-semibold text-muted-foreground">
                        {weekday}
                      </div>
                    ))}
                    {monthGrid.map((day) => (
                      <div key={day.key} className={`min-h-28 rounded-lg border p-2 ${day.inMonth ? 'bg-background' : 'bg-muted/30 text-muted-foreground'}`}>
                        <div className="mb-2 text-xs font-semibold">{day.date.getDate()}</div>
                        <div className="space-y-1">
                          {day.events.map((event) => (
                            <button
                              key={event.id}
                              type="button"
                              className={`block w-full rounded px-2 py-1 text-left text-[11px] ${
                                event.is_instructional_day ? 'bg-emerald-100 text-emerald-900' : 'bg-amber-100 text-amber-900'
                              }`}
                              onClick={() => {
                                setEditingEventId(event.id)
                                setEventForm({
                                  date: event.date,
                                  event_type: event.event_type,
                                  name: event.name,
                                  is_instructional_day: event.is_instructional_day,
                                  notes: event.notes || '',
                                })
                              }}
                            >
                              {event.name}
                            </button>
                          ))}
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="text-sm text-muted-foreground">Pick a school year to load the calendar.</p>
                )}
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Event list</CardTitle>
              </CardHeader>
              <CardContent>
                {selectedSchoolYear.calendar_events.length ? (
                  <div className="space-y-2">
                    {selectedSchoolYear.calendar_events.map((event) => (
                      <div key={event.id} className="rounded-lg border p-3">
                        <div className="flex flex-wrap items-start justify-between gap-2">
                          <div>
                            <p className="font-semibold">{event.name}</p>
                            <p className="text-xs text-muted-foreground">
                              {formatDateLabel(event.date)} • {summarizeType(event.event_type)} •{' '}
                              {event.is_instructional_day ? 'Instructional' : 'Non-instructional'}
                            </p>
                          </div>
                          <div className="flex flex-wrap gap-2">
                            <Button
                              size="sm"
                              variant="outline"
                              onClick={() => {
                                setEditingEventId(event.id)
                                setEventForm({
                                  date: event.date,
                                  event_type: event.event_type,
                                  name: event.name,
                                  is_instructional_day: event.is_instructional_day,
                                  notes: event.notes || '',
                                })
                              }}
                            >
                              <Pencil className="mr-2 h-3.5 w-3.5" />
                              Edit
                            </Button>
                            <Button size="sm" variant="destructive" onClick={() => void api.deleteCalendarEvent(event.id).then(() => load(selectedSchoolYear.id))}>
                              <Trash2 className="mr-2 h-3.5 w-3.5" />
                              Delete
                            </Button>
                          </div>
                        </div>
                        {event.notes ? <p className="mt-2 text-sm text-muted-foreground">{event.notes}</p> : null}
                      </div>
                    ))}
                  </div>
                ) : (
                  <EmptyState title="No events yet" description="Add holidays, weather closures, or custom instructional days." />
                )}
              </CardContent>
            </Card>
          </div>
        </>
      ) : (
        <EmptyState title="No school year selected" description="Create or choose a school year to manage the academic calendar." />
      )}
    </div>
  )
}
