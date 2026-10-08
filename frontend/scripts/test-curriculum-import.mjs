import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'
import vm from 'node:vm'
import ts from 'typescript'

function compile(name, dependencies = {}, globals = {}) {
  const source = readFileSync(new URL(name.includes('\\') ? `../src/${name}` : `../src/lib/${name}.ts`, import.meta.url), 'utf8')
  const { outputText } = ts.transpileModule(source.replaceAll('import.meta.env', '__env'), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, jsx: ts.JsxEmit.ReactJSX },
  })
  const module = { exports: {} }
  vm.runInNewContext(outputText, {
    module, exports: module.exports, require: (name) => {
      assert.ok(Object.hasOwn(dependencies, name), `Unexpected import: ${name}`)
      return dependencies[name]
    },
    Date, FormData, File, crypto, Headers, Response, console,
    setTimeout: (...args) => setTimeout(...args), clearTimeout: (...args) => clearTimeout(...args),
    ...globals,
  })
  return module.exports
}

const errors = compile('apiError')
const imports = compile('curriculumImport')
const sessions = compile('curriculumImportSession')
const casefold = compile('curriculumCasefold')
const storage = new Map()
const mock = compile('curriculumImportMock', {
  '@/lib/apiError': errors, '@/lib/curriculumImport': imports,
  '@/lib/curriculumCasefold': casefold,
}, { window: { localStorage: { getItem: (key) => storage.get(key), setItem: (key, value) => storage.set(key, value) } } })
const apiMock = mock.curriculumImportMockApi
const { CurriculumSessionRunner, duplicatesAcknowledged, CURRICULUM_POLL_MS } = sessions
const flush = () => new Promise((resolve) => setImmediate(resolve))
const copy = (value) => JSON.parse(JSON.stringify(value))

test('casefold matches the generated Python baseline for every Unicode code point', () => {
  const fixture = JSON.parse(readFileSync(new URL('./curriculum-casefold-fixture.json', import.meta.url), 'utf8'))
  assert.equal(fixture.unicode_version, '15.1.0')
  for (const [char, expected] of fixture.overrides) {
    assert.equal(casefold.pythonCasefold(char), expected, `Override U+${char.codePointAt(0).toString(16)}`)
  }
  const expectedFolds = new Map(fixture.folds)
  for (let codePoint = 0; codePoint <= 0x10ffff; codePoint++) {
    const char = String.fromCodePoint(codePoint)
    const actual = casefold.pythonCasefold(char)
    const expected = expectedFolds.get(char) ?? char
    if (actual !== expected) assert.equal(actual, expected, `U+${codePoint.toString(16)}`)
  }
  // Folding is per code point, not context-sensitive lowercase (Greek final sigma).
  assert.equal(casefold.pythonCasefold('ΟΣ'), 'οσ')
})

function duplicateDocument(metadata = {}, subjectMetadata = {}, subjectName = 'Science') {
  return {
    name: 'Candidate', metadata,
    subjects: [{
      name: subjectName, metadata: subjectMetadata,
      units: [{ name: 'Plants', lessons: [{ name: 'Roots' }, { name: 'Leaves' }] }],
    }],
  }
}

function duplicateMatches(candidate, stored) {
  return mock.findMockDuplicateMatches(candidate, [{ id: 101, name: 'Stored', payload: stored }])
}

test('candidate subject extension edition is ignored, with catalog edition fallback', () => {
  const stored = duplicateDocument({ edition: '2026' })
  const extensionOnly = { extensions: { edition: '2027' } }
  assert.equal(duplicateMatches(duplicateDocument({}, extensionOnly), stored)[0].reason, 'exact_curriculum')
  assert.equal(duplicateMatches(duplicateDocument({ edition: '2026' }, extensionOnly), stored)[0].reason, 'exact_curriculum')
  assert.equal(duplicateMatches(duplicateDocument({ edition: '2027' }, { extensions: { edition: '2026' } }), stored).length, 0)
  assert.equal(duplicateMatches(duplicateDocument({ edition: '2027' }, { edition: '2026', ...extensionOnly }), stored)[0].reason, 'exact_curriculum')
})

