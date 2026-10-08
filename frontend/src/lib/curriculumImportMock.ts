import type {
  CurriculumAiImportSession,
  CurriculumImportConfirmPayload,
  CurriculumDuplicateMatch,
  CurriculumImportActivationPayload,
  CurriculumImportActivationResponse,
  CurriculumAiImportConfirmPayload,
  CurriculumAiImportDraftResponse,
  CurriculumImportDetail,
  CurriculumImportDocument,
  CurriculumImportMetadata,
  CurriculumImportSchema,
  CurriculumImportSubject,
  CurriculumImportSummary,
  CurriculumImportUnit,
  CurriculumImportLesson,
  CurriculumSourceSearchResult,
  CurriculumSourceSummary,
} from '@/types/api'
import { buildCurriculumImportExample, normalizeCurriculumImport } from '@/lib/curriculumImport'
import { ApiError } from '@/lib/apiError'
import { pythonCasefold } from '@/lib/curriculumCasefold'

const STORAGE_KEY = 'homeschool-hero-curriculum-import-mock-v1'

type MockStore = {
  nextId: number
  curricula: CurriculumImportDetail[]
}

type MockLessonBlueprint = {
  name: string
  description?: string
  objectives?: string[]
  estimatedHours?: number
}

type MockUnitBlueprint = {
  name: string
  description?: string
  lessons: MockLessonBlueprint[]
}

type MockSourceCatalogItem = {
  item_id: string
  title: string
  description: string
  subject: string
  grade_levels: string[]
  document: CurriculumImportDocument
}

function defaultStore(): MockStore {
  return { nextId: 1, curricula: [] }
}

function getStorage() {
  if (typeof window === 'undefined') return null
  return window.localStorage
}

function readStore(): MockStore {
  const storage = getStorage()
  if (!storage) return defaultStore()

  try {
    const parsed = JSON.parse(storage.getItem(STORAGE_KEY) || 'null') as MockStore | null
    if (!parsed || !Array.isArray(parsed.curricula) || typeof parsed.nextId !== 'number') {
      return defaultStore()
    }
    return parsed
  } catch {
    return defaultStore()
  }
}

function writeStore(store: MockStore) {
  const storage = getStorage()
  if (!storage) return
  storage.setItem(STORAGE_KEY, JSON.stringify(store))
}

function nowIso() {
  return new Date().toISOString()
}

function metadataFromNormalized(metadata: ReturnType<typeof normalizeCurriculumImport>['metadata']): CurriculumImportMetadata {
  return {
    edition: metadata.edition,
    grade_levels: metadata.gradeLevels,
    standards_alignment: metadata.standardsAlignment,
    prerequisites: metadata.prerequisites,
    estimated_hours: metadata.estimatedHours,
    external_source: {},
    extensions: {},
  }
}

function summarize(detail: CurriculumImportDetail): CurriculumImportSummary {
  return {
    id: detail.id,
    name: detail.name,
    description: detail.description,
    source: detail.source,
    schema_version: detail.schema_version,
    metadata: detail.metadata,
    grade_levels: detail.grade_levels,
    standards_alignment: detail.standards_alignment,
    prerequisites: detail.prerequisites,
    estimated_hours: detail.estimated_hours,
    subject_count: detail.subject_count,
    unit_count: detail.unit_count,
    lesson_count: detail.lesson_count,
    is_activated: detail.is_activated,
    last_activation_summary: detail.last_activation_summary,
    last_activated_at: detail.last_activated_at,
    created_at: detail.created_at,
    updated_at: detail.updated_at,
    created_by_user_id: detail.created_by_user_id,
  }
}

