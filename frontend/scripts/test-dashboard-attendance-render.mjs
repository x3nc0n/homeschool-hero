import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { createRequire } from 'node:module'
import test from 'node:test'
import vm from 'node:vm'
import React from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import ts from 'typescript'

const require = createRequire(import.meta.url)
const currentDirectory = new URL('../', import.meta.url)
const attendanceLabels = {
  'attendance.calendar.instructional': 'Instructional day',
  'attendance.calendar.nonInstructional': 'Non-instructional day',
  'attendance.calendar.notRecorded': 'Not recorded',
}

let activeDashboard
let activeStudentId = 1
let studentState

function wrapper(tagName) {
  return function Wrapper({ children, className, id, title, role, ...props }) {
    const attributes = { className, id, title, role }
    for (const [key, value] of Object.entries(props)) {
      if (key.startsWith('aria-') || key === 'href' || key === 'type' || key === 'disabled') {
        attributes[key] = value
      }
    }
    return React.createElement(tagName, attributes, children)
  }
}

function EmptyState({ title, description }) {
  return React.createElement('section', null, React.createElement('h3', null, title), React.createElement('p', null, description))
}

const reactForPage = {
  ...React,
  useState(initialValue) {
    const stateIndex = studentState?.index ?? -1
    if (studentState) studentState.index += 1
    const value = studentState?.values[stateIndex] ?? initialValue
    return React.useState(value)
  },
}

function compileModule(sourceUrl, mocks = {}) {
  const source = readFileSync(sourceUrl, 'utf8')
  const { outputText } = ts.transpileModule(source, {
    compilerOptions: {
      module: ts.ModuleKind.CommonJS,
      target: ts.ScriptTarget.ES2022,
      jsx: ts.JsxEmit.ReactJSX,
    },
  })
  const module = { exports: {} }
  const mockModules = {
    react: reactForPage,
    'react/jsx-runtime': require('react/jsx-runtime'),
    'react-dom/server': { renderToStaticMarkup },
    'lucide-react': {
      Activity: wrapper('svg'),
      ChevronDown: wrapper('svg'),
      ChevronUp: wrapper('svg'),
      RefreshCcw: wrapper('svg'),
    },
    'react-router-dom': {
      Link: wrapper('a'),
      useParams: () => ({ studentId: String(activeStudentId) }),
    },
    '@/context/AuthContext': { useAuth: () => ({ hasRole: () => false }) },
    '@/hooks/useDashboard': () => ({
      useDashboard: () => ({ dashboard: activeDashboard, loading: false, error: '', reload: async () => {} }),
    }),
    '@/lib/api': { api: { getStudent: async () => null } },
    '@/components/common/EmptyState': { EmptyState },
    '@/components/common/ErrorState': { ErrorState: wrapper('div') },
    '@/components/common/LoadingState': { LoadingState: wrapper('div') },
    '@/components/common/PullToRefresh': { PullToRefresh: wrapper('div') },
    '@/components/ui/badge': { Badge: wrapper('span') },
    '@/components/ui/button': { Button: wrapper('button') },
    '@/components/ui/card': {
      Card: wrapper('article'),
      CardAction: wrapper('div'),
      CardContent: wrapper('div'),
      CardDescription: wrapper('p'),
      CardHeader: wrapper('header'),
      CardTitle: wrapper('h2'),
    },
    '@/components/features/AttendanceDayBadge': compileAttendanceBadge,
    'react-i18next': {
      useTranslation: () => ({
        t: (key) => {
          const label = attendanceLabels[key]
          assert.ok(label, `Missing test translation for ${key}`)
          return label
        },
      }),
    },
    ...mocks,
  }
  const loadModule = (specifier) => {
    if (Object.hasOwn(mockModules, specifier)) {
      const mocked = mockModules[specifier]
      return typeof mocked === 'function' ? mocked() : mocked
    }
    throw new Error(`Unexpected page dependency: ${specifier}`)
  }

  vm.runInNewContext(outputText, {
    module,
    exports: module.exports,
    require: loadModule,
    process,
    console,
  }, { filename: sourceUrl.pathname })
  return module.exports
}

function compileAttendanceBadge() {
  return compileModule(new URL('src/components/features/AttendanceDayBadge.tsx', currentDirectory))
}

const { DashboardPage } = compileModule(new URL('src/pages/DashboardPage.tsx', currentDirectory))
const { StudentDetailPage } = compileModule(new URL('src/pages/StudentDetailPage.tsx', currentDirectory))

function dashboardData(attendanceToday = []) {
  return {
    role: 'parent',
    generated_at: '2026-10-04T12:00:00Z',
    today_schedule: [],
    upcoming_assignments: [],
    recent_grades: [],
    attendance_today: attendanceToday,
    pacing_alerts: [],
    compliance_warnings: [],
    system_status: null,
    student_summaries: attendanceToday.map((item) => ({
      student_id: item.student_id,
      student_name: item.student_name,
      current_gpa: null,
      attendance_rate: null,
      assignments_due_count: 0,
      past_due_count: 0,
      pacing_status: null,
      compliance_status: null,
    })),
  }
}

function attendanceRecord(studentId, studentName, isInstructionalDay) {
  return {
    student_id: studentId,
    student_name: studentName,
    date: '2026-10-04',
    is_instructional_day: isInstructionalDay,
    instructional_hours: null,
    notes: null,
  }
}

function renderDashboard(data) {
  activeDashboard = data
  return renderToStaticMarkup(React.createElement(DashboardPage))
}

function renderStudentDetail(data, studentId, studentName) {
  activeDashboard = data
  activeStudentId = studentId
  studentState = {
    index: 0,
    values: [
      { id: studentId, name: studentName },
      false,
      '',
    ],
  }
  try {
    return renderToStaticMarkup(React.createElement(StudentDetailPage))
  } finally {
    studentState = undefined
  }
}

test('DashboardPage renders all API attendance day values with explicit labels', () => {
  const rows = [
    attendanceRecord(1, 'Ada', true),
    attendanceRecord(2, 'Grace', false),
    attendanceRecord(3, 'Katherine', null),
  ]
  const markup = renderDashboard(dashboardData(rows))

  assert.match(markup, /Ada/)
  assert.match(markup, /Instructional day/)
  assert.match(markup, /Grace/)
  assert.match(markup, /Non-instructional day/)
  assert.match(markup, /Katherine/)
  assert.match(markup, /Not recorded/)
})

test('StudentDetailPage renders the API attendance day value with its explicit label', () => {
  for (const [studentId, studentName, dayValue, label] of [
    [1, 'Ada', true, 'Instructional day'],
    [2, 'Grace', false, 'Non-instructional day'],
    [3, 'Katherine', null, 'Not recorded'],
  ]) {
    const markup = renderStudentDetail(
      dashboardData([attendanceRecord(studentId, studentName, dayValue)]),
      studentId,
      studentName,
    )
    assert.match(markup, new RegExp(studentName))
    assert.match(markup, new RegExp(label))
  }
})

test('both pages retain their empty states when dashboard collections are empty', () => {
  const emptyDashboard = dashboardData()
  const dashboardMarkup = renderDashboard(emptyDashboard)
  assert.match(dashboardMarkup, /Nothing scheduled today/)
  assert.match(dashboardMarkup, /No attendance yet/)

  const studentMarkup = renderStudentDetail(emptyDashboard, 1, 'Ada')
  assert.match(studentMarkup, /No schedule today/)
  assert.match(studentMarkup, /No attendance recorded/)
})
