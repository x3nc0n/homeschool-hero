import type {
  CurriculumImportDetail,
  CurriculumImportDocument,
  CurriculumImportLesson,
  CurriculumImportMetadata,
  CurriculumImportResource,
  CurriculumImportSubject,
  CurriculumImportSummary,
  CurriculumImportUnit,
} from '@/types/api'

type JsonObject = Record<string, unknown>

export type NormalizedCurriculumImportMetadata = {
  gradeLevels: string[]
  standardsAlignment: string[]
  prerequisites: string[]
  estimatedHours: number | null
}

export type NormalizedCurriculumImportResource = {
  name: string
  description: string | null
  resourceType: string
  url: string | null
  tags: string[]
}

export type NormalizedCurriculumImportLesson = {
  id: number | null
  name: string
  description: string | null
  sequenceOrder: number
  estimatedMinutes: number | null
  objectives: string[]
  standardsAlignment: string[]
  prerequisites: string[]
  metadata: NormalizedCurriculumImportMetadata
  resources: NormalizedCurriculumImportResource[]
}

export type NormalizedCurriculumImportUnit = {
  id: number | null
  name: string
  description: string | null
  sequenceOrder: number
  metadata: NormalizedCurriculumImportMetadata
  lessons: NormalizedCurriculumImportLesson[]
}

export type NormalizedCurriculumImportSubject = {
  id: number | null
  name: string
  description: string | null
  sequenceOrder: number
  metadata: NormalizedCurriculumImportMetadata
  units: NormalizedCurriculumImportUnit[]
}

export type NormalizedCurriculumImport = {
  id: number | null
  name: string
  description: string | null
  source: string
  schemaVersion: string
  metadata: NormalizedCurriculumImportMetadata
  subjects: NormalizedCurriculumImportSubject[]
  subjectCount: number
  unitCount: number
  lessonCount: number
  estimatedHours: number | null
  isActivated: boolean
  lastActivatedAt: string | null
  createdAt: string | null
  updatedAt: string | null
  payload: JsonObject
}

export type CurriculumImportSource =
  | CurriculumImportDocument
  | CurriculumImportSummary
  | CurriculumImportDetail
  | Record<string, unknown>

function isRecord(value: unknown): value is JsonObject {
  return Boolean(value) && typeof value === 'object' && !Array.isArray(value)
}

function normalizeText(value: unknown) {
  return typeof value === 'string' ? value.trim() : ''
}

function normalizeOptionalText(value: unknown) {
  const normalized = normalizeText(value)
  return normalized || null
}

function normalizeStringArray(value: unknown) {
  if (!Array.isArray(value)) return []
  return value
    .filter((item): item is string => typeof item === 'string')
    .map((item) => item.trim())
    .filter(Boolean)
}

function normalizeNumber(value: unknown) {
  if (typeof value === 'number' && Number.isFinite(value)) return value
  if (typeof value === 'string' && value.trim()) {
    const parsed = Number(value)
    if (Number.isFinite(parsed)) {
      return parsed
    }
  }
  return null
}

function dedupeStrings(values: string[]) {
  const seen = new Set<string>()
  return values.filter((value) => {
    const key = value.toLowerCase()
    if (seen.has(key)) return false
    seen.add(key)
    return true
  })
}

function firstNumber(values: unknown[]) {
  for (const value of values) {
    const normalized = normalizeNumber(value)
    if (normalized != null) {
      return normalized
    }
  }
  return null
}

function readMetadata(source: JsonObject): NormalizedCurriculumImportMetadata {
  const metadata = isRecord(source.metadata) ? source.metadata : {}
  return {
    gradeLevels: dedupeStrings([...normalizeStringArray(source.grade_levels), ...normalizeStringArray(metadata.grade_levels)]),
    standardsAlignment: dedupeStrings([
      ...normalizeStringArray(source.standards_alignment),
      ...normalizeStringArray(metadata.standards_alignment),
    ]),
    prerequisites: dedupeStrings([...normalizeStringArray(source.prerequisites), ...normalizeStringArray(metadata.prerequisites)]),
    estimatedHours: firstNumber([source.estimated_hours, metadata.estimated_hours]),
  }
}