function buildDetail(payload: CurriculumImportDocument | Record<string, unknown>, nextIdStart: number) {
  const normalized = normalizeCurriculumImport(payload)
  let nextId = nextIdStart
  const createdAt = nowIso()

  const subjects = normalized.subjects.map<CurriculumImportSubject>((subject) => {
    const subjectId = nextId++
    const units = subject.units.map<CurriculumImportUnit>((unit) => {
      const unitId = nextId++
      const lessons = unit.lessons.map<CurriculumImportLesson>((lesson) => ({
        id: nextId++,
        name: lesson.name,
        description: lesson.description,
        sequence_order: lesson.sequenceOrder,
        estimated_minutes: lesson.estimatedMinutes,
        objectives: lesson.objectives,
        standards_alignment: lesson.standardsAlignment,
        prerequisites: lesson.prerequisites,
        resources: lesson.resources.map((resource) => ({
          name: resource.name,
          description: resource.description,
          resource_type: resource.resourceType,
          url: resource.url,
          tags: resource.tags,
        })),
        metadata: metadataFromNormalized(lesson.metadata),
        activated_curriculum_lesson_id: null,
        created_at: createdAt,
        updated_at: createdAt,
      }))

      return {
        id: unitId,
        name: unit.name,
        description: unit.description,
        sequence_order: unit.sequenceOrder,
        metadata: metadataFromNormalized(unit.metadata),
        lessons,
        activated_curriculum_unit_id: null,
        created_at: createdAt,
        updated_at: createdAt,
      }
    })

    return {
      id: subjectId,
      name: subject.name,
      description: subject.description,
      sequence_order: subject.sequenceOrder,
      metadata: metadataFromNormalized(subject.metadata),
      units,
      activated_subject_id: null,
      activated_package_id: null,
      created_at: createdAt,
      updated_at: createdAt,
    }
  })

  const detail: CurriculumImportDetail = {
    id: nextId++,
    name: normalized.name,
    description: normalized.description,
    source: normalized.source,
    schema_version: normalized.schemaVersion,
    metadata: metadataFromNormalized(normalized.metadata),
    grade_levels: normalized.metadata.gradeLevels,
    standards_alignment: normalized.metadata.standardsAlignment,
    prerequisites: normalized.metadata.prerequisites,
    estimated_hours: normalized.estimatedHours,
    subject_count: normalized.subjectCount,
    unit_count: normalized.unitCount,
    lesson_count: normalized.lessonCount,
    is_activated: false,
    last_activation_summary: {},
    last_activated_at: null,
    created_at: createdAt,
    updated_at: createdAt,
    created_by_user_id: 0,
    payload: payload as Record<string, unknown>,
    subjects,
  }

  return { detail, nextId }
}

function buildSchema(): CurriculumImportSchema {
  return {
    title: 'CurriculumImportDocument',
    type: 'object',
    required: ['name', 'grade_levels', 'subjects'],
    properties: {
      name: { type: 'string' },
      description: { type: 'string' },
      grade_levels: { type: 'array', items: { type: 'string' } },
      standards_alignment: { type: 'array', items: { type: 'string' } },
      prerequisites: { type: 'array', items: { type: 'string' } },
      estimated_hours: { type: 'number' },
      metadata: { type: 'object', properties: { edition: { type: 'string' } } },
      subjects: { type: 'array', items: { type: 'object' } },
    },
    example: buildCurriculumImportExample(),
  }
}

function cloneDocument<T>(value: T): T {
  return JSON.parse(JSON.stringify(value)) as T
}

function buildSourceDocument({
  source,
  name,
  description,
  gradeLevels,
  subject,
  standardsAlignment,
  prerequisites,
  estimatedHours,
  units,
}: {
  source: string
  name: string
  description: string
  gradeLevels: string[]
  subject: string
  standardsAlignment: string[]
  prerequisites: string[]
  estimatedHours: number
  units: MockUnitBlueprint[]
}): CurriculumImportDocument {
  return {
    name,
    description,
    source,
    grade_levels: gradeLevels,
    standards_alignment: standardsAlignment,
    prerequisites,
    estimated_hours: estimatedHours,
    metadata: {
      grade_levels: gradeLevels,
      standards_alignment: standardsAlignment,
      prerequisites,
      estimated_hours: estimatedHours,
    },
    subjects: [
      {
        name: subject,
        description,
        units: units.map((unit) => ({
          name: unit.name,
          description: unit.description,
          lessons: unit.lessons.map((lesson) => ({
            name: lesson.name,
            description: lesson.description,
            objectives: lesson.objectives ?? [],
            estimated_hours: lesson.estimatedHours ?? 1,
          })),
        })),
      },
    ],
  }
}