test('candidate catalog metadata extensions and stored tree editions follow distinct backend paths', () => {
  const stored = duplicateDocument({ edition: '2026' })
  assert.equal(duplicateMatches(duplicateDocument({ extensions: { edition: '2027' } }), stored).length, 0)
  assert.equal(duplicateMatches(duplicateDocument({ extensions: { extensions: { edition: '2027' } } }), stored).length, 0)
  assert.equal(duplicateMatches(duplicateDocument({ edition: '2026', extensions: { edition: '2027' } }), stored)[0].reason, 'exact_curriculum')
  assert.equal(duplicateMatches(duplicateDocument({ edition: '', extensions: { edition: '2026' } }), stored)[0].reason, 'exact_curriculum')

  const storedSubjectExtension = duplicateDocument({ edition: '2026' }, { extensions: { edition: '2027' } })
  assert.equal(duplicateMatches(duplicateDocument({ edition: '2026' }), storedSubjectExtension).length, 0)
  assert.equal(duplicateMatches(duplicateDocument({ edition: '2026' }, { edition: '2027' }), storedSubjectExtension)[0].reason, 'exact_curriculum')
  assert.equal(duplicateMatches(duplicateDocument({ edition: '2026' }, { extensions: { edition: '2027' } }), storedSubjectExtension).length, 0)
  const storedSubjectExplicit = duplicateDocument({ edition: '2026' }, { edition: '2026', extensions: { edition: '2027' } })
  assert.equal(duplicateMatches(duplicateDocument({ edition: '2026' }), storedSubjectExplicit)[0].reason, 'exact_curriculum')
  const storedCatalogExtension = duplicateDocument({ extensions: { edition: '2026' } })
  const matches = duplicateMatches(duplicateDocument({ edition: '2026' }), storedCatalogExtension)
  assert.equal(matches[0].edition, '2026')
  assert.equal(duplicateMatches(duplicateDocument({ edition: '2027' }), storedCatalogExtension).length, 0)
  // Stored lookup inspects only one extension level; candidate catalog lookup can inspect two.
  const storedNestedExtension = duplicateDocument({ extensions: { extensions: { edition: '2026' } } })
  assert.equal(duplicateMatches(duplicateDocument({ edition: '2027' }), storedNestedExtension)[0].edition, null)
})

test('structural names normalize NFKC plus full Python casefold expansions and Cherokee', () => {
  for (const [name, folded] of [
    ['\u0345', 'ι'],
    ['Straße', 'strasse'],
    ['ᾈ', 'ἀι'],
    ['ΐ', 'ι\u0308\u0301'],
    ['ﬃ', 'ffi'],
    ['Ꭰꭰ', 'ᎠᎠ'],
    ['ΟΣ', 'οσ'],
  ]) {
    const matches = duplicateMatches(duplicateDocument({}, {}, name), duplicateDocument({}, {}, folded))
    assert.equal(matches[0]?.reason, 'exact_curriculum', `Expected matching subject ${name}`)
    const candidate = duplicateDocument()
    candidate.subjects[0].units[0].name = name
    candidate.subjects[0].units[0].lessons[0].name = name
    const stored = copy(candidate)
    stored.subjects[0].units[0].name = folded
    stored.subjects[0].units[0].lessons[0].name = folded
    assert.equal(duplicateMatches(candidate, stored)[0]?.reason, 'exact_curriculum', `Expected matching unit and lesson ${name}`)
  }
})

function session(status = 'processing', overrides = {}) {
  return {
    id: 'session-1', status, source_kind: 'file', source_name: 'outline.txt', warnings: [], revision: 1,
    expires_at: new Date(Date.now() + 600000).toISOString(),
    created_at: new Date().toISOString(), updated_at: new Date().toISOString(),
    draft: status === 'ready' ? imports.buildCurriculumImportExample() : null, error: null, ...overrides,
  }
}

