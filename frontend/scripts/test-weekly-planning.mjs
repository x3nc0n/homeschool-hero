import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'
import vm from 'node:vm'
import ts from 'typescript'

function inputHarness(overrides = {}, api = {}) {
  const tags = new Proxy({}, { get: (_, name) => name })
  const source = readFileSync(new URL('../src/components/features/WeeklyPlanningInput.tsx', import.meta.url), 'utf8')
  const { outputText } = ts.transpileModule(source, {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, jsx: ts.JsxEmit.ReactJSX },
  })
  let downloading = false
  const dependencies = {
    react: {
      useState: () => [downloading, (value) => { downloading = value }],
      useRef: (current) => ({ current }),
    },
    'react/jsx-runtime': { jsx: (type, props) => ({ type, props }), jsxs: (type, props) => ({ type, props }) },
    'lucide-react': tags,
    '@/lib/api': { api },
  }
  for (const name of ['button', 'input', 'label', 'textarea']) dependencies[`@/components/ui/${name}`] = tags
  const module = { exports: {} }
  const downloads = []
  const revoked = []
  vm.runInNewContext(outputText, {
    module, exports: module.exports, Error,
    require(name) {
      assert.ok(Object.hasOwn(dependencies, name), `Unexpected dependency ${name}`)
      return dependencies[name]
    },
    document: { createElement: () => {
      const link = { click() { downloads.push({ href: link.href, download: link.download }) } }
      return link
    } },
    URL: { createObjectURL: () => 'blob:template', revokeObjectURL: (url) => revoked.push(url) },
    window: { setTimeout: (callback) => callback() },
  })
  const errors = []
  const props = {
    schoolYears: [{ id: 1, name: '2026-2027' }],
    students: [{ id: 2, name: 'Lucas' }],
    schoolYearId: '1', weekStart: '2026-10-19', studentId: '2', grade: '',
    text: '', file: null, inputMode: 'paste', busy: false,
    onSchoolYear() {}, onWeek() {}, onStudent() {}, onGrade() {}, onText() {}, onFile() {}, onInputMode() {},
    onAnalyze() {}, onError: (error) => errors.push(error),
    ...overrides,
  }
  let tree
  const nodes = (node) => Array.isArray(node) ? node.flatMap(nodes)
    : node && typeof node === 'object' ? [node, ...nodes(node.props?.children)] : []
  const text = (node) => Array.isArray(node) ? node.map(text).join('')
    : typeof node === 'string' ? node : node && typeof node === 'object' ? text(node.props?.children) : ''
  const render = () => { tree = module.exports.WeeklyPlanningInput(props) }
  render()
  return {
    props, errors, downloads, revoked, render,
    all: () => nodes(tree),
    find(predicate) { const node = nodes(tree).find(predicate); assert.ok(node, 'Expected control'); return node.props },
    button(label) { return this.find((node) => node.type === 'Button' && text(node).includes(label)) },
    text: () => text(tree),
  }
}

const flush = () => new Promise((resolve) => setImmediate(resolve))

test('weekly entry requires a selected year, date, and nonempty input', () => {
  for (const props of [
    { text: '' }, { text: '  \n ' }, { text: 'Tuesday - page 25', schoolYearId: '' },
    { text: 'Tuesday - page 25', weekStart: '' }, { inputMode: 'file', file: null },
  ]) assert.equal(inputHarness(props).button('Review weekly plan').disabled ?? true, true)
  assert.equal(inputHarness({ text: 'Tuesday - page 25', busy: true }).button('Preparing draft').disabled, true)
  assert.equal(inputHarness({ text: 'Tuesday - page 25' }).button('Review weekly plan').disabled, false)
  assert.equal(inputHarness({ inputMode: 'file', file: { name: 'plan.xlsx' } }).button('Review weekly plan').disabled, false)
})

