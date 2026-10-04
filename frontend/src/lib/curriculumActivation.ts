import type { CurriculumImportActivationPayload, SchoolYear } from '../types/api'

export const MISSING_ACTIVE_SCHOOL_YEAR_MESSAGE = 'Create and activate a school year before activating this curriculum.'

export type ResolvedCurriculumImportActivationPayload = CurriculumImportActivationPayload & { school_year_id: number }

export async function resolveCurriculumActivationPayload(
  payload: CurriculumImportActivationPayload | undefined,
  listSchoolYears: () => Promise<Pick<SchoolYear, 'id' | 'is_active'>[]>,
): Promise<ResolvedCurriculumImportActivationPayload> {
  if (payload?.school_year_id) {
    return { ...payload, school_year_id: payload.school_year_id }
  }
  const activeSchoolYear = (await listSchoolYears()).find((schoolYear) => schoolYear.is_active)
  if (!activeSchoolYear) {
    throw new Error(MISSING_ACTIVE_SCHOOL_YEAR_MESSAGE)
  }
  return { ...payload, school_year_id: activeSchoolYear.id }
}