test('polls every two seconds, emits processing then ready, and stops', async (t) => {
  t.mock.timers.enable({ apis: ['setTimeout'] })
  const updates = []
  let polls = 0
  const runner = new CurriculumSessionRunner(async () => {})
  const result = runner.run(async () => session(), async () => {
    polls++
    return session(polls === 2 ? 'ready' : 'processing')
  }, (value) => updates.push(value.status))
  await flush()
  assert.equal(CURRICULUM_POLL_MS, 2000)
  t.mock.timers.tick(1999)
  await flush()
  assert.equal(polls, 0)
  t.mock.timers.tick(1)
  await flush()
  assert.equal(polls, 1)
  t.mock.timers.tick(2000)
  assert.equal((await result).status, 'ready')
  t.mock.timers.tick(10000)
  assert.equal(polls, 2)
  assert.deepEqual(updates, ['processing', 'processing', 'ready'])
  runner.confirmed()
  await runner.cancel()
})

test('failed and expired sessions are terminal; expiry prevents endless polling', async () => {
  for (const status of ['failed', 'expired']) {
    let polls = 0
    const runner = new CurriculumSessionRunner(async () => {})
    assert.equal((await runner.run(async () => session(status), async () => { polls++ }, () => {})).status, status)
    assert.equal(polls, 0)
    await runner.cancel()
  }
  const runner = new CurriculumSessionRunner(async () => {})
  const result = await runner.run(async () => session('processing', { expires_at: new Date(0).toISOString() }), async () => {
    throw new Error('Must not poll an expired session')
  }, () => {})
  assert.equal(result.status, 'expired')
  await runner.cancel()
})

test('closing during create deletes the late session and never emits a stale draft', async () => {
  let resolveCreate
  const removed = []
  const updates = []
  const runner = new CurriculumSessionRunner(async (id) => { removed.push(id) })
  const result = runner.run(() => new Promise((resolve) => { resolveCreate = resolve }), async () => session('ready'), (value) => updates.push(value))
  await flush()
  await runner.cancel()
  resolveCreate(session('ready'))
  assert.equal(await result, null)
  assert.deepEqual(removed, ['session-1'])
  assert.equal(updates.length, 0)
})

test('cancel during poll clears timers and ignores late poll completion', async (t) => {
  t.mock.timers.enable({ apis: ['setTimeout'] })
  let resolvePoll
  const removed = []
  const updates = []
  const runner = new CurriculumSessionRunner(async (id) => { removed.push(id) })
  const result = runner.run(async () => session(), () => new Promise((resolve) => { resolvePoll = resolve }), (value) => updates.push(value.status))
  await flush()
  t.mock.timers.tick(2000)
  await flush()
  await runner.cancel()
  resolvePoll(session('ready'))
  assert.equal(await result, null)
  assert.deepEqual(updates, ['processing'])
  assert.deepEqual(removed, ['session-1'])
})

test('cancel while waiting exits without polling; confirmed sessions are never deleted', async () => {
  let polls = 0
  let removed = 0
  const runner = new CurriculumSessionRunner(async () => { removed++ })
  const result = runner.run(async () => session(), async () => { polls++ }, () => {})
  await flush()
  await runner.cancel()
  assert.equal(await result, null)
  assert.equal(polls, 0)
  assert.equal(removed, 1)
  await runner.run(async () => session('ready'), async () => {}, () => {})
  runner.confirmed()
  await runner.cancel()
  assert.equal(removed, 1)
})

test('failed remote cancellation retains session ID so cancellation can be retried', async () => {
  let calls = 0
  const runner = new CurriculumSessionRunner(async () => { if (++calls === 1) throw new Error('offline') })
  await runner.run(async () => session('ready'), async () => {}, () => {})
  await assert.rejects(runner.cancel(), /offline/)
  await runner.cancel()
  assert.equal(calls, 2)
})

test('duplicate errors retain structured matches/code/details from actual envelopes', () => {
  const matches = [{ id: 7, name: 'Existing', grade_levels: ['6'], edition: '2025', reason: 'Matching lessons',
    matched_subjects: ['Science'], matched_units: ['Cells'], matched_lessons: ['One', 'Two'] }]
  for (const payload of [
    { detail: 'Review matches', code: 'curriculum_import_duplicate_conflict', matches },
    { error: { message: 'Review matches', code: 'curriculum_import_duplicate_conflict', details: { matches } } },
    { detail: { message: 'Review matches', code: 'curriculum_import_duplicate_conflict', matches } },
  ]) {
    const error = errors.parseApiError(409, payload)
    assert.equal(error.message, 'Review matches')
    assert.equal(error.code, 'curriculum_import_duplicate_conflict')
    assert.deepEqual(error.matches, matches)
    assert.equal(error.status, 409)
  }
  assert.equal(errors.parseApiError(422, { detail: [{ msg: 'Invalid' }] }).message, 'Request failed (422)')
})