test('weekly entry preserves school-year and student choices and emits input changes', () => {
  const changes = []
  const harness = inputHarness({
    onSchoolYear: (value) => changes.push(['year', value]),
    onWeek: (value) => changes.push(['week', value]),
    onStudent: (value) => changes.push(['student', value]),
    onText: (value) => changes.push(['text', value]),
  })
  for (const [id, value] of [
    ['weekly-plan-year', '3'], ['weekly-plan-date', '2026-10-20'],
    ['weekly-plan-student', '2'], ['weekly-plan-text', 'Spelling - page 25'],
  ]) harness.find((node) => node.props?.id === id).onChange({ target: { value } })
  assert.deepEqual(changes, [
    ['year', '3'], ['week', '2026-10-20'], ['student', '2'], ['text', 'Spelling - page 25'],
  ])
})

test('upload mode advertises canonical columns and CSV/XLSX without JSON or legacy XLS', () => {
  const harness = inputHarness({ inputMode: 'file' })
  assert.match(harness.text(), /student, grade, subject, unit, lesson/)
  assert.match(harness.text(), /instructions, and date or day/)
  assert.match(harness.text(), /Templates import without AI/)
  const accept = harness.find((node) => node.props?.id === 'weekly-plan-file').accept.split(',')
  assert.ok(accept.includes('.csv'))
  assert.ok(accept.includes('.xlsx'))
  assert.ok(!accept.includes('.xls'))
  assert.ok(!accept.includes('.json'))
})

test('download buttons request the canonical server templates and release blob URLs', async () => {
  for (const format of ['csv', 'xlsx']) {
    const requests = []
    const harness = inputHarness({ inputMode: 'file' }, {
      downloadWeeklyPlanTemplate: async (value) => { requests.push(value); return {} },
    })
    harness.button(`Download example ${format.toUpperCase()}`).onClick()
    await flush()
    assert.deepEqual(requests, [format])
    assert.deepEqual(harness.downloads, [{ href: 'blob:template', download: `weekly-plan-example.${format}` }])
    assert.deepEqual(harness.revoked, ['blob:template'])
    assert.deepEqual(harness.errors, [''])
  }
})

test('template download failure is displayed, not treated as a successful file', async () => {
  const harness = inputHarness({ inputMode: 'file' }, {
    downloadWeeklyPlanTemplate: async () => { throw new Error('Your session expired. Sign in again.') },
  })
  harness.button('Download example CSV').onClick()
  await flush()
  assert.deepEqual(harness.errors, ['', 'Your session expired. Sign in again.'])
  assert.deepEqual(harness.downloads, [])
})

test('paste and upload mode controls are accessible and preserve user choice', () => {
  const modes = []
  const harness = inputHarness({ onInputMode: (value) => modes.push(value) })
  assert.equal(harness.button('Paste plan')['aria-pressed'], true)
  assert.equal(harness.button('Upload CSV / Excel')['aria-pressed'], false)
  harness.button('Upload CSV / Excel').onClick()
  assert.deepEqual(modes, ['file'])
})