const MOCK_SOURCE_CATALOG: Record<string, { summary: CurriculumSourceSummary; items: MockSourceCatalogItem[] }> = {
  openstax: {
    summary: {
      source: 'openstax',
      name: 'OpenStax',
      description: 'Open educational textbooks with structured unit and chapter outlines.',
      website_url: 'https://openstax.org/',
      provider: 'Rice University',
      search_hint: 'biology',
      subjects: ['Science', 'Math', 'Humanities'],
      grade_levels: ['9', '10', '11', '12'],
    },
    items: [
      {
        item_id: 'biology-2e',
        title: 'Biology 2e',
        description: 'Year-long high school biology sequence with labs, reading questions, and unit assessments.',
        subject: 'Science',
        grade_levels: ['9', '10'],
        document: buildSourceDocument({
          source: 'openstax',
          name: 'Biology 2e',
          description: 'Comprehensive biology sequence aligned to major life-science topics.',
          gradeLevels: ['9', '10'],
          subject: 'Science',
          standardsAlignment: ['NGSS-HS-LS1-1', 'NGSS-HS-LS2-3'],
          prerequisites: ['Intro to lab safety'],
          estimatedHours: 144,
          units: [
            {
              name: 'The Chemistry of Life',
              description: 'Core chemistry and cell concepts.',
              lessons: [
                { name: 'Atoms, molecules, and water', objectives: ['Explain how water supports life'], estimatedHours: 1.5 },
                { name: 'Macromolecules', objectives: ['Compare proteins, lipids, and carbohydrates'], estimatedHours: 1.25 },
              ],
            },
            {
              name: 'Cells and Energy',
              description: 'Cell structure, respiration, and photosynthesis.',
              lessons: [
                { name: 'Cell structure and function', estimatedHours: 1.5 },
                { name: 'Photosynthesis and cellular respiration', estimatedHours: 1.75 },
              ],
            },
          ],
        }),
      },
      {
        item_id: 'prealgebra-2e',
        title: 'Prealgebra 2e',
        description: 'Foundational prealgebra with worked examples, practice sets, and review checkpoints.',
        subject: 'Math',
        grade_levels: ['6', '7', '8'],
        document: buildSourceDocument({
          source: 'openstax',
          name: 'Prealgebra 2e',
          description: 'Strengthen number sense and algebra readiness through spiral review.',
          gradeLevels: ['6', '7', '8'],
          subject: 'Mathematics',
          standardsAlignment: ['CCSS.MATH.CONTENT.7.NS.A', 'CCSS.MATH.CONTENT.8.EE.A'],
          prerequisites: ['Comfort with whole-number operations'],
          estimatedHours: 120,
          units: [
            {
              name: 'Whole Numbers and Integers',
              description: 'Build confidence with place value and signed numbers.',
              lessons: [
                { name: 'Place value and order of operations', estimatedHours: 1.25 },
                { name: 'Adding and subtracting integers', estimatedHours: 1.5 },
              ],
            },
            {
              name: 'Fractions, Decimals, and Percent',
              description: 'Equivalent forms and real-world applications.',
              lessons: [
                { name: 'Fraction operations', estimatedHours: 1.5 },
                { name: 'Percents in everyday budgeting', estimatedHours: 1.25 },
              ],
            },
          ],
        }),
      },
    ],
  },
  'ck-12': {
    summary: {
      source: 'ck-12',
      name: 'CK-12',
      description: 'Flexible FlexBooks with modular lessons, interactives, and standards tags.',
      website_url: 'https://www.ck12.org/',
      provider: 'CK-12 Foundation',
      search_hint: 'earth science',
      subjects: ['Science', 'Math', 'Technology'],
      grade_levels: ['4', '5', '6', '7', '8'],
    },
    items: [
      {
        item_id: 'middle-school-earth-science',
        title: 'Middle School Earth Science',
        description: 'Earth systems, weather, and space science arranged into middle school modules.',
        subject: 'Science',
        grade_levels: ['6', '7', '8'],
        document: buildSourceDocument({
          source: 'ck-12',
          name: 'Middle School Earth Science',
          description: 'Earth systems content with short readings and hands-on observations.',
          gradeLevels: ['6', '7', '8'],
          subject: 'Science',
          standardsAlignment: ['NGSS-MS-ESS2-1', 'NGSS-MS-ESS1-1'],
          prerequisites: ['Scientific observation notebook'],
          estimatedHours: 96,
          units: [
            {
              name: 'Earth Materials and Processes',
              lessons: [
                { name: 'Rocks and minerals', estimatedHours: 1.25 },
                { name: 'Plate boundaries', estimatedHours: 1.5 },
              ],
            },
            {
              name: 'Weather and Climate',
              lessons: [
                { name: 'Reading weather maps', estimatedHours: 1 },
                { name: 'Climate zones and patterns', estimatedHours: 1.5 },
              ],
            },
          ],
        }),
      },
      {
        item_id: 'life-science-concepts',
        title: 'Life Science Concepts',
        description: 'Adaptable life-science overview with checkpoints and family discussion prompts.',
        subject: 'Science',
        grade_levels: ['5', '6', '7'],
        document: buildSourceDocument({
          source: 'ck-12',
          name: 'Life Science Concepts',
          description: 'Build a flexible homeschool life-science sequence with bite-size lessons.',
          gradeLevels: ['5', '6', '7'],
          subject: 'Science',
          standardsAlignment: ['NGSS-MS-LS1-5', 'NGSS-MS-LS4-4'],
          prerequisites: ['Basic note-taking'],
          estimatedHours: 90,
          units: [
            {
              name: 'Cells and Organisms',
              lessons: [
                { name: 'Cell basics', estimatedHours: 1.25 },
                { name: 'Body systems overview', estimatedHours: 1.5 },
              ],
            },
            {
              name: 'Ecosystems and Adaptations',
              lessons: [
                { name: 'Food webs', estimatedHours: 1.25 },
                { name: 'Traits and adaptation', estimatedHours: 1.25 },
              ],
            },
          ],
        }),
      },
    ],
  },
  coreknowledge: {
    summary: {
      source: 'coreknowledge',
      name: 'Core Knowledge',
      description: 'Knowledge-building units spanning history, literature, and science for elementary grades.',
      website_url: 'https://www.coreknowledge.org/',
      provider: 'Core Knowledge Foundation',
      search_hint: 'history',
      subjects: ['History', 'Language Arts', 'Science'],
      grade_levels: ['1', '2', '3', '4', '5'],
    },
    items: [
      {
        item_id: 'ancient-civilizations',
        title: 'Ancient Civilizations',
        description: 'Elementary history unit set covering Mesopotamia, Egypt, Greece, and Rome.',
        subject: 'History',
        grade_levels: ['3', '4', '5'],
        document: buildSourceDocument({
          source: 'coreknowledge',
          name: 'Ancient Civilizations',
          description: 'Story-rich world history sequence with map work and narration prompts.',
          gradeLevels: ['3', '4', '5'],
          subject: 'History',
          standardsAlignment: ['NCSS.D2.His.1.3-5'],
          prerequisites: ['Map basics'],
          estimatedHours: 72,
          units: [
            {
              name: 'Ancient River Valley Civilizations',
              lessons: [
                { name: 'Mesopotamia and the first cities', estimatedHours: 1.25 },
                { name: 'Ancient Egypt and the Nile', estimatedHours: 1.5 },
              ],
            },
            {
              name: 'Classical Civilizations',
              lessons: [
                { name: 'Greek myths and city-states', estimatedHours: 1.5 },
                { name: 'Rome and civic life', estimatedHours: 1.25 },
              ],
            },
          ],
        }),
      },
    ],
  },
}

