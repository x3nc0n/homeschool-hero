import type { CurriculumDuplicateMatch } from '@/types/api'

export class ApiError extends Error {
  status: number
  code?: string
  details?: unknown
  matches: CurriculumDuplicateMatch[]
  constructor(
    status: number,
    message: string,
    code?: string,
    details?: unknown,
    matches: CurriculumDuplicateMatch[] = [],
  ) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.code = code
    this.details = details
    this.matches = matches
  }
}

export function parseApiError(status: number, payload: unknown): ApiError {
  const record = (value: unknown): Record<string, unknown> =>
    value !== null && typeof value === 'object' && !Array.isArray(value) ? value as Record<string, unknown> : {}
  const root = record(payload)
  const nested = record(root.error)
  const detail = record(root.detail)
  const details = nested.details ?? root.details ?? root.detail
  const matches = root.matches ?? nested.matches ?? record(details).matches
  const message = [root.detail, nested.message, detail.message, root.message].find((value) => typeof value === 'string')
  const code = nested.code ?? root.code ?? detail.code
  return new ApiError(status, typeof message === 'string' ? message : `Request failed (${status})`,
    typeof code === 'string' ? code : undefined, details,
    Array.isArray(matches) ? matches as CurriculumDuplicateMatch[] : [])
}