test('acknowledgement requires every CURRENT duplicate ID, not stale IDs', () => {
  assert.equal(duplicatesAcknowledged([{ id: 1 }, { id: 2 }], [1]), false)
  assert.equal(duplicatesAcknowledged([{ id: 2 }], [1]), false)
  assert.equal(duplicatesAcknowledged([{ id: 1 }, { id: 2 }], [1, 2]), true)
  assert.equal(duplicatesAcknowledged([], []), true)
})

test('mock duplicates ignore filenames/title cosmetics, preserve editions/grades/standards and detect partial lessons', async () => {
  storage.clear()
  const draft = imports.buildCurriculumImportExample()
  draft.metadata = { ...draft.metadata, edition: '2026' }
  const existing = await apiMock.import(draft)
  const renamed = copy(draft)
  renamed.name = 'Different filename and title'
  renamed.metadata.external_source = { input_label: 'another-file.pdf' }
  const matches = (await apiMock.duplicateCheck(renamed)).matches
  assert.equal(matches.length, 1)
  assert.equal(matches[0].id, existing.id)
  assert.equal(matches[0].edition, '2026')
  assert.ok(matches[0].matched_lessons.length)
  for (const metadata of [{ edition: '2027' }, { grade_levels: ['12'] }, { standards_alignment: ['Other standard'] }]) {
    const changed = copy(renamed)
    changed.metadata = { ...changed.metadata, ...metadata }
    if (metadata.grade_levels) changed.grade_levels = metadata.grade_levels
    if (metadata.standards_alignment) changed.standards_alignment = metadata.standards_alignment
    assert.equal((await apiMock.duplicateCheck(changed)).matches.length, 0)
  }
  const partial = copy(renamed)
  partial.subjects[0].units[0].lessons.push({ name: 'An additional lesson' })
  const partialMatches = (await apiMock.duplicateCheck(partial)).matches
  assert.equal(partialMatches.length, 1)
  assert.equal(partialMatches[0].reason, 'partial_overlap')
  assert.ok(!partialMatches[0].matched_lessons.includes('An additional lesson'))
  assert.equal(storage.size, 1)
})