function readEstimatedMinutes(source: JsonObject) {
  const directMinutes = firstNumber([source.estimated_minutes, source.estimated_duration_minutes])
  if (directMinutes != null) {
    return Math.round(directMinutes)
  }
  const metadata = isRecord(source.metadata) ? source.metadata : {}
  const estimatedHours = firstNumber([source.estimated_hours, metadata.estimated_hours])
  return estimatedHours == null ? null : Math.round(estimatedHours * 60)
}

function validateName(value: unknown, label: string) {
  const normalized = normalizeText(value)
  if (!normalized) {
    throw new Error(`${label} is required.`)
  }
  return normalized
}

function normalizeResources(value: unknown) {
  if (!Array.isArray(value)) return []
  return value
    .filter(isRecord)
    .map<NormalizedCurriculumImportResource>((resource) => ({
      name: validateName(resource.name, 'Resource name'),
      description: normalizeOptionalText(resource.description),
      resourceType: normalizeText(resource.resource_type) || 'reference',
      url: normalizeOptionalText(resource.url),
      tags: dedupeStrings(normalizeStringArray(resource.tags)),
    }))
}

function normalizeLesson(value: unknown, index: number): NormalizedCurriculumImportLesson {
  if (!isRecord(value)) {
    throw new Error(`Lesson ${index + 1} is invalid.`)
  }

  const metadata = readMetadata(value)
  return {
    id: normalizeNumber(value.id),
    name: validateName(value.name, `Lesson ${index + 1} name`),
    description: normalizeOptionalText(value.description),
    sequenceOrder: normalizeNumber(value.sequence_order) ?? index + 1,
    estimatedMinutes: readEstimatedMinutes(value),
    objectives: normalizeStringArray(value.objectives),
    standardsAlignment: dedupeStrings([...normalizeStringArray(value.standards_alignment), ...metadata.standardsAlignment]),
    prerequisites: dedupeStrings([...normalizeStringArray(value.prerequisites), ...metadata.prerequisites]),
    metadata,
    resources: normalizeResources(value.resources),
  }
}

function normalizeUnit(value: unknown, index: number): NormalizedCurriculumImportUnit {
  if (!isRecord(value)) {
    throw new Error(`Unit ${index + 1} is invalid.`)
  }

  const rawLessons = Array.isArray(value.lessons) ? value.lessons : []
  if (rawLessons.length === 0) {
    throw new Error(`Unit "${validateName(value.name, `Unit ${index + 1} name`)}" must include at least one lesson.`)
  }

  return {
    id: normalizeNumber(value.id),
    name: validateName(value.name, `Unit ${index + 1} name`),
    description: normalizeOptionalText(value.description),
    sequenceOrder: normalizeNumber(value.sequence_order) ?? index + 1,
    metadata: readMetadata(value),
    lessons: rawLessons.map((lesson, lessonIndex) => normalizeLesson(lesson, lessonIndex)),
  }
}

function normalizeSubject(value: unknown, index: number): NormalizedCurriculumImportSubject {
  if (!isRecord(value)) {
    throw new Error(`Subject ${index + 1} is invalid.`)
  }

  const rawUnits = Array.isArray(value.units) ? value.units : []
  if (rawUnits.length === 0) {
    throw new Error(`Subject "${validateName(value.name, `Subject ${index + 1} name`)}" must include at least one unit.`)
  }

  return {
    id: normalizeNumber(value.id),
    name: validateName(value.name, `Subject ${index + 1} name`),
    description: normalizeOptionalText(value.description),
    sequenceOrder: normalizeNumber(value.sequence_order) ?? index + 1,
    metadata: readMetadata(value),
    units: rawUnits.map((unit, unitIndex) => normalizeUnit(unit, unitIndex)),
  }
}