function buildSourceResults(source: string, items: MockSourceCatalogItem[]): CurriculumSourceSearchResult[] {
  return items.map((item) => ({
    source,
    item_id: item.item_id,
    title: item.title,
    description: item.description,
    subject: item.subject,
    grade_levels: item.grade_levels,
  }))
}

function mergeExternalSourceMetadata(
  document: CurriculumImportDocument | Record<string, unknown>,
  externalSource: Record<string, unknown>,
) {
  const clone = cloneDocument(document)
  const currentMetadata: Record<string, unknown> =
    'metadata' in clone && clone.metadata && typeof clone.metadata === 'object' && !Array.isArray(clone.metadata)
      ? (clone.metadata as Record<string, unknown>)
      : {}
  const currentExternalSource =
    currentMetadata.external_source && typeof currentMetadata.external_source === 'object' && !Array.isArray(currentMetadata.external_source)
      ? (currentMetadata.external_source as Record<string, unknown>)
      : {}

  return {
    ...clone,
    metadata: {
      ...currentMetadata,
      external_source: {
        ...currentExternalSource,
        ...externalSource,
      },
    },
  }
}

function titleFromLabel(label: string) {
  const base = label.replace(/\.[^.]+$/, '').replace(/[-_]+/g, ' ').replace(/\s+/g, ' ').trim()
  if (!base) return 'Uploaded curriculum draft'
  return base
    .split(' ')
    .map((part) => (part ? part[0].toUpperCase() + part.slice(1) : part))
    .join(' ')
}

async function readAiPayloadLabel(payload: FormData | { url: string }) {
  if (payload instanceof FormData) {
    const fileValue = payload.get('file')
    if (fileValue instanceof File) {
      return { label: fileValue.name, sourceUrl: null as string | null }
    }

    const urlValue = payload.get('url')
    if (typeof urlValue === 'string' && urlValue.trim()) {
      return { label: urlValue.trim(), sourceUrl: urlValue.trim() }
    }
  }

  if (!(payload instanceof FormData) && typeof payload.url === 'string' && payload.url.trim()) {
    return { label: payload.url.trim(), sourceUrl: payload.url.trim() }
  }

  throw new Error('Choose a document or paste a URL to continue.')
}

