import type { ReactNode } from 'react'
import { useSearchParams } from 'react-router-dom'
import {
  calendarRange, calendarViews, isSchoolDate, moveCalendarDate, rangeDays, schoolDate, schoolDateLabel,
  type CalendarScope, type CalendarView,
} from '@/lib/planning-calendar'

const controlClass = 'rounded-md border border-input bg-background px-3 py-2 text-sm'
const viewLabels: Record<CalendarView, string> = {
  day: 'Day', 'work-week': 'Work week', week: 'Week', month: 'Month', agenda: 'Agenda',
}

export function usePlanningCalendar() {
  const [params, setParams] = useSearchParams()
  const dateParam = params.get('date') || ''
  const date = isSchoolDate(dateParam) ? dateParam : schoolDate()
  const viewParam = params.get('view')
  const view: CalendarView = calendarViews.includes(viewParam as CalendarView) ? viewParam as CalendarView : 'week'
  const scopeParam = params.get('scope')
  const legacyHistory = !scopeParam && (
    params.has('due_from') || params.has('due_to') ||
    (!params.has('date') && !params.has('view') && (params.has('q') || params.has('search')))
  )
  const scope: CalendarScope = ['all', 'overdue', 'undated'].includes(scopeParam || '')
    ? scopeParam as CalendarScope : legacyHistory ? 'all' : 'calendar'
  const update = (values: Record<string, string>) => setParams((current) => {
    const next = new URLSearchParams(current)
    Object.entries(values).forEach(([key, value]) => next.set(key, value))
    next.set('page', '1')
    return next
  }, { replace: true })
  return {
    date, view, scope, range: calendarRange(date, view),
    page: Math.max(1, Math.floor(Number(params.get('page')) || 1)),
    setPage: (page: number) => setParams((current) => {
      const next = new URLSearchParams(current)
      next.set('page', String(page))
      return next
    }, { replace: true }),
    setDate: (value: string) => { if (isSchoolDate(value)) update({ date: value, scope: 'calendar' }) },
    setView: (value: CalendarView) => update({ view: value, scope: 'calendar' }),
    setScope: (value: CalendarScope) => update({ scope: value }),
  }
}

type Navigation = ReturnType<typeof usePlanningCalendar>

export function PlanningCalendarToolbar({ navigation }: { navigation: Navigation }) {
  const { date, view, scope, range, setDate, setView, setScope } = navigation
  return (
    <section aria-label="Calendar navigation" className="space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        <button className={controlClass} onClick={() => setDate(moveCalendarDate(date, view, -1))} aria-label="Previous date range">←</button>
        <button className={controlClass} onClick={() => setDate(schoolDate())}>Today</button>
        <button className={controlClass} onClick={() => setDate(moveCalendarDate(date, view, 1))} aria-label="Next date range">→</button>
        <label className="flex items-center gap-2 text-sm">
          Selected date
          <input aria-label="Selected date" className={controlClass} type="date" value={date} onChange={(event) => setDate(event.target.value)} />
        </label>
        <label className="flex items-center gap-2 text-sm">
          View
          <select aria-label="View" className={controlClass} value={view} onChange={(event) => setView(event.target.value as CalendarView)}>
            {calendarViews.map((option) => <option key={option} value={option}>{viewLabels[option]}</option>)}
          </select>
        </label>
      </div>
      <div className="flex flex-wrap gap-2" aria-label="Work dates">
        {([
          ['calendar', 'Selected range'], ['all', 'All dates'], ['overdue', 'Overdue work'], ['undated', 'Undated work'],
        ] as const).map(([value, label]) => (
          <button key={value} className={`${controlClass} ${scope === value ? 'bg-muted font-semibold' : ''}`}
            aria-pressed={scope === value} onClick={() => setScope(value)}>{label}</button>
        ))}
      </div>
      <p className="text-sm text-muted-foreground" aria-live="polite">
        {scope === 'calendar' ? `${schoolDateLabel(range.start)} – ${schoolDateLabel(range.end)} · All-day work` :
          scope === 'all' ? 'All dates · Completed and historical work remains available' :
            scope === 'overdue' ? 'Unfinished work before today' : 'Work without a scheduled date'}
      </p>
    </section>
  )
}

export interface PlanningCalendarEntry {
  id: string | number
  date: string
  title: string
  subtitle?: string
  details: ReactNode
}

export function PlanningEntry({ entry }: { entry: PlanningCalendarEntry }) {
  return (
    <details className="min-w-0 rounded-md border bg-background p-2 text-sm">
      <summary className="cursor-pointer break-words font-medium">
        <span className="line-clamp-2">{entry.title}</span>
        {entry.subtitle ? <span className="mt-1 line-clamp-2 text-xs font-normal text-muted-foreground">{entry.subtitle}</span> : null}
      </summary>
      <div className="mt-3 space-y-2 break-words">{entry.details}</div>
    </details>
  )
}

function DayEntries({ entries, limit }: { entries: PlanningCalendarEntry[]; limit: number }) {
  return (
    <div className="space-y-2">
      {entries.slice(0, limit).map((entry) => <PlanningEntry key={entry.id} entry={entry} />)}
      {entries.length > limit ? (
        <details className="rounded-md border border-dashed p-2 text-sm">
          <summary className="cursor-pointer font-medium">+{entries.length - limit} more</summary>
          <div className="mt-2 space-y-2">{entries.slice(limit).map((entry) => <PlanningEntry key={entry.id} entry={entry} />)}</div>
        </details>
      ) : null}
      {!entries.length ? <p className="text-xs text-muted-foreground">No work scheduled</p> : null}
    </div>
  )
}

export function PlanningCalendar({ date, view, entries }: {
  date: string; view: CalendarView; entries: PlanningCalendarEntry[]
}) {
  const range = calendarRange(date, view)
  const days = rangeDays(range.start, range.end)
  const byDay = new Map<string, PlanningCalendarEntry[]>()
  entries.forEach((entry) => byDay.set(entry.date, [...(byDay.get(entry.date) || []), entry]))
  const agenda = (
    <div className="space-y-4">
      {days.map((day) => (
        <section key={day} aria-label={schoolDateLabel(day)} className="space-y-2">
          <h3 className="text-sm font-semibold">{schoolDateLabel(day)} · {byDay.get(day)?.length || 0}</h3>
          <DayEntries entries={byDay.get(day) || []} limit={5} />
        </section>
      ))}
    </div>
  )
  if (view === 'agenda' || view === 'day') return <div aria-label="Calendar agenda">{agenda}</div>
  return (
    <>
      <div className="md:hidden" aria-label="Mobile calendar agenda">{agenda}</div>
      <div className={`hidden gap-2 md:grid ${view === 'work-week' ? 'md:grid-cols-5' : 'md:grid-cols-7'}`} aria-label="All-day calendar">
        {days.map((day) => (
          <section key={day} aria-label={schoolDateLabel(day)}
            className={`min-w-0 space-y-2 rounded-lg border p-2 ${day === schoolDate() ? 'border-primary' : ''} ${view === 'month' && day.slice(0, 7) !== date.slice(0, 7) ? 'bg-muted/40' : ''}`}>
            <h3 className="text-xs font-semibold">{schoolDateLabel(day)} · {byDay.get(day)?.length || 0}</h3>
            <DayEntries entries={byDay.get(day) || []} limit={view === 'month' ? 2 : 3} />
          </section>
        ))}
      </div>
    </>
  )
}
