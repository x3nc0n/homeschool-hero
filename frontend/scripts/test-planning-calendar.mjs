import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { createRequire } from 'node:module'
import test from 'node:test'
import vm from 'node:vm'
import React from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import ts from 'typescript'

const require = createRequire(import.meta.url)
const root = new URL('../src/', import.meta.url)
let params = new URLSearchParams('date=2026-10-14')
let canManage = true
let stateOverrides = {}
let stateIndex = 0
let effectQueue = null
const api = {}

const react = {
  ...React,
  useState(initial) {
    const index = stateIndex++
    return React.useState(Object.hasOwn(stateOverrides, index) ? stateOverrides[index] : initial)
  },
  useEffect(effect, dependencies) {
    if (effectQueue) effectQueue.push(effect)
    else React.useEffect(effect, dependencies)
  },
}
function wrapper(tag) {
  return ({ children, ...props }) => {
    const safe = Object.fromEntries(Object.entries(props).filter(([key]) =>
      ['className', 'id', 'type', 'disabled', 'value', 'open', 'onChange'].includes(key) || key.startsWith('aria-')))
    return React.createElement(tag, safe, children)
  }
}
const modules = {
  react,
  'react/jsx-runtime': require('react/jsx-runtime'),
  'react-router-dom': { useSearchParams: () => [params, (next) => { params = typeof next === 'function' ? next(params) : next }] },
  'lucide-react': Object.fromEntries(['FileText', 'Pencil', 'Plus', 'Trash2', 'CalendarRange'].map((name) => [name, wrapper('svg')])),
  '@/context/AuthContext': { useAuth: () => ({ canManageCurriculum: canManage, studentId: canManage ? undefined : 1 }) },
  '@/lib/api': { api },
  '@/components/features/BulkAssignmentImportWizard': {
    BulkAssignmentImportWizard: ({ planningMode, initialDate }) => React.createElement('div', null, `Import wizard ${planningMode} ${initialDate}`),
  },
  '@/components/ui/button': { Button: wrapper('button') },
  '@/components/ui/input': { Input: wrapper('input') },
  '@/components/ui/label': { Label: wrapper('label') },
  '@/components/ui/textarea': { Textarea: wrapper('textarea') },
  '@/components/ui/badge': { Badge: wrapper('span') },
  '@/components/ui/select': Object.fromEntries(['Select', 'SelectContent', 'SelectItem', 'SelectTrigger', 'SelectValue'].map((name) => [name, wrapper('div')])),
  '@/components/ui/card': Object.fromEntries(['Card', 'CardContent', 'CardHeader', 'CardTitle', 'CardDescription'].map((name) => [name, wrapper('section')])),
  '@/components/common/LoadingState': { LoadingState: () => React.createElement('p', null, 'Loading') },
  '@/components/common/ErrorState': { ErrorState: () => React.createElement('p', null, 'Error') },
  '@/components/common/EmptyState': { EmptyState: ({ title }) => React.createElement('p', null, title) },
}
function compile(relative) {
  const source = readFileSync(new URL(relative, root), 'utf8')
  const { outputText } = ts.transpileModule(source, {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, jsx: ts.JsxEmit.ReactJSX },
  })
  const module = { exports: {} }
  vm.runInNewContext(outputText, {
    module, exports: module.exports, URLSearchParams, console,
    require: (name) => {
      assert.ok(Object.hasOwn(modules, name), `Unexpected dependency ${name}`)
      return modules[name]
    },
  })
  return module.exports
}
const dates = compile('lib/planning-calendar.ts')
modules['@/lib/planning-calendar'] = dates
const calendar = compile('components/features/PlanningCalendar.tsx')
modules['@/components/features/PlanningCalendar'] = calendar
const { AssignmentsPage } = compile('pages/AssignmentsPage.tsx')
const { LessonPlansPage } = compile('pages/LessonPlansPage.tsx')