async function buildAiDraft(payload: FormData | { url: string }): Promise<CurriculumAiImportDraftResponse> {
  const { label, sourceUrl } = await readAiPayloadLabel(payload)
  const title = titleFromLabel(label)
  const document = mergeExternalSourceMetadata(
    buildSourceDocument({
      source: 'ai-import',
      name: `${title} Draft`,
      description: `AI-generated draft based on ${sourceUrl ? 'the provided URL' : 'your uploaded document'}. Review the outline before importing.`,
      gradeLevels: ['6', '7'],
      subject: 'Interdisciplinary Studies',
      standardsAlignment: ['Family-defined standards review'],
      prerequisites: ['Parent review recommended'],
      estimatedHours: 48,
      units: [
        {
          name: 'Scope and Sequence',
          description: 'Suggested sequence distilled from the uploaded material.',
          lessons: [
            { name: 'Big ideas and themes', estimatedHours: 1.25 },
            { name: 'Vocabulary and routines', estimatedHours: 1 },
          ],
        },
        {
          name: 'Projects and Assessments',
          description: 'Project milestones and review checkpoints inferred from the source.',
          lessons: [
            { name: 'Practice and discussion checkpoints', estimatedHours: 1.25 },
            { name: 'Portfolio or mastery assessment', estimatedHours: 1.5 },
          ],
        },
      ],
    }),
    {
      input_label: label,
      source_url: sourceUrl,
      extraction_mode: sourceUrl ? 'url' : 'file',
    },
  )

  return {
    draft: document,
    source_label: sourceUrl ? 'Curriculum web page' : label,
    warnings: [
      'This is a generated draft. Review unit names, grade levels, and estimated hours before importing.',
    ],
    metadata: {
      mock: true,
    },
  }
}

function getConfirmDraft(payload: CurriculumAiImportConfirmPayload) {
  return mergeExternalSourceMetadata(payload.draft, {
    source_url: payload.source_url,
    confirmed_via: 'ai-import',
  })
}

const mockSessions = new Map<string, { session: CurriculumAiImportSession; input: FormData | { url: string } }>()