test('mock duplicate matching follows backend normalization, optional metadata, and generic lesson rules', async () => {
  storage.clear()
  const draft = imports.buildCurriculumImportExample()
  draft.metadata = { ...draft.metadata, edition: '3rd Edition', grade_levels: ['4th Grade'], standards_alignment: ['CCSS.MATH.4.NF'] }
  draft.grade_levels = ['4th Grade']
  draft.standards_alignment = ['CCSS.MATH.4.NF']
  draft.subjects[0].name = 'Straße'
  draft.subjects[0].units[0].lessons[0].name = 'Student’s Guide'
  const existing = await apiMock.import(draft)

  const equivalent = copy(draft)
  equivalent.name = 'Different import'
  equivalent.metadata = { ...equivalent.metadata, edition: '3rd edition', grade_levels: ['grade 4'], standards_alignment: ['ccss.math.4.nf'] }
  equivalent.grade_levels = ['grade 4']
  equivalent.standards_alignment = ['ccss.math.4.nf']
  equivalent.subjects[0].name = 'STRASSE'
  equivalent.subjects[0].units[0].lessons[0].name = 'Students Guide'
  assert.equal((await apiMock.duplicateCheck(equivalent)).matches[0].id, existing.id)

  const metadataOmitted = copy(draft)
  delete metadataOmitted.metadata.edition
  delete metadataOmitted.metadata.grade_levels
  delete metadataOmitted.metadata.standards_alignment
  delete metadataOmitted.grade_levels
  delete metadataOmitted.standards_alignment
  assert.equal((await apiMock.duplicateCheck(metadataOmitted)).matches[0].id, existing.id)

  const differentSubjectGrades = copy(draft)
  differentSubjectGrades.subjects.forEach((subject) => {
    subject.metadata = { ...subject.metadata, grade_levels: ['12'] }
  })
  assert.equal((await apiMock.duplicateCheck(differentSubjectGrades)).matches.length, 0)

  const differentSubjectEdition = copy(draft)
  differentSubjectEdition.subjects.forEach((subject) => {
    subject.metadata = { ...subject.metadata, edition: '4th Edition' }
  })
  assert.equal((await apiMock.duplicateCheck(differentSubjectEdition)).matches.length, 0)

  storage.clear()
  const genericOnly = copy(draft)
  genericOnly.subjects.forEach((subject) => subject.units.forEach((unit) => {
    unit.lessons.forEach((lesson, index) => { lesson.name = `Lesson ${index + 1}` })
  }))
  await apiMock.import(genericOnly)
  assert.equal((await apiMock.duplicateCheck({ ...copy(genericOnly), name: 'Generic copy' })).matches.length, 0)

  storage.clear()
  const specific = imports.buildCurriculumImportExample()
  let genericIndex = 0
  specific.subjects.forEach((subject) => subject.units.forEach((unit) => {
    unit.lessons.forEach((lesson) => { lesson.name = `Lesson ${++genericIndex}` })
  }))
  specific.subjects[0].units[0].lessons[0].name = 'Adding Fractions'
  specific.subjects[0].units[0].lessons[1].name = 'Subtracting Fractions'
  const specificExisting = await apiMock.import(specific)
  const oneSharedSpecific = copy(specific)
  oneSharedSpecific.name = 'Only one specific lesson'
  oneSharedSpecific.subjects[0].units[0].lessons[1].name = 'Lesson 2'
  oneSharedSpecific.subjects[0].units[0].lessons.push({ name: 'Lesson 99' })
  assert.equal((await apiMock.duplicateCheck(oneSharedSpecific)).matches.length, 0)
  const mixedPartial = copy(specific)
  mixedPartial.name = 'Two specific lessons and generic names'
  mixedPartial.subjects[0].units[0].lessons.push({ name: 'Lesson 99' })
  const partial = (await apiMock.duplicateCheck(mixedPartial)).matches
  assert.equal(partial[0].id, specificExisting.id)
  assert.ok(!partial[0].matched_lessons.includes('Lesson 1'))
})

test('mock manual confirmation never saves without acknowledgement, and name conflict cannot be overridden', async () => {
  storage.clear()
  const draft = imports.buildCurriculumImportExample()
  const existing = await apiMock.import(draft)
  const renamed = { ...draft, name: 'Separate import', extensions: { preserve: 'all custom fields' }, metadata: { ...draft.metadata, edition: '' } }
  await assert.rejects(apiMock.confirmImport({ draft: renamed, acknowledged_duplicate_ids: [] }),
    (error) => error instanceof errors.ApiError && error.code === 'curriculum_import_duplicate_conflict' && error.matches[0].id === existing.id)
  assert.equal((await apiMock.list()).length, 1)
  await assert.rejects(apiMock.confirmImport({ draft, acknowledged_duplicate_ids: [existing.id] }),
    (error) => error.code === 'curriculum_name_conflict')
  const imported = await apiMock.confirmImport({ draft: renamed, acknowledged_duplicate_ids: [existing.id] })
  assert.equal((await apiMock.list()).length, 2)
  assert.equal(imported.payload.extensions.preserve, 'all custom fields')
  assert.equal(draft.name, existing.name)
})