function plain(value) { return JSON.parse(JSON.stringify(value)) }
function render(component, props = {}) {
  stateIndex = 0
  return renderToStaticMarkup(React.createElement(component, props))
}
function reset() {
  params = new URLSearchParams('date=2026-10-14')
  stateOverrides = {}
  canManage = true
}
const subject = { id: 1, name: 'Science - 7th Grade' }
const student = { id: 1, name: 'Lucas' }
const assignment = {
  id: 1, title: 'Observe cells', description: 'Use a microscope', subject_id: 1, subject,
  due_date: '2026-10-14T00:00:00Z', status: 'pending', category: 'homework',
  weight: 1, max_score: 100, recurrence: 'none', attachments: [],
  targets: [{ id: 1, student_id: 1, due_date: '2026-10-14T00:00:00Z', status: 'assigned', student }],
}
const lesson = {
  id: 1, target_date: '2026-10-14', status: 'planned', student_id: 1, notes: 'Use a microscope',
  assignment_ids: [1], curriculum_lesson_id: 1,
  curriculum_lesson: { name: 'Observe cells', resources: [], unit: { name: 'Unit 4', package: { id: 1, name: 'Science' } } },
}
function assignmentState(extra = {}) {
  stateOverrides = { 0: [assignment], 1: [subject], 2: [student], 5: false, ...extra }
}
function lessonState(extra = {}) {
  stateOverrides = { 0: [student], 1: [subject], 4: [lesson], 14: false, ...extra }
}

test('week and work-week use Monday boundaries across years', () => {
  assert.deepEqual(plain(dates.calendarRange('2027-01-01', 'week')), { start: '2026-12-28', end: '2027-01-03' })
  assert.deepEqual(plain(dates.calendarRange('2027-01-03', 'work-week')), { start: '2026-12-28', end: '2027-01-01' })
  assert.deepEqual(plain(dates.calendarRange('2026-10-14', 'day')), { start: '2026-10-14', end: '2026-10-14' })
  assert.deepEqual(plain(dates.calendarRange('2026-10-14', 'agenda')), { start: '2026-10-12', end: '2026-10-18' })
})

test('month fetches complete visible adjacent weeks, including leap days', () => {
  const range = dates.calendarRange('2024-02-15', 'month')
  assert.deepEqual(plain(range), { start: '2024-01-29', end: '2024-03-03' })
  assert.equal(dates.rangeDays(range.start, range.end).length, 35)
  assert.ok(dates.rangeDays(range.start, range.end).includes('2024-02-29'))
})

test('navigation clamps month dates and moves other views without timezone drift', () => {
  assert.equal(dates.moveCalendarDate('2024-01-31', 'month', 1), '2024-02-29')
  assert.equal(dates.moveCalendarDate('2026-03-31', 'month', -1), '2026-02-28')
  assert.equal(dates.moveCalendarDate('2026-10-14', 'week', 1), '2026-10-21')
  assert.equal(dates.moveCalendarDate('2026-10-14', 'day', -1), '2026-10-13')
  assert.equal(dates.addSchoolDays('2026-03-08', 1), '2026-03-09')
  assert.equal(dates.addSchoolDays('2026-11-01', 1), '2026-11-02')
  assert.equal(dates.isSchoolDate('2026-02-30'), false)
  assert.equal(dates.isSchoolDate('2024-02-29'), true)
})

test('all result pages are fetched before global sorting, not just page one', async () => {
  const calls = []
  const items = await dates.fetchEveryPage(async (page) => {
    calls.push(page)
    return { items: [{ id: 4 - page }], total_pages: 3 }
  })
  assert.deepEqual(calls, [1, 2, 3])
  assert.deepEqual(plain(items.sort((a, b) => a.id - b.id)), [{ id: 1 }, { id: 2 }, { id: 3 }])
  const empty = await dates.fetchEveryPage(async () => ({ items: [], total_pages: 0 }))
  assert.equal(empty.length, 0)
})