const apostrophes = /['\u2018\u2019\u02bc`\u00b4]/gu
const gradeNoiseWords = new Set(['grade', 'grades', 'gr', 'level', 'levels', 'year', 'years'])
const gradeAliases = new Map([
  ['kindergarten', 'k'], ['kinder', 'k'], ['pre k', 'prek'], ['pk', 'prek'],
  ['prekindergarten', 'prek'], ['pre kindergarten', 'prek'],
])
const genericLessonNames = new Set([
  'introduction', 'intro', 'overview', 'review', 'unit review', 'chapter review', 'test', 'unit test',
  'chapter test', 'quiz', 'assessment', 'final exam', 'midterm', 'exam', 'practice', 'conclusion',
  'wrap up', 'project', 'final project', 'summary', 'vocabulary', 'warm up',
])
const genericLessonPattern = /^(lesson|day|week|chapter|session|class|part|section|module|unit|topic|activity|worksheet|quiz|test|exam|review)( ?(\p{Nd}+|[ivxlc]+|[a-z]))?$/u

function normalizedName(value: string) {
  return pythonCasefold(value.normalize('NFKC')).normalize('NFKC')
    .replace(apostrophes, '').replace(/\p{P}/gu, ' ').replace(/\s+/gu, ' ')
    .replaceAll('\u0085', ' ').replaceAll('\u001c', ' ').replaceAll('\u001d', ' ')
    .replaceAll('\u001e', ' ').replaceAll('\u001f', ' ').replace(/ +/gu, ' ').trim()
}

function normalizedGrades(values: string[]) {
  return new Set(values.map((value) => {
    const text = normalizedName(value)
    const alias = gradeAliases.get(text)
    if (alias) return alias
    const tokens = text.split(' ').filter((token) => !gradeNoiseWords.has(token)).map((token) => {
      const ordinal = token.match(/^(\p{Nd}+)(st|nd|rd|th)$/u)
      const normalized = ordinal?.[1] || token
      return gradeAliases.get(normalized) || normalized
    })
    const joined = tokens.join(' ')
    return gradeAliases.get(joined) || joined
  }).filter(Boolean))
}

function normalizedTags(values: string[]) {
  return new Set(values.map(normalizedName).filter(Boolean))
}

function isGenericLesson(name: string) {
  return genericLessonNames.has(name) || genericLessonPattern.test(name)
}

function editionFromMetadata(value: unknown): string | null {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return null
  const metadata = value as Record<string, unknown>
  let edition = metadata.edition
  if (!edition && metadata.extensions && typeof metadata.extensions === 'object' && !Array.isArray(metadata.extensions)) {
    edition = (metadata.extensions as Record<string, unknown>).edition
  }
  return (typeof edition === 'string' || typeof edition === 'number') && String(edition).trim()
    ? String(edition).trim()
    : null
}

type MockDuplicateUnit = {
  key: string
  name: string
  lessons: Map<string, string>
}

type MockDuplicateSubject = {
  key: string
  name: string
  grades: Set<string>
  edition: string | null
  units: MockDuplicateUnit[]
}

type MockDuplicateCurriculum = {
  edition: string | null
  grades: Set<string>
  gradeLevels: string[]
  standards: Set<string>
  subjects: MockDuplicateSubject[]
}

function duplicateStructure(document: ReturnType<typeof normalizeCurriculumImport>, raw: unknown, stored = false): MockDuplicateCurriculum {
  const rawDocument = raw && typeof raw === 'object' ? raw as Record<string, unknown> : {}
  const rawMetadata = rawDocument.metadata
  // Candidate extensions are a metadata object themselves; stored metadata uses
  // the outer object. Subject extension editions apply only to stored trees.
  const curriculumEdition = stored
    ? editionFromMetadata(rawMetadata)
    : document.metadata.edition || editionFromMetadata(
      rawMetadata && typeof rawMetadata === 'object' ? (rawMetadata as Record<string, unknown>).extensions : null,
    )
  const curriculumGrades = normalizedGrades(document.metadata.gradeLevels)
  return {
    edition: curriculumEdition,
    grades: curriculumGrades,
    gradeLevels: document.metadata.gradeLevels,
    standards: normalizedTags(document.metadata.standardsAlignment),
    subjects: document.subjects.map((subject, index) => {
      const grades = normalizedGrades(subject.metadata.gradeLevels)
      const rawSubjects = rawDocument.subjects
      const rawSubject = Array.isArray(rawSubjects) ? rawSubjects[index] : null
      return {
        key: normalizedName(subject.name),
        name: subject.name,
        grades: grades.size ? grades : curriculumGrades,
        edition: stored && rawSubject && typeof rawSubject === 'object'
          ? editionFromMetadata((rawSubject as Record<string, unknown>).metadata) || curriculumEdition
          : subject.metadata.edition || curriculumEdition,
        units: subject.units.map((unit) => ({
          key: normalizedName(unit.name),
          name: unit.name,
          lessons: new Map(unit.lessons.map((lesson) => [normalizedName(lesson.name), lesson.name])),
        })),
      }
    }),
  }
}

function setsEqual(left: Set<string>, right: Set<string>) {
  return left.size === right.size && [...left].every((value) => right.has(value))
}

function compatibleSubjects(candidate: MockDuplicateSubject, existing: MockDuplicateSubject) {
  if (candidate.grades.size && existing.grades.size && !setsEqual(candidate.grades, existing.grades)) return false
  const candidateEdition = normalizedName(candidate.edition || '')
  const existingEdition = normalizedName(existing.edition || '')
  return !candidateEdition || !existingEdition || candidateEdition === existingEdition
}

function compatibleCurricula(candidate: MockDuplicateCurriculum, existing: MockDuplicateCurriculum) {
  if (!candidate.standards.size || !existing.standards.size) return true
  return ![...candidate.standards].every((standard) => !existing.standards.has(standard))
}

function structuralTriples(document: MockDuplicateCurriculum) {
  return new Set(document.subjects.flatMap((subject) => subject.units.flatMap((unit) =>
    [...unit.lessons.keys()].map((lesson) => JSON.stringify([subject.key, unit.key, lesson])))))
}

function dedupeEvidence(values: string[]) {
  return [...new Set(values)].slice(0, 50)
}

export function findMockDuplicateMatches(draft: CurriculumImportDocument | Record<string, unknown>, curricula: CurriculumImportDetail[]): CurriculumDuplicateMatch[] {
  const candidate = duplicateStructure(normalizeCurriculumImport(draft), draft)
  return curricula.flatMap((existing) => {
    const rawExisting = existing.payload || existing
    const previous = duplicateStructure(normalizeCurriculumImport(rawExisting), rawExisting, true)
    if (!compatibleCurricula(candidate, previous)) return []

    const candidateByKey = new Map<string, MockDuplicateSubject[]>()
    for (const subject of candidate.subjects) {
      candidateByKey.set(subject.key, [...(candidateByKey.get(subject.key) || []), subject])
    }
    const compatiblePairs = previous.subjects.flatMap((oldSubject) =>
      (candidateByKey.get(oldSubject.key) || [])
        .filter((subject) => compatibleSubjects(subject, oldSubject))
        .map((subject) => [subject, oldSubject] as const))
    if (!compatiblePairs.length) return []

    const candidateTriples = structuralTriples(candidate)
    const previousTriples = structuralTriples(previous)
    const hasSpecificLesson = candidate.subjects.some((subject) =>
      subject.units.some((unit) => [...unit.lessons.keys()].some((lesson) => !isGenericLesson(lesson))))
    const whole = hasSpecificLesson && setsEqual(candidateTriples, previousTriples) &&
      previous.subjects.every((oldSubject) =>
        (candidateByKey.get(oldSubject.key) || []).every((subject) => compatibleSubjects(subject, oldSubject)))

    if (whole) {
      return [{
        id: existing.id,
        name: existing.name,
        grade_levels: [...previous.gradeLevels],
        edition: previous.edition,
        reason: 'exact_curriculum',
        matched_subjects: dedupeEvidence(previous.subjects.map((subject) => subject.name)),
        matched_units: dedupeEvidence(previous.subjects.flatMap((subject) => subject.units.map((unit) => unit.name))),
        matched_lessons: dedupeEvidence(previous.subjects.flatMap((subject) => subject.units.flatMap((unit) => [...unit.lessons.values()]))),
      }]
    }

    const matchedSubjects: string[] = []
    const matchedUnits: string[] = []
    const matchedLessons: string[] = []
    for (const [subject, oldSubject] of compatiblePairs) {
      const candidateUnits = new Map<string, MockDuplicateUnit[]>()
      for (const unit of subject.units) {
        candidateUnits.set(unit.key, [...(candidateUnits.get(unit.key) || []), unit])
      }
      for (const oldUnit of oldSubject.units) {
        const candidateLessons = new Set((candidateUnits.get(oldUnit.key) || []).flatMap((unit) => [...unit.lessons.keys()]))
        const shared = [...oldUnit.lessons.keys()].filter((lesson) => candidateLessons.has(lesson) && !isGenericLesson(lesson))
        if (shared.length < 2) continue
        matchedSubjects.push(oldSubject.name)
        matchedUnits.push(oldUnit.name)
        matchedLessons.push(...shared.map((lesson) => oldUnit.lessons.get(lesson)!))
      }
    }
    if (!matchedUnits.length) return []
    return [{
      id: existing.id,
      name: existing.name,
      grade_levels: [...previous.gradeLevels],
      edition: previous.edition,
      reason: 'partial_overlap',
      matched_subjects: dedupeEvidence(matchedSubjects),
      matched_units: dedupeEvidence(matchedUnits),
      matched_lessons: dedupeEvidence(matchedLessons),
    }]
  })
}

function requireMockSession(id: string) {
  const entry = mockSessions.get(id)
  if (!entry) throw new ApiError(404, 'Import session not found.')
  if (Date.parse(entry.session.expires_at) <= Date.now() && entry.session.status !== 'confirmed') entry.session.status = 'expired'
  return entry
}

export const curriculumImportMockApi = {
  async createSession(input: FormData | { url: string }): Promise<CurriculumAiImportSession> {
    const label = await readAiPayloadLabel(input)
    const session: CurriculumAiImportSession = {
      id: crypto.randomUUID(), status: 'processing', source_kind: input instanceof FormData ? 'file' : 'url',
      source_name: label.label, warnings: ['Development mock: this is a sample draft, not AI analysis.'],
      revision: 1, expires_at: new Date(Date.now() + 30 * 60 * 1000).toISOString(),
      created_at: nowIso(), updated_at: nowIso(), draft: null, error: null,
    }
    mockSessions.set(session.id, { session, input })
    return cloneDocument(session)
  },
  async getSession(id: string): Promise<CurriculumAiImportSession> {
    const entry = requireMockSession(id)
    if (entry.session.status === 'processing') {
      try {
        const result = await buildAiDraft(entry.input)
        if (mockSessions.get(id) !== entry) throw new ApiError(404, 'Import session was cancelled.')
        entry.session = { ...entry.session, status: 'ready', draft: result.draft, revision: 2,
          warnings: [...entry.session.warnings, ...(result.warnings || [])], updated_at: nowIso() }
      } catch (error) {
        if (!mockSessions.has(id)) throw error
        entry.session = { ...entry.session, status: 'failed', error: { code: 'mock_analysis_failed', message: 'Mock analysis failed.' } }
      }
    }
    return cloneDocument(entry.session)
  },
  async deleteSession(id: string) {
    const entry = requireMockSession(id)
    if (entry.session.status === 'confirmed') throw new ApiError(409, 'A confirmed session cannot be cancelled.')
    mockSessions.delete(id)
  },
  async confirmSession(id: string, payload: CurriculumImportConfirmPayload & { client_revision: number }) {
    const entry = requireMockSession(id)
    if (entry.session.status !== 'ready') throw new ApiError(409, 'This session is not ready. Start a new analysis.')
    if (entry.session.revision !== payload.client_revision) throw new ApiError(409, 'The session revision changed. Start a new analysis.')
    const result = await this.confirmImport(payload)
    entry.session.status = 'confirmed'
    return result
  },
  async duplicateCheck(draft: CurriculumImportDocument | Record<string, unknown>) {
    return { matches: findMockDuplicateMatches(draft, readStore().curricula) }
  },
  async confirmImport(payload: CurriculumImportConfirmPayload) {
    const matches = findMockDuplicateMatches(payload.draft, readStore().curricula)
    if (matches.some((match) => !payload.acknowledged_duplicate_ids.includes(match.id))) {
      throw new ApiError(409, 'Review the duplicate curriculum matches.', 'curriculum_import_duplicate_conflict', { matches }, matches)
    }
    return this.persistImport(payload.draft)
  },
  async list() {
    const store = readStore()
    return store.curricula.map(summarize).sort((left, right) => right.updated_at.localeCompare(left.updated_at))
  },

  async get(curriculumId: number) {
    const store = readStore()
    const detail = store.curricula.find((item) => item.id === curriculumId)
    if (!detail) {
      throw new Error('Curriculum not found in mock store.')
    }
    return detail
  },

  async import(payload: CurriculumImportDocument | Record<string, unknown>) {
    return this.confirmImport({ draft: payload, acknowledged_duplicate_ids: [] })
  },

  async persistImport(payload: CurriculumImportDocument | Record<string, unknown>) {
    const store = readStore()
    const name = normalizeCurriculumImport(payload).name
    if (store.curricula.some((item) => normalizedName(item.name) === normalizedName(name))) {
      throw new ApiError(409, 'A curriculum with this name already exists. Rename the draft.', 'curriculum_name_conflict')
    }
    const { detail, nextId } = buildDetail(payload, store.nextId)
    const nextStore = {
      nextId,
      curricula: [detail, ...store.curricula],
    }
    writeStore(nextStore)
    return detail
  },

  async activate(curriculumId: number, payload?: CurriculumImportActivationPayload): Promise<CurriculumImportActivationResponse> {
    const store = readStore()
    const activatedAt = nowIso()
    const curricula = store.curricula.map((item) =>
      item.id === curriculumId
        ? {
            ...item,
            is_activated: true,
            last_activated_at: activatedAt,
            updated_at: activatedAt,
            last_activation_summary: {
              activated_subjects: item.subject_count,
              activated_units: item.unit_count,
              activated_lessons: item.lesson_count,
              generate_assignments: payload?.generate_assignments ?? false,
            },
          }
        : item,
    )
    writeStore({ ...store, curricula })
    const updated = curricula.find((item) => item.id === curriculumId)
    if (!updated) {
      throw new Error('Curriculum not found in mock store.')
    }
    return {
      curriculum_id: curriculumId,
      package_ids: [],
      subject_ids: [],
      unit_ids: [],
      lesson_ids: [],
      resource_ids: [],
      assignment_ids: [],
      generated_assignments: payload?.generate_assignments ?? false,
      activated_at: activatedAt,
    }
  },

  async remove(curriculumId: number) {
    const store = readStore()
    writeStore({ ...store, curricula: store.curricula.filter((item) => item.id !== curriculumId) })
  },

  async schema() {
    return buildSchema()
  },

  async sources() {
    return Object.values(MOCK_SOURCE_CATALOG)
      .map((entry) => cloneDocument(entry.summary))
      .sort((left, right) => left.name.localeCompare(right.name))
  },

  async search(source: string, query: string) {
    const catalog = MOCK_SOURCE_CATALOG[source]
    if (!catalog) {
      throw new Error('This curriculum source is unavailable right now.')
    }

    const term = query.trim().toLowerCase()
    const items = !term
      ? catalog.items
      : catalog.items.filter((item) =>
          [item.title, item.description, item.subject, item.grade_levels.join(' ')]
            .join(' ')
            .toLowerCase()
            .includes(term),
        )

    return buildSourceResults(source, items)
  },

  async importFromSource(source: string, itemId: string) {
    const catalog = MOCK_SOURCE_CATALOG[source]
    const item = catalog?.items.find((candidate) => candidate.item_id === itemId)
    if (!catalog || !item) {
      throw new Error('Unable to import that curriculum item right now.')
    }

    return this.import(
      mergeExternalSourceMetadata(item.document, {
        provider: catalog.summary.name,
        item_id: itemId,
        title: item.title,
        website_url: catalog.summary.website_url,
      }),
    )
  },

  async aiImportDraft(payload: FormData | { url: string }) {
    return buildAiDraft(payload)
  },

  async confirmAiImport(payload: CurriculumAiImportConfirmPayload) {
    return this.import(getConfirmDraft(payload))
  },
}
