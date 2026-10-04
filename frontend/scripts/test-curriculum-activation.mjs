import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'
import ts from 'typescript'

const source = readFileSync(new URL('../src/lib/curriculumActivation.ts', import.meta.url), 'utf8')
const { outputText } = ts.transpileModule(source, {
  compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 },
})
const { MISSING_ACTIVE_SCHOOL_YEAR_MESSAGE, resolveCurriculumActivationPayload } = await import(
  `data:text/javascript;base64,${Buffer.from(outputText).toString('base64')}`
)

const years = [
  { id: 3, is_active: false },
  { id: 7, is_active: true },
]

test('uses the active school year when no payload is provided', async () => {
  assert.deepEqual(await resolveCurriculumActivationPayload(undefined, async () => years), { school_year_id: 7 })
})

test('adds the active school year while preserving other activation options', async () => {
  assert.deepEqual(await resolveCurriculumActivationPayload({ generate_assignments: true }, async () => years), {
    generate_assignments: true,
    school_year_id: 7,
  })
})

test('preserves an explicit school year without looking up school years', async () => {
  let calls = 0
  const payload = { school_year_id: 3, create_missing_subjects: false }
  const resolved = await resolveCurriculumActivationPayload(payload, async () => {
    calls += 1
    return years
  })
  assert.deepEqual(resolved, payload)
  assert.equal(calls, 0)
})

test('fails with an explicit error when there is no active school year', async () => {
  await assert.rejects(
    resolveCurriculumActivationPayload(undefined, async () => [{ id: 3, is_active: false }]),
    { message: MISSING_ACTIVE_SCHOOL_YEAR_MESSAGE },
  )
})