test('school dates use target date and fallback on the same selected student', () => {
  const work = { ...assignment, targets: [
    { student_id: 1, due_date: null, status: 'assigned' },
    { student_id: 2, due_date: '2026-10-16T00:00:00Z', status: 'graded' },
  ] }
  assert.deepEqual(plain(dates.assignmentDates(work, 1)), ['2026-10-14'])
  assert.deepEqual(plain(dates.assignmentDates(work, 2)), ['2026-10-16'])
  assert.deepEqual(plain(dates.assignmentDates(work, 2, 'assigned')), [])
  assert.equal(dates.assignmentIsOverdue(work, '2026-10-15', 1), true)
  assert.equal(dates.assignmentIsOverdue(work, '2026-10-20', 2), false)
  assert.equal(dates.assignmentIsOverdue({ ...work, status: 'complete' }, '2026-10-20', 1), false)
  assert.deepEqual(plain(dates.assignmentDates({ due_date: null, targets: [] })), [''])
})

test('navigation preserves existing deep links and filter context', () => {
  reset()
  params.set('subject_id', '9')
  params.set('student_id', '1')
  params.set('search', 'cells')
  const nav = calendar.usePlanningCalendar()
  assert.equal(nav.view, 'week')
  nav.setView('month')
  assert.equal(params.get('view'), 'month')
  assert.equal(params.get('subject_id'), '9')
  assert.equal(params.get('search'), 'cells')
  nav.setScope('all')
  assert.equal(params.get('scope'), 'all')
  nav.setPage(3)
  assert.equal(calendar.usePlanningCalendar().page, 3)
  nav.setDate('2026-10-20')
  assert.equal(params.get('date'), '2026-10-20')
  assert.equal(params.get('scope'), 'calendar')
  assert.equal(calendar.usePlanningCalendar().page, 1)
  nav.setDate('not-a-date')
  assert.equal(params.get('date'), '2026-10-20')
  params = new URLSearchParams('due_from=2020-01-01')
  assert.equal(calendar.usePlanningCalendar().scope, 'all')
  params = new URLSearchParams('q=historical-assignment')
  assert.equal(calendar.usePlanningCalendar().scope, 'all')
})

test('toolbar exposes every view, date picker, history and unfinished-work entries', () => {
  reset()
  const html = render(calendar.PlanningCalendarToolbar, { navigation: calendar.usePlanningCalendar() })
  for (const label of ['Today', 'Previous date range', 'Next date range', 'Selected date', 'Day', 'Work week', 'Week', 'Month', 'Agenda', 'All dates', 'Overdue work', 'Undated work']) {
    assert.ok(html.includes(label), label)
  }
  assert.match(html, /type="date"/)
  assert.match(html, /<input aria-label="Selected date"[^>]*type="date"/)
  assert.match(html, /<select aria-label="View"/)
  assert.match(html, /aria-pressed="true"/)
})

test('busy calendars have native expandable details, counted overflow and mobile agenda', () => {
  const entries = Array.from({ length: 8 }, (_, index) => ({
    id: index, date: '2026-10-14', title: `Activity ${index}`, subtitle: 'Lucas · Science',
    details: React.createElement('p', null, `Instructions ${index}`),
  }))
  const html = render(calendar.PlanningCalendar, { date: '2026-10-14', view: 'week', entries })
  assert.match(html, /Mobile calendar agenda/)
  assert.match(html, /md:hidden/)
  assert.match(html, /md:grid-cols-7/)
  assert.match(html, /\+5 more/)
  assert.match(html, /<details[^>]*><summary/)
  assert.match(html, /Instructions 7/)
  assert.doesNotMatch(html, /<details[^>]* open/)
})