test('mock AI session supports processing, cancellation, revision, expiry and explicit confirmation', async () => {
  storage.clear()
  const cancelled = await apiMock.createSession({ url: 'https://example.com/cancelled' })
  assert.equal(cancelled.status, 'processing')
  await apiMock.deleteSession(cancelled.id)
  await assert.rejects(apiMock.getSession(cancelled.id), (error) => error.status === 404)
  const pending = await apiMock.createSession({ url: 'https://example.com/new' })
  const ready = await apiMock.getSession(pending.id)
  assert.equal(ready.status, 'ready')
  assert.ok(ready.warnings.some((warning) => warning.includes('Development mock')))
  assert.equal((await apiMock.list()).length, 0)
  const payload = { draft: ready.draft, client_revision: ready.revision, acknowledged_duplicate_ids: [] }
  await assert.rejects(apiMock.confirmSession(ready.id, { ...payload, client_revision: 999 }), /revision changed/)
  await apiMock.confirmSession(ready.id, payload)
  assert.equal((await apiMock.getSession(ready.id)).status, 'confirmed')
  await assert.rejects(apiMock.deleteSession(ready.id), (error) => error.status === 409)
  const expiring = await apiMock.createSession({ url: 'https://example.com/expiry' })
  const originalNow = Date.now
  try {
    Date.now = () => originalNow() + 31 * 60 * 1000
    assert.equal((await apiMock.getSession(expiring.id)).status, 'expired')
    await assert.rejects(apiMock.confirmSession(expiring.id, payload), /not ready/)
  } finally { Date.now = originalNow }
  await apiMock.deleteSession(expiring.id)
})

test('API calls use session/preflight/confirm contracts and production errors never use the mock', async () => {
  const calls = []
  let response = new Response(JSON.stringify(session()), { status: 202, headers: { 'content-type': 'application/json' } })
  let fallbacks = 0
  const { api } = compile('api', {
    '@/lib/curriculumActivation': compile('curriculumActivation'),
    '@/lib/apiError': errors, '@/lib/locale': { getCurrentLanguage: () => 'en' },
    '@/lib/curriculumImportMock': { curriculumImportMockApi: new Proxy({}, { get: () => () => { fallbacks++; throw new Error('Unexpected mock fallback') } }) },
  }, {
    __env: { DEV: false }, document: { cookie: '' }, window: { dispatchEvent() {} },
    fetch: async (path, init) => { calls.push({ path, init }); return response.clone() },
  })
  const draft = imports.buildCurriculumImportExample()
  const payload = { draft, acknowledged_duplicate_ids: [7] }
  await api.createCurriculumAiImportSession({ url: 'https://example.com' })
  await api.getCurriculumAiImportSession('session-1')
  response = new Response(null, { status: 204 })
  await api.deleteCurriculumAiImportSession('session-1')
  response = new Response('{}', { status: 201, headers: { 'content-type': 'application/json' } })
  await api.confirmCurriculumAiImportSession('session-1', { ...payload, client_revision: 2 })
  await api.checkCurriculumImportDuplicates(draft)
  await api.confirmCurriculumImport(payload)
  assert.deepEqual(calls.map((call) => call.path), [
    '/api/curriculum/ai-import-sessions', '/api/curriculum/ai-import-sessions/session-1',
    '/api/curriculum/ai-import-sessions/session-1', '/api/curriculum/ai-import-sessions/session-1/confirm',
    '/api/curriculum/import/duplicate-check', '/api/curriculum/import/confirm',
  ])
  assert.deepEqual(JSON.parse(calls[3].init.body), copy({ ...payload, client_revision: 2 }))
  assert.deepEqual(JSON.parse(calls[4].init.body), copy({ draft }))
  assert.deepEqual(JSON.parse(calls[5].init.body), copy(payload))
  response = new Response(JSON.stringify({ detail: 'Matches changed', code: 'curriculum_import_duplicate_conflict', matches: [{ id: 8 }] }),
    { status: 409, headers: { 'content-type': 'application/json' } })
  await assert.rejects(api.confirmCurriculumImport(payload), (error) => error.code === 'curriculum_import_duplicate_conflict' && error.matches[0].id === 8)
  response = new Response('{}', { status: 404, headers: { 'content-type': 'application/json' } })
  await assert.rejects(api.getCurriculumAiImportSession('missing'), (error) => error.status === 404)
  assert.equal(fallbacks, 0)
})

