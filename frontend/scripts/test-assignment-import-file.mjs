import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'
import ts from 'typescript'

const source = readFileSync(new URL('../src/lib/assignmentImportFile.ts', import.meta.url), 'utf8')
const { outputText } = ts.transpileModule(source, {
  compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 },
})
const { ASSIGNMENT_IMPORT_FILE_TYPES, MAX_ASSIGNMENT_IMPORT_FILE_BYTES, validateAssignmentImportFile } = await import(
  `data:text/javascript;base64,${Buffer.from(outputText).toString('base64')}`
)
const xlsxMime = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'

test('picker advertises XLSX, not legacy XLS', () => {
  assert.ok(ASSIGNMENT_IMPORT_FILE_TYPES.split(',').includes('.xlsx'))
  assert.ok(ASSIGNMENT_IMPORT_FILE_TYPES.split(',').includes(xlsxMime))
  assert.ok(!ASSIGNMENT_IMPORT_FILE_TYPES.split(',').includes('.xls'))
})

test('picker advertises each structured text extension and canonical MIME', () => {
  for (const value of ['.json', '.csv', '.tsv', 'application/json', 'text/csv', 'text/tab-separated-values']) {
    assert.ok(ASSIGNMENT_IMPORT_FILE_TYPES.split(',').includes(value))
  }
})

test('picker/drop accepts structured text with common browser MIME values', () => {
  const types = {
    json: ['application/json', 'text/json', 'text/plain'],
    csv: ['text/csv', 'application/csv', 'text/plain', 'application/vnd.ms-excel'],
    tsv: ['text/tab-separated-values', 'text/tsv', 'text/plain'],
  }
  for (const [extension, mimes] of Object.entries(types)) {
    for (const type of ['', 'application/octet-stream', ...mimes]) {
      assert.equal(validateAssignmentImportFile({
        name: `Plan.${extension.toUpperCase()}`, type: `${type.toUpperCase()}; charset=utf-8`, size: 1024,
      }), null)
    }
    assert.equal(validateAssignmentImportFile({
      name: `plan.${extension}`, type: '', size: MAX_ASSIGNMENT_IMPORT_FILE_BYTES,
    }), null)
    assert.match(validateAssignmentImportFile({
      name: `plan.${extension}`, type: '', size: MAX_ASSIGNMENT_IMPORT_FILE_BYTES + 1,
    }), /10 MB/)
  }
})

test('rejects unsupported extensions and MIME/extension conflicts instead of trusting MIME', () => {
  for (const [name, type] of [
    ['plan.exe', 'application/json'],
    ['plan', 'text/csv'],
    ['plan.xml', 'text/plain'],
    ['plan.json', 'application/pdf'],
    ['plan.csv', 'application/json'],
    ['plan.tsv', 'application/vnd.ms-excel'],
    ['plan.txt', 'application/json'],
    ['plan.pdf', 'text/plain'],
    ['plan.xlsx', 'text/csv'],
  ]) {
    assert.match(validateAssignmentImportFile({ name, type, size: 1024 }), /matching file type/)
  }
})

test('picker/drop validation accepts XLSX with normal or generic browser MIME', () => {
  for (const type of [xlsxMime, '', 'application/octet-stream', 'application/zip']) {
    assert.equal(validateAssignmentImportFile({ name: 'Plan.XLSX', type, size: 1024 }), null)
  }
})

test('rejects legacy, macro-enabled, renamed or mismatched Excel uploads', () => {
  for (const [name, type] of [
    ['plan.xls', 'application/vnd.ms-excel'],
    ['plan.xlsm', xlsxMime],
    ['plan.xlsx', 'text/plain'],
    ['plan.txt', xlsxMime],
  ]) {
    assert.match(validateAssignmentImportFile({ name, type, size: 1024 }), /\.xlsx/)
  }
})

test('retains upload size bounds and original supported formats', () => {
  assert.equal(validateAssignmentImportFile({ name: 'plan.xlsx', type: xlsxMime, size: MAX_ASSIGNMENT_IMPORT_FILE_BYTES }), null)
  assert.match(validateAssignmentImportFile({ name: 'plan.xlsx', type: xlsxMime, size: MAX_ASSIGNMENT_IMPORT_FILE_BYTES + 1 }), /10 MB/)
  for (const [name, type] of [
    ['plan.txt', 'text/plain'],
    ['plan.md', 'text/markdown'],
    ['plan.docx', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'],
    ['plan.pdf', 'application/pdf'],
  ]) {
    assert.equal(validateAssignmentImportFile({ name, type, size: 1024 }), null)
    for (const genericType of ['', 'application/octet-stream']) {
      assert.equal(validateAssignmentImportFile({ name, type: genericType, size: 1024 }), null)
    }
  }
})
