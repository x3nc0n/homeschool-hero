import type {
  CurriculumImportActivationPayload,
  CurriculumImportActivationResponse,
  CurriculumImportDetail,
  CurriculumImportDocument,
  CurriculumImportMetadata,
  CurriculumImportSchema,
  CurriculumImportSubject,
  CurriculumImportSummary,
  CurriculumImportUnit,
  CurriculumImportLesson,
} from '@/types/api'
import { buildCurriculumImportExample, normalizeCurriculumImport } from '@/lib/curriculumImport'

const STORAGE_KEY = 'homeschool-hero-curriculum-import-mock-v1'

type MockStore = {
  nextId: number
  curricula: CurriculumImportDetail[]
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
      subjects: { type: 'array', items: { type: 'object' } },
    },
    example: buildCurriculumImportExample(),
  }
}

export const curriculumImportMockApi = {
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
    const store = readStore()
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
}