test('agenda and day use a single list while month keeps compact overflow', () => {
  const entries = Array.from({ length: 4 }, (_, id) => ({ id, date: '2026-10-14', title: `Item ${id}`, details: 'Read' }))
  for (const view of ['day', 'agenda']) {
    const html = render(calendar.PlanningCalendar, { date: '2026-10-14', view, entries })
    assert.match(html, /Calendar agenda/)
    assert.doesNotMatch(html, /Mobile calendar agenda/)
  }
  const html = render(calendar.PlanningCalendar, { date: '2026-10-14', view: 'month', entries })
  assert.match(html, /\+2 more/)
  assert.match(html, /No work scheduled/)
})

test('assignments default to calendar with create/import forms hidden until chosen', () => {
  reset()
  assignmentState()
  const html = render(AssignmentsPage)
  assert.match(html, /Observe cells/)
  assert.match(html, /Plan week/)
  assert.match(html, /All-day calendar/)
  assert.doesNotMatch(html, /Import wizard|Answer key questions|Per-student targeting/)
  assignmentState({ 11: true, 12: true })
  assert.match(render(AssignmentsPage), /Import wizard weekly 2026-10-14/)
})

test('assignment history retains completed work and paginates globally sorted records', () => {
  reset()
  params.set('scope', 'all')
  assignmentState({ 0: Array.from({ length: 25 }, (_, index) => ({
    ...assignment, id: index + 1, title: `History ${String(index).padStart(2, '0')}`,
    due_date: `2020-01-${String(index + 1).padStart(2, '0')}T00:00:00Z`, targets: [], status: 'graded',
  })).reverse() })
  const html = render(AssignmentsPage)
  assert.match(html, /25 assignments/)
  assert.match(html, /Page 1 of 3/)
  assert.match(html, /History 00/)
  assert.doesNotMatch(html, /History 24/)
})

test('overdue and undated work remain accessible separately without hiding completed history', () => {
  reset()
  const work = [
    { ...assignment, id: 1, title: 'Unfinished old work', due_date: '2020-01-01', targets: [] },
    { ...assignment, id: 2, title: 'Finished old work', due_date: '2020-01-01', targets: [], status: 'graded' },
    { ...assignment, id: 3, title: 'No date work', due_date: null, targets: [] },
    { ...assignment, id: 4, title: 'Future work', due_date: '2099-01-01', targets: [] },
  ]
  assignmentState({ 0: work })
  params.set('scope', 'overdue')
  const overdue = render(AssignmentsPage)
  assert.match(overdue, /Unfinished old work/)
  assert.doesNotMatch(overdue, /Finished old work|No date work|Future work/)
  params.set('scope', 'undated')
  const undated = render(AssignmentsPage)
  assert.match(undated, /No date work/)
  assert.doesNotMatch(undated, /Unfinished old work|Finished old work|Future work/)
  params.set('scope', 'all')
  const history = render(AssignmentsPage)
  for (const item of work) assert.ok(history.includes(item.title))
})

test('lesson plans default to calendar with forms hidden and weekly entry available', () => {
  reset()
  lessonState()
  const html = render(LessonPlansPage)
  assert.match(html, /Observe cells/)
  assert.match(html, /Plan week/)
  assert.match(html, /All-day calendar/)
  assert.doesNotMatch(html, /Import wizard|Manually schedule|Auto-place lessons/)
  lessonState({ 13: true })
  assert.match(render(LessonPlansPage), /Import wizard weekly 2026-10-14/)
})

test('lesson history remains paginated and searchable across completed and planned work', () => {
  reset()
  params.set('scope', 'all')
  const lessons = Array.from({ length: 22 }, (_, index) => ({
    ...lesson, id: index + 1, target_date: `2020-01-${String(index + 1).padStart(2, '0')}`,
    status: index % 2 ? 'planned' : 'completed',
    curriculum_lesson: { ...lesson.curriculum_lesson, name: `Old lesson ${String(index).padStart(2, '0')}` },
  }))
  lessonState({ 4: lessons })
  const first = render(LessonPlansPage)
  assert.match(first, /Page 1 of 3/)
  assert.match(first, /Old lesson 00/)
  assert.doesNotMatch(first, /Old lesson 21/)
  params.set('page', '3')
  const last = render(LessonPlansPage)
  assert.match(last, /Old lesson 21/)
  params.set('page', '1')
  params.set('search', 'lesson 11')
  const search = render(LessonPlansPage)
  assert.match(search, /Old lesson 11/)
  assert.doesNotMatch(search, /Old lesson 00/)
})

