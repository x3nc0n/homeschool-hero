import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'
import vm from 'node:vm'
import ts from 'typescript'

function compile(path, dependencies = {}, globals = {}) {
  const source = readFileSync(new URL(path, import.meta.url), 'utf8')
  const { outputText } = ts.transpileModule(source, {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, jsx: ts.JsxEmit.ReactJSX },
  })
  const module = { exports: {} }
  vm.runInNewContext(outputText, {
    module, exports: module.exports,
    require(name) {
      assert.ok(Object.hasOwn(dependencies, name), `Unexpected import: ${name}`)
      return dependencies[name]
    },
    Date, FormData, File, crypto, console,
    setTimeout: (...args) => setTimeout(...args),
    clearTimeout: (...args) => clearTimeout(...args),
    ...globals,
  })
  return module.exports
}

const errors = compile('../src/lib/apiError.ts')
const imports = compile('../src/lib/curriculumImport.ts')
const sessions = compile('../src/lib/curriculumImportSession.ts')
const flush = () => new Promise((resolve) => setImmediate(resolve))
const copy = (value) => JSON.parse(JSON.stringify(value))
const match = (id) => ({
  id, name: `Existing ${id}`, grade_levels: ['3'], edition: null, reason: 'exact_curriculum',
  matched_subjects: ['Science'], matched_units: ['Plants'], matched_lessons: ['Roots', 'Leaves'],
})

function wizardHarness(api) {
  const hooks = []
  let index = 0
  let effects = []
  let tree
  const equal = (before, after) => before && after && before.length === after.length && before.every((value, index) => Object.is(value, after[index]))
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
      if (!equal(hooks[slot]?.deps, deps)) hooks[slot] = { deps, value: compute() }
      return hooks[slot].value
    },
    useEffect(effect, deps) {
      const slot = index++
      if (!equal(hooks[slot]?.deps, deps)) effects.push(() => {
        hooks[slot]?.cleanup?.()
        hooks[slot] = { deps, cleanup: effect() }
      })
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
  const { CurriculumImportWizard } = compile('../src/components/features/CurriculumImportWizard.tsx', dependencies, {
    window: {
      setTimeout: (...args) => setTimeout(...args), clearTimeout: (...args) => clearTimeout(...args),
      setInterval: (...args) => setInterval(...args), clearInterval: (...args) => clearInterval(...args),
    },
  })
  const elements = (node) => !node || typeof node !== 'object' ? [] : Array.isArray(node)
    ? node.flatMap(elements) : [node, ...elements(node.props?.children)]
  const text = (node) => Array.isArray(node) ? node.map(text).join('')
    : typeof node === 'string' ? node : node && typeof node === 'object' ? text(node.props?.children) : ''
  return {
    render() {
      index = 0
      tree = CurriculumImportWizard({ schema: null, onCancel() {}, onImported() {} })
      const pending = effects
      effects = []
      pending.forEach((effect) => effect())
    },
    find(predicate) {
      const node = elements(tree).find(predicate)
      assert.ok(node, 'Expected wizard control was not rendered')
      return node.props
    },
    has(predicate) { return elements(tree).some(predicate) },
    button(label) { return this.find((node) => node.type === 'Button' && text(node) === label) },
    text() { return text(tree) },
    cleanup() { hooks.forEach((hook) => hook?.cleanup?.()) },
  }
}

test('actual AI wizard unmount during status polling cancels remotely and rejects the late draft', async (t) => {
  t.mock.timers.enable({ apis: ['setTimeout', 'setInterval'] })
  let resolvePoll
  let confirms = 0
  const removed = []
  const processing = {
    id: 9, status: 'processing', source_kind: 'file', source_name: 'scope.txt', revision: 1,
    warnings: [], draft: null, error: null, expires_at: new Date(Date.now() + 600000).toISOString(),
    created_at: new Date().toISOString(), updated_at: new Date().toISOString(),
  }
  const wizard = wizardHarness({
    createCurriculumAiImportSession: async () => processing,
    getCurriculumAiImportSession: () => new Promise((resolve) => { resolvePoll = resolve }),
    deleteCurriculumAiImportSession: async (id) => { removed.push(id) },
    confirmCurriculumAiImportSession: async () => { confirms++ },
    checkCurriculumImportDuplicates: async () => { throw new Error('Cancelled draft must not reach preflight') },
  })
  try {
    wizard.render()
    wizard.find((node) => node.type === 'Tabs' && node.props?.value === 'manual').onValueChange('ai')
    wizard.render()
    wizard.find((node) => node.props?.id === 'curriculum-ai-upload').onChange({
      target: { files: [new File(['Plants scope'], 'scope.txt', { type: 'text/plain' })] },
    })
    wizard.render()
    wizard.button('Analyze curriculum').onClick()
    await flush()
    wizard.render()
    t.mock.timers.tick(2000)
    await flush()
    assert.equal(typeof resolvePoll, 'function')
    wizard.cleanup()
    await flush()
    assert.deepEqual(removed, [9])
    resolvePoll({ ...processing, status: 'ready', revision: 2, draft: imports.buildCurriculumImportExample() })
    await flush()
    wizard.render()
    assert.equal(wizard.has((node) => node.props?.['aria-label'] === 'Curriculum draft JSON'), false)
    assert.equal(confirms, 0)
  } finally { wizard.cleanup() }
})