function summarizeCounts(subjects: NormalizedCurriculumImportSubject[]) {
  return subjects.reduce(
    (summary, subject) => {
      summary.subjectCount += 1
      summary.unitCount += subject.units.length
      summary.lessonCount += subject.units.reduce((unitTotal, unit) => unitTotal + unit.lessons.length, 0)
      summary.totalMinutes += subject.units.reduce(
        (unitTotal, unit) => unitTotal + unit.lessons.reduce((lessonTotal, lesson) => lessonTotal + (lesson.estimatedMinutes ?? 0), 0),
        0,
      )
      return summary
    },
    { subjectCount: 0, unitCount: 0, lessonCount: 0, totalMinutes: 0 },
  )
}

function metadataToPayload(metadata: NormalizedCurriculumImportMetadata): CurriculumImportMetadata {
  return {
    grade_levels: metadata.gradeLevels,
    standards_alignment: metadata.standardsAlignment,
    prerequisites: metadata.prerequisites,
    estimated_hours: metadata.estimatedHours,
  }
}

function lessonToPayload(lesson: NormalizedCurriculumImportLesson): CurriculumImportLesson {
  return {
    name: lesson.name,
    description: lesson.description,
    sequence_order: lesson.sequenceOrder,
    estimated_minutes: lesson.estimatedMinutes,
    objectives: lesson.objectives,
    standards_alignment: lesson.standardsAlignment,
    prerequisites: lesson.prerequisites,
    metadata: metadataToPayload(lesson.metadata),
    resources: lesson.resources.map<CurriculumImportResource>((resource) => ({
      name: resource.name,
      description: resource.description,
      resource_type: resource.resourceType,
      url: resource.url,
      tags: resource.tags,
    })),
  }
}

function unitToPayload(unit: NormalizedCurriculumImportUnit): CurriculumImportUnit {
  return {
    name: unit.name,
    description: unit.description,
    sequence_order: unit.sequenceOrder,
    metadata: metadataToPayload(unit.metadata),
    lessons: unit.lessons.map(lessonToPayload),
  }
}

function subjectToPayload(subject: NormalizedCurriculumImportSubject): CurriculumImportSubject {
  return {
    name: subject.name,
    description: subject.description,
    sequence_order: subject.sequenceOrder,
    metadata: metadataToPayload(subject.metadata),
    units: subject.units.map(unitToPayload),
  }
}

export function normalizeCurriculumImport(input: CurriculumImportSource): NormalizedCurriculumImport {
  if (!isRecord(input)) {
    throw new Error('Curriculum import must be a JSON object.')
  }

  const rawSubjects = Array.isArray(input.subjects) ? input.subjects : []
  if (rawSubjects.length === 0) {
    throw new Error('Curriculum import must include at least one subject.')
  }

  const subjects = rawSubjects.map((subject, index) => normalizeSubject(subject, index))
  const counts = summarizeCounts(subjects)
  const metadata = readMetadata(input)
  const estimatedHours = metadata.estimatedHours ?? (counts.totalMinutes ? Math.round((counts.totalMinutes / 60) * 10) / 10 : null)
  const payload = isRecord(input.payload)
    ? input.payload
    : (toCurriculumImportPayload({
        id: normalizeNumber(input.id),
        name: validateName(input.name, 'Curriculum name'),
        description: normalizeOptionalText(input.description),
        source: normalizeText(input.source) || 'manual',
        schemaVersion: normalizeText(input.schema_version) || '1.0',
        metadata,
        subjects,
        subjectCount: counts.subjectCount,
        unitCount: counts.unitCount,
        lessonCount: counts.lessonCount,
        estimatedHours,
        isActivated: Boolean(input.is_activated),
        lastActivatedAt: normalizeOptionalText(input.last_activated_at),
        createdAt: normalizeOptionalText(input.created_at),
        updatedAt: normalizeOptionalText(input.updated_at),
        payload: {},
      }) as unknown as JsonObject)

  return {
    id: normalizeNumber(input.id),
    name: validateName(input.name, 'Curriculum name'),
    description: normalizeOptionalText(input.description),
    source: normalizeText(input.source) || 'manual',
    schemaVersion: normalizeText(input.schema_version) || '1.0',
    metadata,
    subjects,
    subjectCount: counts.subjectCount,
    unitCount: counts.unitCount,
    lessonCount: counts.lessonCount,
    estimatedHours,
    isActivated: Boolean(input.is_activated) || Boolean(input.last_activated_at),
    lastActivatedAt: normalizeOptionalText(input.last_activated_at),
    createdAt: normalizeOptionalText(input.created_at),
    updatedAt: normalizeOptionalText(input.updated_at),
    payload,
  }
}

