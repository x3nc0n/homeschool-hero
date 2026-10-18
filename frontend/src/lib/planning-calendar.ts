export const calendarViews = ['day', 'work-week', 'week', 'month', 'agenda'] as const
export type CalendarView = (typeof calendarViews)[number]
export type CalendarScope = 'calendar' | 'all' | 'overdue' | 'undated'

export function schoolDate(date = new Date()): string {
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`
}

export function isSchoolDate(value: string): boolean {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(value)) return false
  const date = new Date(`${value}T12:00:00Z`)
  return Number.isFinite(date.getTime()) && date.toISOString().slice(0, 10) === value
}

export function addSchoolDays(value: string, days: number): string {
  const date = new Date(`${value}T12:00:00Z`)
  date.setUTCDate(date.getUTCDate() + days)
  return date.toISOString().slice(0, 10)
}

export function weekStart(value: string): string {
  const weekday = new Date(`${value}T12:00:00Z`).getUTCDay()
  return addSchoolDays(value, -((weekday + 6) % 7))
}

export function calendarRange(value: string, view: CalendarView): { start: string; end: string } {
  if (view === 'day') return { start: value, end: value }
  if (view === 'month') {
    const first = `${value.slice(0, 7)}-01`
    const next = new Date(`${first}T12:00:00Z`)
    next.setUTCMonth(next.getUTCMonth() + 1)
    const last = addSchoolDays(next.toISOString().slice(0, 10), -1)
    return { start: weekStart(first), end: addSchoolDays(weekStart(last), 6) }
  }
  const start = weekStart(value)
  return { start, end: addSchoolDays(start, view === 'work-week' ? 4 : 6) }
}

export function rangeDays(start: string, end: string): string[] {
  const dates: string[] = []
  for (let date = start; date <= end; date = addSchoolDays(date, 1)) dates.push(date)
  return dates
}

export function moveCalendarDate(value: string, view: CalendarView, direction: number): string {
  if (view !== 'month') return addSchoolDays(value, direction * (view === 'day' ? 1 : 7))
  const date = new Date(`${value.slice(0, 7)}-01T12:00:00Z`)
  date.setUTCMonth(date.getUTCMonth() + direction)
  const month = date.toISOString().slice(0, 7)
  date.setUTCMonth(date.getUTCMonth() + 1)
  const lastDay = Number(addSchoolDays(date.toISOString().slice(0, 10), -1).slice(8))
  return `${month}-${String(Math.min(Number(value.slice(8)), lastDay)).padStart(2, '0')}`
}

export function schoolDateLabel(value: string): string {
  return new Date(`${value.slice(0, 10)}T12:00:00`).toLocaleDateString(undefined, {
    weekday: 'short', month: 'short', day: 'numeric', year: 'numeric',
  })
}

export async function fetchEveryPage<T>(
  fetchPage: (page: number) => Promise<{ items: T[]; total_pages: number }>,
): Promise<T[]> {
  const first = await fetchPage(1)
  const items = [...first.items]
  // Sequential pages avoid flooding the API for a busy month or a large history.
  for (let page = 2; page <= first.total_pages; page += 1) {
    items.push(...(await fetchPage(page)).items)
  }
  return items
}

export function assignmentDates(
  assignment: Pick<Assignment, 'targets' | 'due_date'>,
  studentId?: number,
  targetStatus?: AssignmentTargetStatus,
): string[] {
  if (!assignment.targets.length) return [(assignment.due_date || '').slice(0, 10)]
  return [...new Set(assignment.targets
    .filter((target) => (!studentId || target.student_id === studentId) && (!targetStatus || target.status === targetStatus))
    .map((target) => (target.due_date || assignment.due_date || '').slice(0, 10)))]
}

export function assignmentIsOverdue(
  assignment: Pick<Assignment, 'targets' | 'due_date' | 'status'>,
  today: string,
  studentId?: number,
): boolean {
  return assignment.status === 'pending' && assignmentDates(assignment, studentId, 'assigned')
    .some((date) => Boolean(date) && date < today)
}
import type { Assignment, AssignmentTargetStatus } from '@/types/api'