test('read-only student calendar hides teacher actions and locks student scope', () => {
  reset()
  canManage = false
  assignmentState()
  const assignments = render(AssignmentsPage)
  assert.match(assignments, /Observe cells/)
  assert.doesNotMatch(assignments, /Plan week|Create assignment|Edit assignment|Import assignments|Delete/)
  lessonState()
  const lessons = render(LessonPlansPage)
  assert.match(lessons, /Observe cells/)
  assert.match(lessons, /aria-label="Student" disabled/)
  assert.doesNotMatch(lessons, /Plan week|Add lesson plan|Generate assignment|Delete/)
})

test('assignments request the complete visible month and every result page with filters', async () => {
  reset()
  params = new URLSearchParams('date=2024-02-15&view=month&student_id=1&subject_id=3&search=cells')
  assignmentState()
  const requests = []
  Object.assign(api, {
    listSchoolYears: async () => [],
    listSubjects: async () => [],
    listStudents: async () => [],
    listAssignments: async (filters) => {
      requests.push(filters)
      return { items: [], total_pages: 3 }
    },
  })

  effectQueue = []
  render(AssignmentsPage)
  const [loadEffect] = effectQueue
  effectQueue = null
  loadEffect()
  await new Promise((resolve) => setImmediate(resolve))
  assert.deepEqual(requests.map((request) => request.page), [1, 2, 3])
  for (const request of requests) {
    assert.equal(request.due_from, '2024-01-29')
    assert.equal(request.due_to, '2024-03-03')
    assert.equal(request.student_id, 1)
    assert.equal(request.subject_id, 3)
    assert.equal(request.q, 'cells')
  }
})

test('lesson plans request only the selected work-week with student, subject and status filters', async () => {
  reset()
  params = new URLSearchParams('date=2026-10-14&view=work-week&student_id=1&subject_id=3&status=planned&school_year_id=all')
  lessonState()
  const requests = []
  Object.assign(api, {
    listLessonPlans: async (filters) => { requests.push(filters); return [] },
    listPacingTargets: async () => [],
    getPacingStatus: async () => ({ items: [] }),
  })
  effectQueue = []
  render(LessonPlansPage)
  const loadEffect = effectQueue[2]
  effectQueue = null
  loadEffect()
  await new Promise((resolve) => setImmediate(resolve))
  assert.equal(requests.length, 1)
  assert.equal(requests[0].start_date, '2026-10-12')
  assert.equal(requests[0].end_date, '2026-10-16')
  assert.equal(requests[0].student_id, 1)
  assert.equal(requests[0].subject_id, 3)
  assert.equal(requests[0].status, 'planned')
  assert.equal(requests[0].school_year_id, undefined)
})

test('calendar and history details have stable keys even when target response IDs are absent', () => {
  reset()
  const warnings = []
  const originalError = console.error
  console.error = (...args) => warnings.push(args.join(' '))
  try {
    const targets = [
      { student_id: 1, due_date: '2026-10-14', status: 'assigned', student },
      { student_id: 2, due_date: '2026-10-14', status: 'assigned', student: { id: 2, name: 'Sam' } },
    ]
    assignmentState({ 0: [{ ...assignment, targets }] })
    render(AssignmentsPage)
    params.set('scope', 'all')
    render(AssignmentsPage)
    lessonState({ 4: [lesson, { ...lesson, id: 2 }] })
    render(LessonPlansPage)
    params.set('scope', 'calendar')
    render(LessonPlansPage)
  } finally {
    console.error = originalError
  }
  assert.deepEqual(warnings, [])
})