test('edition and unknown fields survive JSON review without normalizing away user edits', () => {
  const draft = imports.buildCurriculumImportExample()
  draft.metadata = { ...draft.metadata, edition: 'Third edition', custom: { preserve: true } }
  draft.subjects[0].units[0].lessons[0].custom = ['preserve this too']
  const parsed = imports.parseCurriculumImportJson(JSON.stringify(draft))
  assert.deepEqual(copy(parsed.raw), copy(draft))
  assert.equal(parsed.normalized.metadata.edition, 'Third edition')
  assert.equal(imports.toCurriculumImportPayload(parsed.normalized).metadata.edition, 'Third edition')
})

function wizardHarness(api) {
  const hooks = []
  let index = 0
  let pendingEffects = []
  const same = (before, after) => before && after && before.length === after.length && before.every((value, index) => Object.is(value, after[index]))
  const react = {
    useState(initial) {
      const slot = index++
      if (!(slot in hooks)) hooks[slot] = typeof initial === 'function' ? initial() : initial
      return [hooks[slot], (value) => { hooks[slot] = typeof value === 'function' ? value(hooks[slot]) : value }]
    },
    useRef(initial) {
      const slot = index++
      if (!(slot in hooks)) hooks[slot] = { current: initial }
      return hooks[slot]
    },
    useMemo(compute, deps) {
      const slot = index++
      if (!same(hooks[slot]?.deps, deps)) hooks[slot] = { value: compute(), deps }
      return hooks[slot].value
    },
    useEffect(effect, deps) {
      const slot = index++
      if (!same(hooks[slot]?.deps, deps)) {
        pendingEffects.push(() => {
          hooks[slot]?.cleanup?.()
          hooks[slot] = { deps, cleanup: effect() }
        })
      }
    },
  }
  const tags = new Proxy({}, { get: (_, name) => name })
  const dependencies = {
    react,
    'react/jsx-runtime': { jsx: (type, props) => ({ type, props }), jsxs: (type, props) => ({ type, props }) },
    'lucide-react': tags, 'react-router-dom': tags,
    '@/context/AuthContext': { useAuth: () => ({ isFeatureEnabled: () => true }) },
    '@/context/CapabilitiesContext': { useCapabilities: () => ({ onlineCurriculumEnabled: true }) },
    '@/lib/api': { api, ApiError: errors.ApiError }, '@/lib/curriculumImportSession': sessions,
    '@/lib/curriculumImport': imports, '@/components/features/CurriculumImportTree': tags,
  }
  for (const name of ['badge', 'button', 'card', 'input', 'label', 'progress', 'tabs', 'textarea']) dependencies[`@/components/ui/${name}`] = tags
  const { CurriculumImportWizard } = compile('components\\features\\CurriculumImportWizard.tsx', dependencies, {
    window: {
      setTimeout: (...args) => setTimeout(...args), clearTimeout: (...args) => clearTimeout(...args),
      setInterval: (...args) => setInterval(...args), clearInterval: (...args) => clearInterval(...args),
    },
  })
  let tree
  const elements = (node) => {
    if (!node || typeof node !== 'object') return []
    if (Array.isArray(node)) return node.flatMap(elements)
    return [node, ...elements(node.props?.children)]
  }
  const text = (node) => {
    if (Array.isArray(node)) return node.map(text).join('')
    return typeof node === 'string' ? node : node && typeof node === 'object' ? text(node.props?.children) : ''
  }
  return {
    render() {
      index = 0
      tree = CurriculumImportWizard({ schema: null, onCancel() {}, onImported() {} })
      const effects = pendingEffects
      pendingEffects = []
      effects.forEach((effect) => effect())
    },
    find(predicate) {
      const found = elements(tree).find(predicate)
      assert.ok(found, 'Expected wizard control was not rendered')
      return found.props
    },
    button(label) { return this.find((node) => node.type === 'Button' && text(node) === label) },
    text() { return text(tree) },
    cleanup() { hooks.forEach((hook) => hook?.cleanup?.()) },
  }
}