function wizardHarness(api, overrides = {}) {
  const slots = []
  let index = 0
  let effects = []
  const tags = new Proxy({}, { get: (_, name) => name })
  const dependencies = {
    react: {
      useState(initial) {
        const slot = index++
        if (!(slot in slots)) slots[slot] = typeof initial === 'function' ? initial() : initial
        return [slots[slot], (value) => { slots[slot] = typeof value === 'function' ? value(slots[slot]) : value }]
      },
      useRef(value) {
        const slot = index++
        if (!(slot in slots)) slots[slot] = { current: value }
        return slots[slot]
      },
      useMemo(compute) { return compute() },
      useEffect(effect, deps) {
        const slot = index++
        if (!slots[slot] || deps?.some((value, position) => !Object.is(value, slots[slot].deps?.[position]))) {
          effects.push(() => { slots[slot]?.cleanup?.(); slots[slot] = { deps, cleanup: effect() } })
        }
      },
    },
    'react/jsx-runtime': { jsx: (type, props) => ({ type, props }), jsxs: (type, props) => ({ type, props }) },
    'lucide-react': tags,
    '@/lib/api': { api, ApiError: class ApiError extends Error {} },
    '@/lib/assignmentImportFile': { ASSIGNMENT_IMPORT_FILE_TYPES: '.csv,.xlsx', validateAssignmentImportFile: () => null },
    '@/components/features/WeeklyPlanningInput': tags,
    '@/components/features/WeeklyPlanningPreview': tags,
  }
  for (const name of ['badge', 'button', 'card', 'input', 'label', 'progress', 'select', 'table', 'textarea']) {
    dependencies[`@/components/ui/${name}`] = tags
  }
  const source = readFileSync(new URL('../src/components/features/BulkAssignmentImportWizard.tsx', import.meta.url), 'utf8')
  const { outputText } = ts.transpileModule(source, {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, jsx: ts.JsxEmit.ReactJSX },
  })
  const module = { exports: {} }
  vm.runInNewContext(outputText, {
    module, exports: module.exports, Date, Error,
    require(name) { assert.ok(Object.hasOwn(dependencies, name), `Unexpected import ${name}`); return dependencies[name] },
    window: { setInterval: () => 1, clearInterval() {}, setTimeout, clearTimeout },
  })
  const props = {
    subjects: [], students: [{ id: 2, name: 'Lucas' }], gradingPeriods: [],
    schoolYears: [{ id: 1, name: '2026-2027', is_active: true }],
    planningMode: 'weekly', initialDate: '2026-10-20', initialStudentId: 2,
    onClose() {}, onImported() {}, ...overrides,
  }
  let tree
  const nodes = (node) => Array.isArray(node) ? node.flatMap(nodes)
    : node && typeof node === 'object' ? [node, ...nodes(node.props?.children)] : []
  const text = (node) => Array.isArray(node) ? node.map(text).join('')
    : typeof node === 'string' ? node : node && typeof node === 'object' ? text(node.props?.children) : ''
  return {
    render() {
      index = 0
      tree = module.exports.BulkAssignmentImportWizard(props)
      const pending = effects
      effects = []
      pending.forEach((effect) => effect())
    },
    find(predicate) { const node = nodes(tree).find(predicate); assert.ok(node, 'Expected wizard element'); return node.props },
    button(label) { return this.find((node) => node.type === 'Button' && text(node).includes(label)) },
    text: () => text(tree),
    cleanup() { slots.forEach((slot) => slot?.cleanup?.()) },
  }
}

const readyDraft = () => ({
  id: 4, status: 'ready', revision: 1, warnings: [], parse_method: 'weekly_template',
  summary: { total: 1, ready: 1, needs_clarification: 0, invalid: 0 }, questions: [],
  items: [{
    client_item_id: 'row1', title: 'Page 25', description: 'Complete page 25.', due_date: '2026-10-20T00:00:00Z',
    category: 'homework', weight: 1, max_score: 100, recurrence: 'none', status: 'ready',
    targets: [{ student_id: 2, status: 'assigned' }],
  }],
})

test('weekly wizard submits paste context without fabricating a file or creating records', async () => {
  const calls = []
  const wizard = wizardHarness({
    createWeeklyPlanSession: async (input) => { calls.push(input); return readyDraft() },
    getAssignmentImportSession: async () => readyDraft(),
    confirmAssignmentImportSession: async () => { assert.fail('No records may be confirmed during input') },
  })
  try {
    wizard.render()
    wizard.find((node) => node.type === 'WeeklyPlanningInput').onText('Lucas - 7th Grade\nSpelling\nTuesday - page 25')
    wizard.render()
    wizard.find((node) => node.type === 'WeeklyPlanningInput').onAnalyze()
    await flush()
    wizard.render()
    assert.equal(calls.length, 1)
    assert.equal(calls[0].text, 'Lucas - 7th Grade\nSpelling\nTuesday - page 25')
    assert.equal(calls[0].week_start, '2026-10-19')
    assert.equal(calls[0].school_year_id, 1)
    assert.deepEqual(Array.from(calls[0].defaults.student_ids), [2])
    assert.equal(calls[0].file, undefined)
    assert.match(wizard.text(), /Save preview edits/)
  } finally { wizard.cleanup() }
})