test('actual wizard invalidates acknowledged IDs on draft edit and consumes backend error.details.matches', async (t) => {
  t.mock.timers.enable({ apis: ['setTimeout'] })
  const draft = imports.buildCurriculumImportExample()
  let confirms = 0
  const wizard = wizardHarness({
    deleteCurriculumAiImportSession: async () => {},
    checkCurriculumImportDuplicates: async () => ({ matches: [match(11)] }),
    confirmCurriculumImport: async (payload) => {
      confirms++
      assert.deepEqual(copy(payload.acknowledged_duplicate_ids), [11])
      assert.equal(payload.draft.description, 'Reviewed draft edit')
      throw errors.parseApiError(409, {
        detail: 'Review current matches',
        error: { message: 'Review current matches', code: 'curriculum_import_duplicate_conflict', details: { matches: [match(22)] } },
      })
    },
  })
  const settlePreflight = async () => {
    t.mock.timers.tick(350)
    await flush()
    wizard.render()
  }
  const checkbox = () => wizard.find((node) => node.type === 'input' && node.props?.type === 'checkbox')
  try {
    wizard.render()
    wizard.find((node) => node.props?.id === 'curriculum-import-json').onChange({ target: { value: JSON.stringify(draft) } })
    wizard.render()
    wizard.button('Validate & preview').onClick()
    wizard.render()
    await settlePreflight()
    checkbox().onChange({ target: { checked: true } })
    wizard.render()
    assert.equal(checkbox().checked, true)
    const editedText = JSON.stringify({ ...draft, description: 'Reviewed draft edit' }, null, 2)
    wizard.find((node) => node.props?.['aria-label'] === 'Curriculum draft JSON').onChange({ target: { value: editedText } })
    wizard.render()
    await settlePreflight()
    assert.equal(checkbox().checked, false)
    wizard.button('Continue').onClick()
    wizard.render()
    await settlePreflight()
    assert.equal(wizard.button('Import curriculum').disabled, true)
    checkbox().onChange({ target: { checked: true } })
    wizard.render()
    assert.equal(wizard.button('Import curriculum').disabled, false)
    wizard.button('Import curriculum').onClick()
    await flush()
    wizard.render()
    assert.equal(confirms, 1)
    assert.ok(wizard.text().includes('Existing 22'))
    assert.ok(!wizard.text().includes('Existing 11'))
    assert.equal(checkbox().checked, false)
    assert.equal(wizard.button('Import curriculum').disabled, true)
    wizard.button('Back').onClick()
    wizard.render()
    assert.equal(wizard.find((node) => node.props?.['aria-label'] === 'Curriculum draft JSON').value, editedText)
  } finally { wizard.cleanup() }
})

for (const terminalStatus of ['ready', 'failed', 'expired']) {
  test(`actual AI wizard polls processing then ${terminalStatus} and stops`, async (t) => {
    t.mock.timers.enable({ apis: ['setTimeout', 'setInterval'] })
    let polls = 0
    let confirms = 0
    const removed = []
    const session = (status) => ({
      id: 7, status, source_kind: 'file', source_name: 'scope.txt', revision: status === 'processing' ? 1 : 2,
      warnings: [], draft: status === 'ready' ? imports.buildCurriculumImportExample() : null,
      error: status === 'failed' ? { code: 'ai_response_invalid', message: 'Invalid response' } : null,
      expires_at: new Date(Date.now() + 600000).toISOString(),
      created_at: new Date().toISOString(), updated_at: new Date().toISOString(),
    })
    const wizard = wizardHarness({
      createCurriculumAiImportSession: async () => session('processing'),
      getCurriculumAiImportSession: async () => { polls++; return session(terminalStatus) },
      deleteCurriculumAiImportSession: async (id) => { removed.push(id) },
      checkCurriculumImportDuplicates: async () => ({ matches: [] }),
      confirmCurriculumAiImportSession: async () => { confirms++ },
    })
    try {
      wizard.render()
      wizard.find((node) => node.type === 'Tabs' && node.props?.value === 'manual').onValueChange('ai')
      wizard.render()
      wizard.find((node) => node.props?.id === 'curriculum-ai-upload').onChange({
        target: { files: [new File(['Plants scope'], 'scope.txt', { type: 'text/plain' })] },
      })
      wizard.render()
      wizard.button('Analyze curriculum').onClick()
      await flush()
      wizard.render()
      assert.ok(wizard.text().includes('Processing in the background'))
      t.mock.timers.tick(2000)
      await flush()
      wizard.render()
      assert.equal(polls, 1)
      if (terminalStatus === 'ready') {
        assert.ok(wizard.find((node) => node.props?.['aria-label'] === 'Curriculum draft JSON').value)
      } else {
        assert.ok(wizard.text().includes(terminalStatus === 'failed' ? 'Analysis failed.' : 'This analysis session expired.'))
        assert.equal(wizard.button('Start a new analysis').disabled, false)
      }
      t.mock.timers.tick(10000)
      await flush()
      assert.equal(polls, 1)
      assert.equal(confirms, 0)
    } finally {
      wizard.cleanup()
      await flush()
    }
    assert.deepEqual(removed, [7])
  })
}