test('manual wizard ignores stale preflight, requires current acknowledgement, and preserves edits on changed-match 409', async (t) => {
  t.mock.timers.enable({ apis: ['setTimeout'] })
  const draft = imports.buildCurriculumImportExample()
  draft.metadata = { edition: '2026', extensions: { retained: true } }
  const editedText = JSON.stringify(draft, null, 2)
  let resolveFirstCheck
  let checks = 0
  let confirms = 0
  const match = (id) => ({ id, name: `Existing ${id}`, grade_levels: ['8'], edition: '2026', reason: 'Matching lessons',
    matched_subjects: ['Science'], matched_units: ['Cells'], matched_lessons: ['One', 'Two'] })
  const wizard = wizardHarness({
    deleteCurriculumAiImportSession: async () => {},
    checkCurriculumImportDuplicates: async () => {
      if (++checks === 1) return new Promise((resolve) => { resolveFirstCheck = resolve })
      return { matches: [match(2)] }
    },
    confirmCurriculumImport: async (payload) => {
      confirms++
      assert.equal(payload.draft.metadata.edition, '2026')
      assert.equal(payload.draft.metadata.extensions.retained, true)
      assert.deepEqual(copy(payload.acknowledged_duplicate_ids), [2])
      throw errors.parseApiError(409, { detail: 'Changed', code: 'curriculum_import_duplicate_conflict', matches: [match(3)] })
    },
  })

  try {
    wizard.render()
    wizard.find((node) => node.props?.id === 'curriculum-import-json').onChange({ target: { value: editedText } })
    wizard.render()
    wizard.button('Validate & preview').onClick()
    wizard.render()
    t.mock.timers.tick(350)
    await flush()
    const editor = wizard.find((node) => node.props?.['aria-label'] === 'Curriculum draft JSON')
    editor.onChange({ target: { value: `${editedText}\n` } })
    wizard.render()
    resolveFirstCheck({ matches: [match(1)] })
    await flush()
    wizard.render()
    assert.ok(!wizard.text().includes('Existing 1'))
    t.mock.timers.tick(350)
    await flush()
    wizard.render()
    assert.ok(wizard.text().includes('Existing 2'))
    wizard.button('Continue').onClick()
    wizard.render()
    t.mock.timers.tick(350)
    await flush()
    wizard.render()
    assert.equal(wizard.button('Import curriculum').disabled, true)
    wizard.find((node) => node.type === 'input' && node.props?.type === 'checkbox').onChange({ target: { checked: true } })
    wizard.render()
    assert.equal(wizard.button('Import curriculum').disabled, false)
    await wizard.button('Import curriculum').onClick()
    await flush()
    wizard.render()
    assert.equal(confirms, 1)
    assert.ok(wizard.text().includes('Existing 3'))
    assert.ok(!wizard.text().includes('Existing 2'))
    assert.equal(wizard.button('Import curriculum').disabled, true)
    wizard.button('Back').onClick()
    wizard.render()
    assert.equal(wizard.find((node) => node.props?.['aria-label'] === 'Curriculum draft JSON').value, `${editedText}\n`)
  } finally { wizard.cleanup() }
})

test('AI wizard unmount cancels a late upload without exposing its draft or confirming', async (t) => {
  t.mock.timers.enable({ apis: ['setTimeout', 'setInterval'] })
  let resolveCreate
  let confirms = 0
  const removed = []
  const wizard = wizardHarness({
    createCurriculumAiImportSession: () => new Promise((resolve) => { resolveCreate = resolve }),
    getCurriculumAiImportSession: async () => { throw new Error('Must not poll after unmount') },
    deleteCurriculumAiImportSession: async (id) => { removed.push(id) },
    confirmCurriculumAiImportSession: async () => { confirms++ },
  })
  wizard.render()
  wizard.find((node) => node.type === 'Tabs' && node.props?.value === 'manual').onValueChange('ai')
  wizard.render()
  wizard.find((node) => node.props?.id === 'curriculum-ai-upload').onChange({
    target: { files: [new File(['An outline'], 'outline.txt', { type: 'text/plain' })] },
  })
  wizard.render()
  wizard.button('Analyze curriculum').onClick()
  await flush()
  wizard.render()
  assert.ok(wizard.text().includes('Processing in the background'))
  wizard.cleanup()
  resolveCreate(session('ready'))
  await flush()
  assert.deepEqual(removed, ['session-1'])
  assert.equal(confirms, 0)
})