test('weekly wizard upload mode sends the selected template, not stale pasted text', async () => {
  const calls = []
  const wizard = wizardHarness({
    createWeeklyPlanSession: async (input) => { calls.push(input); return readyDraft() },
  })
  try {
    wizard.render()
    let input = wizard.find((node) => node.type === 'WeeklyPlanningInput')
    input.onText('Old pasted plan')
    input.onInputMode('file')
    input.onFile({ name: 'plan.xlsx', size: 20, type: '' })
    wizard.render()
    input = wizard.find((node) => node.type === 'WeeklyPlanningInput')
    input.onAnalyze()
    await flush()
    assert.equal(calls.length, 1)
    assert.equal(calls[0].file.name, 'plan.xlsx')
    assert.equal(calls[0].text, undefined)
  } finally { wizard.cleanup() }
})

test('weekly wizard surfaces analysis failures and remains on input', async () => {
  const wizard = wizardHarness({
    createWeeklyPlanSession: async () => { throw new Error('CSV row 2: date and day disagree.') },
  })
  try {
    wizard.render()
    wizard.find((node) => node.type === 'WeeklyPlanningInput').onText('Tuesday - page 25')
    wizard.render()
    wizard.find((node) => node.type === 'WeeklyPlanningInput').onAnalyze()
    await flush()
    wizard.render()
    assert.match(wizard.text(), /CSV row 2: date and day disagree/)
    wizard.find((node) => node.type === 'WeeklyPlanningInput')
  } finally { wizard.cleanup() }
})

function previewHarness(overrides = {}) {
  const tags = new Proxy({}, { get: (_, name) => name })
  const dependencies = {
    'react/jsx-runtime': { jsx: (type, props) => ({ type, props }), jsxs: (type, props) => ({ type, props }) },
  }
  for (const name of ['badge', 'input', 'label', 'textarea']) dependencies[`@/components/ui/${name}`] = tags
  const source = readFileSync(new URL('../src/components/features/WeeklyPlanningPreview.tsx', import.meta.url), 'utf8')
  const { outputText } = ts.transpileModule(source, {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, jsx: ts.JsxEmit.ReactJSX },
  })
  const module = { exports: {} }
  vm.runInNewContext(outputText, {
    module, exports: module.exports,
    require(name) { assert.ok(Object.hasOwn(dependencies, name), `Unexpected import ${name}`); return dependencies[name] },
  })
  const edits = []
  const selections = []
  const item = {
    ...readyDraft().items[0],
    weekly: {
      student: 'Lucas', grade: '7', subject: 'Spelling - 7th Grade', unit: 'Lesson 6',
      lesson: 'Page 25', instructions: 'Complete page 25.', curriculum: 'Spelling 2026',
      scheduled_date: '2026-10-20', day: 'Tuesday', package_id: 12,
      source_location: 'Sheet1!F6', source_week_label: 'Lucas Week 9 October 26-30',
      activity_name: 'Page 25',
      resolution: {
        subject: 'reused', package: 'ambiguous', activity: 'new', lesson_plan: 'new',
        package_choices: [{ id: 12, label: 'Spelling 2026' }, { id: 13, label: 'Spelling enrichment' }],
      },
    },
  }
  const tree = module.exports.WeeklyPlanningPreview({
    items: [item], students: [{ id: 2, name: 'Lucas' }], subjects: [], selectedIds: ['row1'], busy: false,
    onEdit: (id, patch) => edits.push({ id, patch }), onSelect: (id, selected) => selections.push({ id, selected }),
    ...overrides,
  })
  const nodes = (node) => Array.isArray(node) ? node.flatMap(nodes)
    : node && typeof node === 'object' ? [node, ...nodes(node.props?.children)] : []
  const text = (node) => Array.isArray(node) ? node.map(text).join('')
    : typeof node === 'string' ? node : node && typeof node === 'object' ? text(node.props?.children) : ''
  return {
    edits, selections, item, text: () => text(tree),
    find(predicate) { const node = nodes(tree).find(predicate); assert.ok(node, 'Expected preview element'); return node.props },
  }
}