export function toCurriculumImportPayload(normalized: NormalizedCurriculumImport): CurriculumImportDocument {
  return {
    schema_version: normalized.schemaVersion,
    name: normalized.name,
    description: normalized.description,
    source: normalized.source,
    metadata: metadataToPayload(normalized.metadata),
    grade_levels: normalized.metadata.gradeLevels,
    standards_alignment: normalized.metadata.standardsAlignment,
    prerequisites: normalized.metadata.prerequisites,
    estimated_hours: normalized.estimatedHours,
    subjects: normalized.subjects.map(subjectToPayload),
  }
}

export function parseCurriculumImportJson(text: string) {
  const trimmed = text.trim()
  if (!trimmed) {
    throw new Error('Paste curriculum JSON or upload a JSON file to continue.')
  }

  let parsed: unknown
  try {
    parsed = JSON.parse(trimmed)
  } catch {
    throw new Error('The uploaded curriculum is not valid JSON.')
  }

  const normalized = normalizeCurriculumImport(parsed as CurriculumImportSource)
  return {
    raw: isRecord(parsed) ? parsed : (toCurriculumImportPayload(normalized) as unknown as JsonObject),
    normalized,
  }
}

export function formatDurationMinutes(value: number | null | undefined) {
  if (value == null) return 'No estimate'
  if (value < 60) return `${value} min`

  const hours = Math.floor(value / 60)
  const minutes = value % 60
  if (minutes === 0) {
    return `${hours} hr${hours === 1 ? '' : 's'}`
  }
  return `${hours} hr ${minutes} min`
}

export function formatEstimatedHours(value: number | null | undefined) {
  if (value == null) return '—'
  return Number.isInteger(value) ? `${value} hrs` : `${value.toFixed(1)} hrs`
}

export function buildCurriculumImportExample(): CurriculumImportDocument {
  return {
    name: 'Biology Foundations',
    description: 'Full-year biology with labs, notebooking, and family field studies.',
    grade_levels: ['8'],
    standards_alignment: ['NGSS-MS-LS1-1', 'OKLA.SCI.8.1'],
    prerequisites: ['General science notebooking'],
    estimated_hours: 132,
    subjects: [
      {
        name: 'Science',
        description: 'Core life-science strand.',
        units: [
          {
            name: 'Cells & Systems',
            description: 'Structure and function of living systems.',
            lessons: [
              {
                name: 'Cell theory',
                description: 'Microscope lab and observation journal.',
                objectives: ['Describe core parts of a cell', 'Compare plant and animal cells'],
                standards_alignment: ['NGSS-MS-LS1-1'],
                prerequisites: ['Lab safety basics'],
                estimated_hours: 1.5,
                resources: [
                  {
                    name: 'Cell sketch notebook page',
                    resource_type: 'note',
                    description: 'Guided notebook template',
                  },
                  {
                    name: 'Microscope warm-up',
                    resource_type: 'link',
                    url: 'https://example.com/microscope-warmup',
                  },
                ],
              },
              {
                name: 'Organelles in action',
                objectives: ['Explain organelle roles in cell survival'],
                estimated_hours: 1.25,
              },
            ],
          },
        ],
      },
    ],
  }
}