test('weekly preview shows curriculum decisions, source context, and package choices', () => {
  const harness = previewHarness()
  assert.match(harness.text(), /subject: reused/)
  assert.match(harness.text(), /activity: new/)
  assert.match(harness.text(), /package: ambiguous/)
  assert.match(harness.text(), /Lucas Week 9 October 26-30/)
  const packages = harness.find((node) => node.props?.id === 'row1-package-match')
  packages.onChange({ target: { value: '13' } })
  assert.equal(harness.edits[0].patch.weekly.package_id, 13)
  assert.equal(harness.edits[0].patch.weekly.source_location, 'Sheet1!F6')
})

test('editing a school date clears stale weekday context and updates target date', () => {
  const harness = previewHarness()
  harness.find((node) => node.props?.id === 'row1-date').onChange({ target: { value: '2026-10-21' } })
  const { patch } = harness.edits[0]
  assert.equal(patch.due_date, '2026-10-21')
  assert.equal(patch.weekly.scheduled_date, '2026-10-21')
  assert.equal(patch.weekly.day, null)
  assert.equal(patch.targets[0].due_date, '2026-10-21')
})

test('editing curriculum scope clears an obsolete explicit package match', () => {
  for (const field of ['subject', 'grade', 'curriculum']) {
    const harness = previewHarness()
    harness.find((node) => node.props?.id === `row1-${field}`).onChange({ target: { value: 'Changed' } })
    assert.equal(harness.edits[0].patch.weekly[field], 'Changed')
    assert.equal(harness.edits[0].patch.weekly.package_id, null)
    assert.equal(harness.edits[0].patch.weekly.source_location, 'Sheet1!F6')
  }
})

test('weekly preview preserves daily instructions for curriculum and assignment together', () => {
  const harness = previewHarness()
  harness.find((node) => node.props?.id === 'row1-instructions').onChange({ target: { value: 'Complete page 26.' } })
  assert.equal(harness.edits[0].patch.description, 'Complete page 26.')
  assert.equal(harness.edits[0].patch.weekly.instructions, 'Complete page 26.')
  const selection = harness.find((node) => node.props?.['aria-label'] === 'Include Page 25')
  selection.onChange({ target: { checked: false } })
  assert.equal(harness.selections[0].id, 'row1')
  assert.equal(harness.selections[0].selected, false)
})

test('saving a preview does not reselect deliberately skipped rows', async () => {
  let confirmed = false
  const draft = readyDraft()
  const wizard = wizardHarness({
    createWeeklyPlanSession: async () => draft,
    updateAssignmentImportSession: async () => ({ ...draft, revision: 2 }),
    confirmAssignmentImportSession: async () => { confirmed = true },
  })
  try {
    wizard.render()
    wizard.find((node) => node.type === 'WeeklyPlanningInput').onText('Tuesday - page 25')
    wizard.render()
    wizard.find((node) => node.type === 'WeeklyPlanningInput').onAnalyze()
    await flush()
    wizard.render()
    wizard.find((node) => node.type === 'WeeklyPlanningPreview').onSelect('row1', false)
    wizard.render()
    wizard.button('Save preview edits').onClick()
    await flush()
    wizard.render()
    assert.equal(wizard.find((node) => node.type === 'WeeklyPlanningPreview').selectedIds.length, 0)
    assert.equal(wizard.button('Confirm linked weekly plan').disabled, true)
    assert.equal(confirmed, false)
  } finally { wizard.cleanup() }
})
