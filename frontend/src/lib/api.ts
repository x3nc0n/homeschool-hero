import type {
  AcceptInvitationPayload,
  AttendanceExcuse,
  AttendanceHoursSummary,
  AttendanceRecord,
  AttendanceSummary,
  BackupConfig,
  BackupJob,
  BackupStatus,
  BackupType,
  RestoreBackup,
  RestoreExecution,
  RestoreValidation,
  RetentionPolicy,
  DailyAgenda,
  AuditEventFilters,
  AuditEventListResponse,
  ApiErrorPayload,
  Assignment,
  AssignmentFilters,
  AssignmentListResponse,
  AnswerKey,
  AnswerKeyUpsertPayload,
  AssignmentUpsertPayload,
  CalendarEvent,
  ComplianceCustomRulePayload,
  ComplianceDashboard,
  ComplianceReport,
  ComplianceReportStatus,
  ComplianceReportSummary,
  ComplianceReportType,
  ComplianceRule,
  ComplianceRuleListResponse,
  ComplianceStudentStatus,
  Schedule,
  ScheduleBlock,
  ScheduleDetail,
  ScheduleOverride,
  ScheduleOverrideType,
  CurriculumLesson,
  CurriculumImportActivationPayload,
  CurriculumImportActivationResponse,
  CurriculumImportDetail,
  CurriculumImportDocument,
  CurriculumImportSchema,
  CurriculumImportSummary,
  CurriculumPackage,
  CurriculumPackageDetail,
  CurriculumUnit,
  LessonPlan,
  LessonPlanBulkStatusPayload,
  LessonPlanFilters,
  LessonPlanGenerationPayload,
  LessonPlanUpsertPayload,
  AuthSession,
  BootstrapStatus,
  DashboardData,
  ExportEntityType,
  ExportFormat,
  ExportJob,
  ExportType,
  CapabilitiesResponse,
  FamilyFeatureSettings,
  CreateInvitationPayload,
  Grade,
  GradeHistoryResponse,
  GradeCategory,
  GradebookSummary,
  GradebookTrends,
  GradebookView,
  GradeListResponse,
  GradeScale,
  GradeScaleInput,
  GradingJob,
  GradeHistoryFilters,
  HealthResponse,
  GradingPeriod,
  InstructionalDayCount,
  ImportEntityType,
  ImportJob,
  Invitation,
  Notification,
  NotificationListResponse,
  NotificationPreference,
  MetricsResponse,
  MaintenanceSchedulePayload,
  MaintenanceStatus,
  MaintenanceTogglePayload,
  PacingStatusSummary,
  PortfolioCollection,
  PortfolioCollectionPayload,
  PortfolioEntry,
  PortfolioEntryFilters,
  PortfolioEntryPayload,
  PortfolioShareLink,
  PublicPortfolioCollection,
  PacingTarget,
  PacingTargetUpsertPayload,
  Quiz,
  QuizAttempt,
  RegisterPayload,
  ReportCard,
  ReportCardSummary,
  ReportCardStatus,
  RequiredComplianceReportListResponse,
  Resource,
  ResourceType,
  Transcript,
  TranscriptStatus,
  TranscriptSummary,
  ReviewApprovePayload,
  ReviewAssignPayload,
  ReviewBulkResponse,
  ReviewBulkPayload,
  ReviewComment,
  ReviewCommentPayload,
  ReviewQueueItem,
  ReviewRejectPayload,
  ReviewRegradePayload,
  ReviewReviewer,
  SchoolYear,
  SchoolYearDetail,
  Student,
  Subject,
  SubmissionDetail,
  Submission,
  Term,
  WeeklyAgenda,
  SearchFilters,
  SearchResponse,
  UserUiPreferences,
  PaginatedResponse,
} from '@/types/api'
import type { DetailedHealthResponse, ReadinessResponse, SystemStatusResponse } from '@/types/health'
import { curriculumImportMockApi } from '@/lib/curriculumImportMock'
import { getCurrentLanguage } from '@/lib/locale'

export const API_BASE_URL = import.meta.env.VITE_API_URL || '/api'
export const MAINTENANCE_EVENT = 'homeschool:maintenance'
export const AUTH_EXPIRED_EVENT = 'homeschool:auth-expired'

export class ApiError extends Error {
  status: number

  constructor(status: number, message: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

function getCookie(name: string) {
  const value = document.cookie
    .split('; ')
    .find((cookie) => cookie.startsWith(`${name}=`))
    ?.split('=')
    .slice(1)
    .join('=')
  return value ? decodeURIComponent(value) : ''
}

async function parseResponse<T>(response: Response): Promise<T> {
  if (response.status === 204) {
    return undefined as T
  }

  const contentType = response.headers.get('content-type')
  if (contentType?.includes('application/json')) {
    return (await response.json()) as T
  }

  return (await response.text()) as T
}

function shouldHandleAuthExpiry(path: string) {
  return !['/auth/login', '/auth/register', '/auth/bootstrap'].includes(path)
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const headers = new Headers(init?.headers || {})
  const isFormData = init?.body instanceof FormData
  if (!isFormData && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json')
  }
  if (!headers.has('x-csrf-token')) {
    const csrfToken = getCookie('homeschool_csrf')
    if (csrfToken) {
      headers.set('x-csrf-token', csrfToken)
    }
  }
  if (!headers.has('Accept-Language')) {
    headers.set('Accept-Language', getCurrentLanguage())
  }
  const response = await fetch(`${API_BASE_URL}${path}`, {
    credentials: 'include',
    headers,
    ...init,
  })

  if (!response.ok) {
    let message = `Request failed (${response.status})`
    let payload: { detail?: string; message?: string; error?: { code?: string; details?: { maintenance?: unknown } } } | null = null
    try {
      payload = await parseResponse<{ detail?: string; message?: string; error?: { code?: string; details?: { maintenance?: unknown } } }>(response)
      message = payload?.detail || payload?.message || message
    } catch {
      // ignore parse issues
    }
    if (response.status === 401 && shouldHandleAuthExpiry(path)) {
      window.dispatchEvent(new CustomEvent(AUTH_EXPIRED_EVENT, { detail: { path, status: response.status } }))
    }
    if (response.status === 503 && payload?.error?.code === 'maintenance_mode') {
      window.dispatchEvent(
        new CustomEvent(MAINTENANCE_EVENT, {
          detail: (payload.error.details?.maintenance as Record<string, unknown> | undefined) ?? {
            active: true,
            message,
            source: 'server',
          },
        }),
      )
    }
    throw new ApiError(response.status, message)
  }

  return parseResponse<T>(response)
}

function shouldUseCurriculumImportMock(error: unknown) {
  return (
    import.meta.env.DEV &&
    (error instanceof TypeError || (error instanceof ApiError && [404, 405, 501].includes(error.status)))
  )
}

async function withCurriculumImportFallback<T>(operation: () => Promise<T>, fallback: () => Promise<T> | T): Promise<T> {
  try {
    return await operation()
  } catch (error) {
    if (!shouldUseCurriculumImportMock(error)) {
      throw error
    }
    return fallback()
  }
}

export const api = {
  getBootstrapStatus() {
    return request<BootstrapStatus>('/auth/bootstrap')
  },

  getCapabilities() {
    return request<CapabilitiesResponse>('/capabilities')
  },

  getHealth() {
    return request<HealthResponse>('/health')
  },

  getDetailedHealth() {
    return request<DetailedHealthResponse>('/health/detailed')
  },

  getReadiness() {
    return request<ReadinessResponse>('/health/ready')
  },

  getSystemStatus() {
    return request<SystemStatusResponse>('/status')
  },

  getMaintenanceStatus() {
    return request<MaintenanceStatus>('/admin/maintenance')
  },

  toggleMaintenance(payload: MaintenanceTogglePayload) {
    return request<MaintenanceStatus>('/admin/maintenance', {
      method: 'POST',
      body: JSON.stringify(payload),
    })
  },

  scheduleMaintenance(payload: MaintenanceSchedulePayload) {
    return request<MaintenanceStatus>('/admin/maintenance/schedule', {
      method: 'PUT',
      body: JSON.stringify(payload),
    })
  },

  getMetrics() {
    return request<MetricsResponse>('/metrics')
  },

  getDashboard(studentId?: number) {
    const query = studentId ? `?student_id=${studentId}` : ''
    return request<DashboardData>(`/dashboard${query}`)
  },

  getComplianceDashboard(schoolYearId?: number) {
    const query = schoolYearId ? `?school_year_id=${schoolYearId}` : ''
    return request<ComplianceDashboard>(`/compliance/dashboard${query}`)
  },

  getComplianceRules(stateCode?: string) {
    const query = stateCode ? `?state=${encodeURIComponent(stateCode)}` : ''
    return request<ComplianceRuleListResponse>(`/compliance/rules${query}`)
  },

  getComplianceStatus(studentId: number, schoolYearId?: number) {
    const query = schoolYearId ? `?school_year_id=${schoolYearId}` : ''
    return request<ComplianceStudentStatus>(`/compliance/${studentId}/status${query}`)
  },

  listRequiredComplianceReports(filters: { state?: string; student_id?: number; school_year_id?: number } = {}) {
    const params = new URLSearchParams()
    Object.entries(filters).forEach(([key, value]) => {
      if (value === undefined || value === null || value === '') return
      params.set(key, String(value))
    })
    const query = params.toString()
    return request<RequiredComplianceReportListResponse>(`/compliance-reports/required${query ? `?${query}` : ''}`)
  },

  getFamilyComplianceState() {
    return request<{ state_code: string }>('/compliance/family/state')
  },

  updateFamilyComplianceState(stateCode: string) {
    return request<{ state_code: string }>('/compliance/family/state', {
      method: 'PUT',
      body: JSON.stringify({ state_code: stateCode }),
    })
  },

  updateFamilyFeatures(enabledFeatures: Record<string, boolean>) {
    return request<FamilyFeatureSettings>('/family-settings/features', {
      method: 'PUT',
      body: JSON.stringify({ enabled_features: enabledFeatures }),
    })
  },

  createCustomComplianceRule(payload: ComplianceCustomRulePayload) {
    return request<ComplianceRule>('/compliance/rules/custom', {
      method: 'POST',
      body: JSON.stringify(payload),
    })
  },

  getExternalAuthUrl(provider: 'oidc' | 'saml') {
    return `${API_BASE_URL}/auth/${provider}/login`
  },

  register(payload: RegisterPayload) {
    return request<AuthSession>('/auth/register', {
      method: 'POST',
      body: JSON.stringify(payload),
    })
  },

  login(email: string, password: string, familyId?: number) {
    return request<AuthSession>('/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email, password, family_id: familyId }),
    })
  },

  logout() {
    return request<void>('/auth/logout', { method: 'POST' })
  },

  me() {
    return request<AuthSession>('/auth/me')
  },

  acceptInvitation(invitationId: number, payload: AcceptInvitationPayload) {
    return request<AuthSession>(`/invitations/${invitationId}/accept`, {
      method: 'POST',
      body: JSON.stringify(payload),
    })
  },

  listInvitations() {
    return request<Invitation[]>('/invitations')
  },

  listNotifications(filters: { page?: number; page_size?: number; read?: boolean } = {}) {
    const params = new URLSearchParams()
    Object.entries(filters).forEach(([key, value]) => {
      if (value === undefined || value === null) {
        return
      }
      params.set(key, String(value))
    })
    const query = params.toString()
    return request<NotificationListResponse>(`/notifications${query ? `?${query}` : ''}`)
  },

  markNotificationRead(id: number, read = true) {
    return request<Notification>(`/notifications/${id}/read`, {
      method: 'PATCH',
      body: JSON.stringify({ read }),
    })
  },

  markAllNotificationsRead() {
    return request<{ updated: number }>('/notifications/read-all', { method: 'POST' })
  },

  getNotificationPreferences() {
    return request<NotificationPreference[]>('/notifications/preferences')
  },

  updateNotificationPreferences(preferences: NotificationPreference[]) {
    return request<NotificationPreference[]>('/notifications/preferences', {
      method: 'PUT',
      body: JSON.stringify({ preferences }),
    })
  },

  getUserPreferences() {
    return request<UserUiPreferences>('/users/preferences')
  },

  updateUserPreferences(preferences: UserUiPreferences) {
    return request<UserUiPreferences>('/users/preferences', {
      method: 'PUT',
      body: JSON.stringify(preferences),
    })
  },

  listAuditEvents(filters: AuditEventFilters = {}) {
    const params = new URLSearchParams()
    Object.entries(filters).forEach(([key, value]) => {
      if (value === undefined || value === null || value === '' || value === 'all') {
        return
      }
      params.set(key, String(value))
    })
    const query = params.toString()
    return request<AuditEventListResponse>(`/audit${query ? `?${query}` : ''}`)
  },

  listExportJobs() {
    return request<ExportJob[]>('/exports')
  },

  listBackups() {
    return request<BackupJob[]>('/backups')
  },

  getBackup(id: number) {
    return request<BackupJob>(`/backups/${id}`)
  },

  getBackupConfig() {
    return request<BackupConfig>('/backups/config')
  },

  getBackupStatus() {
    return request<BackupStatus>('/backups/status')
  },

  triggerBackup(backupType: BackupType = 'manual') {
    return request<BackupJob>('/backups/trigger', {
      method: 'POST',
      body: JSON.stringify({ backup_type: backupType }),
    })
  },

  listRestoreBackups() {
    return request<RestoreBackup[]>('/restore/backups')
  },

  validateRestoreBackup(backupId: string) {
    return request<RestoreValidation>(`/restore/validate/${encodeURIComponent(backupId)}`, { method: 'POST' })
  },

  executeRestore(
    backupId: string,
    payload: { confirmation_token: string; include_database?: boolean; include_files?: boolean; auto_backup?: boolean },
  ) {
    return request<RestoreExecution>(`/restore/execute/${encodeURIComponent(backupId)}`, {
      method: 'POST',
      body: JSON.stringify(payload),
    })
  },

  executeSelectiveRestore(
    backupId: string,
    payload: { confirmation_token: string; entity_types: ExportEntityType[]; overwrite_existing?: boolean; auto_backup?: boolean },
  ) {
    return request<RestoreExecution>(`/restore/selective/${encodeURIComponent(backupId)}`, {
      method: 'POST',
      body: JSON.stringify(payload),
    })
  },

  getRestoreRetention() {
    return request<RetentionPolicy>('/restore/retention')
  },

  updateRestoreRetention(payload: RetentionPolicy) {
    return request<RetentionPolicy>('/restore/retention', {
      method: 'PUT',
      body: JSON.stringify(payload),
    })
  },

  cleanupRestoreBackups() {
    return request<RetentionPolicy & { deleted: string[]; kept: string[] }>('/restore/cleanup', { method: 'POST' })
  },

  createExportJob(payload: { export_type: ExportType; format: ExportFormat; entity_types?: ExportEntityType[]; date_from?: string }) {
    return request<ExportJob>('/exports', {
      method: 'POST',
      body: JSON.stringify(payload),
    })
  },

  getExportJobStatus(id: number) {
    return request<ExportJob>(`/exports/${id}/status`)
  },

  deleteExportJob(id: number) {
    return request<void>(`/exports/${id}`, { method: 'DELETE' })
  },

  getExportDownloadUrl(id: number) {
    return `${API_BASE_URL}/exports/${id}/download`
  },

  search(filters: SearchFilters = {}) {
    const params = new URLSearchParams()
    Object.entries(filters).forEach(([key, value]) => {
      if (value === undefined || value === null || value === '' || value === 'all') {
        return
      }
      params.set(key, String(value))
    })
    const query = params.toString()
    return request<SearchResponse>(`/search${query ? `?${query}` : ''}`)
  },

  createInvitation(payload: CreateInvitationPayload) {
    return request<Invitation>('/invitations', { method: 'POST', body: JSON.stringify(payload) })
  },

  revokeInvitation(id: number) {
    return request<void>(`/invitations/${id}/revoke`, { method: 'DELETE' })
  },

  listStudents() {
    return request<Student[]>('/students')
  },

  getStudent(id: number) {
    return request<Student>(`/students/${id}`)
  },

  createStudent(payload: Pick<Student, 'name'>) {
    return request<Student>('/students', { method: 'POST', body: JSON.stringify(payload) })
  },

  updateStudent(id: number, payload: Partial<Pick<Student, 'name'>>) {
    return request<Student>(`/students/${id}`, { method: 'PUT', body: JSON.stringify(payload) })
  },

  deleteStudent(id: number) {
    return request<void>(`/students/${id}`, { method: 'DELETE' })
  },

  listSubjects() {
    return request<Subject[]>('/subjects')
  },

  createSubject(payload: Pick<Subject, 'name' | 'color' | 'grading_mode' | 'grade_scale_id'>) {
    return request<Subject>('/subjects', { method: 'POST', body: JSON.stringify(payload) })
  },

  updateSubject(id: number, payload: Partial<Pick<Subject, 'name' | 'color' | 'grading_mode' | 'grade_scale_id'>>) {
    return request<Subject>(`/subjects/${id}`, { method: 'PUT', body: JSON.stringify(payload) })
  },

  deleteSubject(id: number) {
    return request<void>(`/subjects/${id}`, { method: 'DELETE' })
  },

  listImportJobs() {
    return request<ImportJob[]>('/imports')
  },

  uploadImportFile(entityType: ImportEntityType, file: File) {
    const formData = new FormData()
    formData.set('file', file)
    return request<ImportJob>(`/imports/upload?entity_type=${encodeURIComponent(entityType)}`, {
      method: 'POST',
      body: formData,
    })
  },

  getImportJobStatus(jobId: number) {
    return request<ImportJob>(`/imports/${jobId}/status`)
  },

  validateImportJob(jobId: number) {
    return request<ImportJob>(`/imports/${jobId}/validate`, { method: 'POST' })
  },

  executeImportJob(jobId: number) {
    return request<ImportJob>(`/imports/${jobId}/execute`, { method: 'POST' })
  },

  listAttendance(filters: { student_id?: number; date?: string; date_from?: string; date_to?: string } = {}) {
    const params = new URLSearchParams()
    Object.entries(filters).forEach(([key, value]) => {
      if (value === undefined || value === null || value === '') return
      params.set(key, String(value))
    })
    const query = params.toString()
    return request<AttendanceRecord[]>(`/attendance${query ? `?${query}` : ''}`)
  },

  recordDailyAttendance(payload: {
    date: string
    records: Array<{
      student_id: number
      status: string
      instructional_hours?: string | number
      check_in_time?: string
      check_out_time?: string
      notes?: string | null
    }>
  }) {
    return request<AttendanceRecord[]>('/attendance/daily', { method: 'POST', body: JSON.stringify(payload) })
  },

  logInstructionalHours(payload: {
    student_id: number
    date: string
    instructional_hours: string | number
    check_in_time?: string | null
    check_out_time?: string | null
    notes?: string | null
  }) {
    return request<AttendanceRecord>('/attendance/hours', { method: 'POST', body: JSON.stringify(payload) })
  },

  getAttendanceSummary(studentId: number, period: 'day' | 'week' | 'term' | 'year', schoolYearId?: number) {
    const params = new URLSearchParams({ student_id: String(studentId), period })
    if (schoolYearId) params.set('school_year_id', String(schoolYearId))
    return request<AttendanceSummary>(`/attendance/summary?${params.toString()}`)
  },

  getAttendanceHours(studentId: number, schoolYearId: number) {
    return request<AttendanceHoursSummary>(`/attendance/hours?student_id=${studentId}&school_year_id=${schoolYearId}`)
  },

  createAttendanceExcuse(formData: FormData) {
    return request<AttendanceExcuse>('/attendance/excuses', { method: 'POST', body: formData })
  },

  approveAttendanceExcuse(excuseId: number) {
    return request<AttendanceExcuse>(`/attendance/excuses/${excuseId}/approve`, { method: 'POST' })
  },

  listSchoolYears() {
    return request<SchoolYear[]>('/calendar/school-years')
  },

  getSchoolYear(id: number) {
    return request<SchoolYearDetail>(`/calendar/school-years/${id}`)
  },

  createSchoolYear(payload: Pick<SchoolYear, 'name' | 'start_date' | 'end_date' | 'is_active'>) {
    return request<SchoolYear>('/calendar/school-years', { method: 'POST', body: JSON.stringify(payload) })
  },

  updateSchoolYear(id: number, payload: Pick<SchoolYear, 'name' | 'start_date' | 'end_date' | 'is_active'>) {
    return request<SchoolYear>(`/calendar/school-years/${id}`, { method: 'PUT', body: JSON.stringify(payload) })
  },

  deleteSchoolYear(id: number) {
    return request<void>(`/calendar/school-years/${id}`, { method: 'DELETE' })
  },

  getActiveSchoolYear() {
    return request<SchoolYearDetail>('/calendar/active')
  },

  getInstructionalDays(schoolYearId: number) {
    return request<InstructionalDayCount>(`/calendar/${schoolYearId}/days`)
  },

  createTerm(payload: Pick<Term, 'school_year_id' | 'name' | 'start_date' | 'end_date' | 'term_type'>) {
    return request<Term>('/calendar/terms', { method: 'POST', body: JSON.stringify(payload) })
  },

  updateTerm(id: number, payload: Pick<Term, 'name' | 'start_date' | 'end_date' | 'term_type'>) {
    return request<Term>(`/calendar/terms/${id}`, { method: 'PUT', body: JSON.stringify(payload) })
  },

  deleteTerm(id: number) {
    return request<void>(`/calendar/terms/${id}`, { method: 'DELETE' })
  },

  createGradingPeriod(payload: Pick<GradingPeriod, 'term_id' | 'name' | 'start_date' | 'end_date'>) {
    return request<GradingPeriod>('/calendar/grading-periods', { method: 'POST', body: JSON.stringify(payload) })
  },

  updateGradingPeriod(id: number, payload: Pick<GradingPeriod, 'name' | 'start_date' | 'end_date'>) {
    return request<GradingPeriod>(`/calendar/grading-periods/${id}`, { method: 'PUT', body: JSON.stringify(payload) })
  },

  deleteGradingPeriod(id: number) {
    return request<void>(`/calendar/grading-periods/${id}`, { method: 'DELETE' })
  },

  createCalendarEvent(
    payload: Pick<CalendarEvent, 'school_year_id' | 'date' | 'event_type' | 'name' | 'is_instructional_day' | 'notes'>,
  ) {
    return request<CalendarEvent>('/calendar/events', { method: 'POST', body: JSON.stringify(payload) })
  },

  updateCalendarEvent(
    id: number,
    payload: Pick<CalendarEvent, 'date' | 'event_type' | 'name' | 'is_instructional_day' | 'notes'>,
  ) {
    return request<CalendarEvent>(`/calendar/events/${id}`, { method: 'PUT', body: JSON.stringify(payload) })
  },

  deleteCalendarEvent(id: number) {
    return request<void>(`/calendar/events/${id}`, { method: 'DELETE' })
  },

  listSchedules(studentId?: number) {
    const params = new URLSearchParams()
    if (studentId) {
      params.set('student_id', String(studentId))
    }
    const query = params.toString()
    return request<Schedule[]>(`/schedule${query ? `?${query}` : ''}`)
  },

  getSchedule(id: number) {
    return request<ScheduleDetail>(`/schedule/${id}`)
  },

  createSchedule(payload: Pick<Schedule, 'student_id' | 'school_year_id' | 'name'>) {
    return request<Schedule>('/schedule', { method: 'POST', body: JSON.stringify(payload) })
  },

  updateSchedule(id: number, payload: Pick<Schedule, 'student_id' | 'school_year_id' | 'name'>) {
    return request<Schedule>(`/schedule/${id}`, { method: 'PUT', body: JSON.stringify(payload) })
  },

  deleteSchedule(id: number) {
    return request<void>(`/schedule/${id}`, { method: 'DELETE' })
  },

  createScheduleBlock(
    scheduleId: number,
    payload: Pick<ScheduleBlock, 'subject_id' | 'day_of_week' | 'start_time' | 'end_time' | 'location' | 'notes'>,
  ) {
    return request<ScheduleBlock>(`/schedule/${scheduleId}/blocks`, { method: 'POST', body: JSON.stringify(payload) })
  },

  updateScheduleBlock(
    blockId: number,
    payload: Pick<ScheduleBlock, 'subject_id' | 'day_of_week' | 'start_time' | 'end_time' | 'location' | 'notes'>,
  ) {
    return request<ScheduleBlock>(`/schedule/blocks/${blockId}`, { method: 'PUT', body: JSON.stringify(payload) })
  },

  deleteScheduleBlock(blockId: number) {
    return request<void>(`/schedule/blocks/${blockId}`, { method: 'DELETE' })
  },

  createScheduleOverride(payload: {
    schedule_id: number
    date: string
    original_block_id?: number
    override_type: ScheduleOverrideType
    subject_id?: number
    start_time?: string
    end_time?: string
    reason: string
  }) {
    return request<ScheduleOverride>('/schedule/override', { method: 'POST', body: JSON.stringify(payload) })
  },

  deleteScheduleOverride(overrideId: number) {
    return request<void>(`/schedule/override/${overrideId}`, { method: 'DELETE' })
  },

  getDailyAgenda(studentId: number, date: string) {
    return request<DailyAgenda>(`/schedule/${studentId}/agenda?date=${encodeURIComponent(date)}`)
  },

  getWeeklyAgenda(studentId: number, date: string) {
    return request<WeeklyAgenda>(`/schedule/${studentId}/week?date=${encodeURIComponent(date)}`)
  },

  listImportedCurricula() {
    return withCurriculumImportFallback(
      () => request<CurriculumImportSummary[]>('/curriculum/'),
      () => curriculumImportMockApi.list(),
    )
  },

  getImportedCurriculum(id: number) {
    return withCurriculumImportFallback(
      () => request<CurriculumImportDetail>(`/curriculum/${id}`),
      () => curriculumImportMockApi.get(id),
    )
  },

  importCurriculum(payload: CurriculumImportDocument | Record<string, unknown>) {
    return withCurriculumImportFallback(
      () => request<CurriculumImportDetail>('/curriculum/import', { method: 'POST', body: JSON.stringify(payload) }),
      () => curriculumImportMockApi.import(payload),
    )
  },

  activateImportedCurriculum(id: number, payload?: CurriculumImportActivationPayload) {
    return withCurriculumImportFallback(
      () =>
        request<CurriculumImportActivationResponse>(`/curriculum/${id}/activate`, {
          method: 'POST',
          body: payload ? JSON.stringify(payload) : undefined,
        }),
      () => curriculumImportMockApi.activate(id, payload),
    )
  },

  deleteImportedCurriculum(id: number) {
    return withCurriculumImportFallback(
      () => request<void>(`/curriculum/${id}`, { method: 'DELETE' }),
      () => curriculumImportMockApi.remove(id),
    )
  },

  getCurriculumImportSchema() {
    return withCurriculumImportFallback(
      () => request<CurriculumImportSchema>('/curriculum/schema'),
      () => curriculumImportMockApi.schema(),
    )
  },

  listCurriculumPackages(schoolYearId?: number) {
    const query = schoolYearId ? `?school_year_id=${schoolYearId}` : ''
    return request<CurriculumPackageDetail[]>(`/curriculum/packages${query}`)
  },

  createCurriculumPackage(payload: Pick<CurriculumPackage, 'school_year_id' | 'name' | 'description' | 'subject_id'>) {
    return request<CurriculumPackage>('/curriculum/packages', { method: 'POST', body: JSON.stringify(payload) })
  },

  updateCurriculumPackage(
    id: number,
    payload: Pick<CurriculumPackage, 'school_year_id' | 'name' | 'description' | 'subject_id'>,
  ) {
    return request<CurriculumPackage>(`/curriculum/packages/${id}`, { method: 'PUT', body: JSON.stringify(payload) })
  },

  deleteCurriculumPackage(id: number) {
    return request<void>(`/curriculum/packages/${id}`, { method: 'DELETE' })
  },

  cloneCurriculumPackage(id: number, payload: { target_school_year_id: number; name?: string }) {
    return request<CurriculumPackageDetail>(`/curriculum/packages/${id}/clone`, {
      method: 'POST',
      body: JSON.stringify(payload),
    })
  },

  createCurriculumUnit(
    payload: Pick<CurriculumUnit, 'package_id' | 'name' | 'description' | 'sequence_order' | 'standards_tags'>,
  ) {
    return request<CurriculumUnit>('/curriculum/units', { method: 'POST', body: JSON.stringify(payload) })
  },

  updateCurriculumUnit(id: number, payload: Pick<CurriculumUnit, 'name' | 'description' | 'sequence_order' | 'standards_tags'>) {
    return request<CurriculumUnit>(`/curriculum/units/${id}`, { method: 'PUT', body: JSON.stringify(payload) })
  },

  deleteCurriculumUnit(id: number) {
    return request<void>(`/curriculum/units/${id}`, { method: 'DELETE' })
  },

  createCurriculumLesson(
    payload: Pick<
      CurriculumLesson,
      'unit_id' | 'name' | 'description' | 'sequence_order' | 'estimated_duration_minutes' | 'standards_tags'
    >,
  ) {
    return request<CurriculumLesson>('/curriculum/lessons', { method: 'POST', body: JSON.stringify(payload) })
  },

  updateCurriculumLesson(
    id: number,
    payload: Pick<CurriculumLesson, 'name' | 'description' | 'sequence_order' | 'estimated_duration_minutes' | 'standards_tags'>,
  ) {
    return request<CurriculumLesson>(`/curriculum/lessons/${id}`, { method: 'PUT', body: JSON.stringify(payload) })
  },

  deleteCurriculumLesson(id: number) {
    return request<void>(`/curriculum/lessons/${id}`, { method: 'DELETE' })
  },

  listLessonPlans(filters: LessonPlanFilters = {}) {
    const params = new URLSearchParams()
    Object.entries(filters).forEach(([key, value]) => {
      if (value === undefined || value === null || value === '' || value === 'all') {
        return
      }
      params.set(key, String(value))
    })
    const query = params.toString()
    return request<LessonPlan[]>(`/lesson-plans${query ? `?${query}` : ''}`)
  },

  createLessonPlan(payload: LessonPlanUpsertPayload) {
    return request<LessonPlan>('/lesson-plans', { method: 'POST', body: JSON.stringify(payload) })
  },

  updateLessonPlan(id: number, payload: LessonPlanUpsertPayload) {
    return request<LessonPlan>(`/lesson-plans/${id}`, { method: 'PUT', body: JSON.stringify(payload) })
  },

  deleteLessonPlan(id: number) {
    return request<void>(`/lesson-plans/${id}`, { method: 'DELETE' })
  },

  generateLessonPlans(payload: LessonPlanGenerationPayload) {
    return request<LessonPlan[]>('/lesson-plans/generate', { method: 'POST', body: JSON.stringify(payload) })
  },

  bulkUpdateLessonPlans(payload: LessonPlanBulkStatusPayload) {
    return request<LessonPlan[]>('/lesson-plans/bulk-status', { method: 'POST', body: JSON.stringify(payload) })
  },

  generateAssignmentsFromLessonPlans(payload: { lesson_plan_ids: number[]; include_existing?: boolean }) {
    return request<Assignment[]>('/lesson-plans/generate-assignments', { method: 'POST', body: JSON.stringify(payload) })
  },

  listPacingTargets(filters: { student_id?: number; subject_id?: number } = {}) {
    const params = new URLSearchParams()
    if (filters.student_id) params.set('student_id', String(filters.student_id))
    if (filters.subject_id) params.set('subject_id', String(filters.subject_id))
    const query = params.toString()
    return request<PacingTarget[]>(`/pacing-targets${query ? `?${query}` : ''}`)
  },

  createPacingTarget(payload: PacingTargetUpsertPayload) {
    return request<PacingTarget>('/pacing-targets', { method: 'POST', body: JSON.stringify(payload) })
  },

  updatePacingTarget(id: number, payload: PacingTargetUpsertPayload) {
    return request<PacingTarget>(`/pacing-targets/${id}`, { method: 'PUT', body: JSON.stringify(payload) })
  },

  deletePacingTarget(id: number) {
    return request<void>(`/pacing-targets/${id}`, { method: 'DELETE' })
  },

  getPacingStatus(studentId: number, subjectId?: number) {
    const query = subjectId ? `?subject_id=${subjectId}` : ''
    return request<PacingStatusSummary>(`/pacing/${studentId}${query}`)
  },

  listResources(filters: { search?: string; resource_type?: ResourceType | 'all'; tag?: string } = {}) {
    const params = new URLSearchParams()
    if (filters.search?.trim()) params.set('search', filters.search.trim())
    if (filters.tag?.trim()) params.set('tag', filters.tag.trim())
    if (filters.resource_type && filters.resource_type !== 'all') params.set('resource_type', filters.resource_type)
    const query = params.toString()
    return request<Resource[]>(`/resources${query ? `?${query}` : ''}`)
  },

  createResource(formData: FormData) {
    return request<Resource>('/resources', { method: 'POST', body: formData })
  },

  updateResource(
    id: number,
    payload: Pick<Resource, 'name' | 'description' | 'resource_type' | 'url' | 'tags' | 'metadata'>,
  ) {
    return request<Resource>(`/resources/${id}`, { method: 'PUT', body: JSON.stringify(payload) })
  },

  deleteResource(id: number) {
    return request<void>(`/resources/${id}`, { method: 'DELETE' })
  },

  linkResourceToLesson(lessonId: number, resourceId: number) {
    return request<void>(`/curriculum/lessons/${lessonId}/resources/${resourceId}`, { method: 'POST' })
  },

  unlinkResourceFromLesson(lessonId: number, resourceId: number) {
    return request<void>(`/curriculum/lessons/${lessonId}/resources/${resourceId}`, { method: 'DELETE' })
  },

  listAssignments(filters: AssignmentFilters = {}) {
    const params = new URLSearchParams()
    Object.entries(filters).forEach(([key, value]) => {
      if (value === undefined || value === null || value === '' || value === 'all') {
        return
      }
      params.set(key, String(value))
    })
    const query = params.toString()
    return request<AssignmentListResponse>(`/assignments${query ? `?${query}` : ''}`)
  },

  createAssignment(payload: AssignmentUpsertPayload) {
    return request<Assignment>('/assignments', { method: 'POST', body: JSON.stringify(payload) })
  },

  updateAssignment(id: number, payload: AssignmentUpsertPayload) {
    return request<Assignment>(`/assignments/${id}`, { method: 'PUT', body: JSON.stringify(payload) })
  },

  getAnswerKey(assignmentId: number) {
    return request<AnswerKey | null>(`/assignments/${assignmentId}/answer-key`)
  },

  upsertAnswerKey(assignmentId: number, payload: AnswerKeyUpsertPayload) {
    return request<AnswerKey>(`/assignments/${assignmentId}/answer-key`, {
      method: 'PUT',
      body: JSON.stringify(payload),
    })
  },

  deleteAssignment(id: number) {
    return request<void>(`/assignments/${id}`, { method: 'DELETE' })
  },

  listGrades(params: { page?: number; page_size?: number; student_id?: number; subject_id?: number } = {}) {
    const resolved = { page: 1, page_size: 100, ...params }
    const search = new URLSearchParams()
    Object.entries(resolved).forEach(([key, value]) => {
      if (value === undefined || value === null) return
      search.set(key, String(value))
    })
    const query = search.toString()
    return request<GradeListResponse>(`/grades${query ? `?${query}` : ''}`).then((payload) => payload.items)
  },

  listGradeHistory(filters: GradeHistoryFilters = {}) {
    const params = new URLSearchParams()
    Object.entries(filters).forEach(([key, value]) => {
      if (value === undefined || value === null || value === '') {
        return
      }
      params.set(key, String(value))
    })
    const query = params.toString()
    return request<GradeHistoryResponse>(`/grades/history${query ? `?${query}` : ''}`)
  },

  createGrade(payload: Partial<Grade>) {
    return request<Grade>('/grades', { method: 'POST', body: JSON.stringify(payload) })
  },

  updateGrade(id: number, payload: Partial<Grade>) {
    return request<Grade>(`/grades/${id}`, { method: 'PUT', body: JSON.stringify(payload) })
  },

  deleteGrade(id: number) {
    return request<void>(`/grades/${id}`, { method: 'DELETE' })
  },

  getGradebook(studentId: number, filters: { subject_id?: number; grading_period_id?: number } = {}) {
    const params = new URLSearchParams()
    Object.entries(filters).forEach(([key, value]) => {
      if (value === undefined || value === null) return
      params.set(key, String(value))
    })
    const query = params.toString()
    return request<GradebookView>(`/gradebook/${studentId}${query ? `?${query}` : ''}`)
  },

  getGradebookSummary(studentId: number) {
    return request<GradebookSummary>(`/gradebook/${studentId}/summary`)
  },

  getGradeTrends(studentId: number, filters: { subject_id?: number; grading_period_id?: number } = {}) {
    const params = new URLSearchParams()
    Object.entries(filters).forEach(([key, value]) => {
      if (value === undefined || value === null) return
      params.set(key, String(value))
    })
    const query = params.toString()
    return request<GradebookTrends>(`/gradebook/${studentId}/trends${query ? `?${query}` : ''}`)
  },

  getGradeCategories(subjectId: number) {
    return request<GradeCategory[]>(`/gradebook/categories?subject_id=${subjectId}`)
  },

  upsertGradeCategories(subjectId: number, categories: GradeCategory[]) {
    return request<GradeCategory[]>('/gradebook/categories', {
      method: 'PUT',
      body: JSON.stringify({ subject_id: subjectId, categories }),
    })
  },

  listGradeScales() {
    return request<GradeScale[]>('/gradebook/scales')
  },

  upsertGradeScales(scales: GradeScaleInput[]) {
    return request<GradeScale[]>('/gradebook/scales', {
      method: 'PUT',
      body: JSON.stringify({ scales }),
    })
  },

  recalculateGradebook(payload: { student_id: number; subject_id?: number; grading_period_id?: number }) {
    return request<GradebookView>('/gradebook/calculate', {
      method: 'POST',
      body: JSON.stringify(payload),
    })
  },

  listReportCards(filters: { student_id?: number; grading_period_id?: number; status?: ReportCardStatus } = {}) {
    const params = new URLSearchParams()
    Object.entries(filters).forEach(([key, value]) => {
      if (value === undefined || value === null) return
      params.set(key, String(value))
    })
    const query = params.toString()
    return request<ReportCardSummary[]>(`/report-cards${query ? `?${query}` : ''}`)
  },

  generateReportCard(payload: { student_id: number; grading_period_id: number; notes?: string | null }) {
    return request<ReportCard>('/report-cards/generate', {
      method: 'POST',
      body: JSON.stringify(payload),
    })
  },

  getReportCard(id: number) {
    return request<ReportCard>(`/report-cards/${id}`)
  },

  updateReportCard(
    id: number,
    payload: { notes?: string | null; status?: ReportCardStatus; entries?: Array<{ entry_id: number; teacher_comments?: string | null }> },
  ) {
    return request<ReportCard>(`/report-cards/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(payload),
    })
  },

  finalizeReportCard(id: number) {
    return request<ReportCard>(`/report-cards/${id}/finalize`, { method: 'POST' })
  },

  getReportCardPdfUrl(id: number) {
    return `${API_BASE_URL}/report-cards/${id}/pdf`
  },

  listComplianceReports(filters: {
    student_id?: number
    school_year_id?: number
    report_type?: ComplianceReportType
    status?: ComplianceReportStatus
  } = {}) {
    const params = new URLSearchParams()
    Object.entries(filters).forEach(([key, value]) => {
      if (value === undefined || value === null) return
      params.set(key, String(value))
    })
    const query = params.toString()
    return request<ComplianceReportSummary[]>(`/compliance-reports${query ? `?${query}` : ''}`)
  },

  generateComplianceReport(payload: {
    student_id: number
    school_year_id: number
    report_type: ComplianceReportType
    grading_period_id?: number | null
    notes?: string | null
  }) {
    return request<ComplianceReport>('/compliance-reports/generate', {
      method: 'POST',
      body: JSON.stringify(payload),
    })
  },

  getComplianceReport(id: number) {
    return request<ComplianceReport>(`/compliance-reports/${id}`)
  },

  finalizeComplianceReport(id: number) {
    return request<ComplianceReport>(`/compliance-reports/${id}/finalize`, { method: 'POST' })
  },

  getComplianceReportPdfUrl(id: number) {
    return `${API_BASE_URL}/compliance-reports/${id}/pdf`
  },

  listTranscripts(filters: { student_id?: number; status?: TranscriptStatus } = {}) {
    const params = new URLSearchParams()
    Object.entries(filters).forEach(([key, value]) => {
      if (value === undefined || value === null) return
      params.set(key, String(value))
    })
    const query = params.toString()
    return request<TranscriptSummary[]>(`/transcripts${query ? `?${query}` : ''}`)
  },

  generateTranscript(payload: { student_id: number; notes?: string | null }) {
    return request<Transcript>('/transcripts/generate', {
      method: 'POST',
      body: JSON.stringify(payload),
    })
  },

  getTranscript(id: number) {
    return request<Transcript>(`/transcripts/${id}`)
  },

  updateTranscript(
    id: number,
    payload: {
      notes?: string | null
      status?: TranscriptStatus
      entries?: Array<{
        entry_id: number
        credits?: number | null
        is_honors?: boolean | null
        is_ap?: boolean | null
        notes?: string | null
        subject_name?: string | null
      }>
    },
  ) {
    return request<Transcript>(`/transcripts/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(payload),
    })
  },

  finalizeTranscript(id: number) {
    return request<Transcript>(`/transcripts/${id}/finalize`, { method: 'POST' })
  },

  getTranscriptPdfUrl(id: number) {
    return `${API_BASE_URL}/transcripts/${id}/pdf`
  },

  listQuizzes() {
    return request<Quiz[]>('/quizzes')
  },

  createQuiz(payload: Partial<Quiz>) {
    return request<Quiz>('/quizzes', { method: 'POST', body: JSON.stringify(payload) })
  },

  updateQuiz(id: number, payload: Partial<Quiz>) {
    return request<Quiz>(`/quizzes/${id}`, { method: 'PUT', body: JSON.stringify(payload) })
  },

  deleteQuiz(id: number) {
    return request<void>(`/quizzes/${id}`, { method: 'DELETE' })
  },

  async submitQuizAttempt(quizId: number, payload: { student_id: number; answers: string[] }) {
    try {
      return await request<QuizAttempt>(`/quizzes/${quizId}/attempts`, {
        method: 'POST',
        body: JSON.stringify(payload),
      })
    } catch (error) {
      if (error instanceof ApiError && error.status === 404) {
        return request<QuizAttempt>(`/quizzes/${quizId}/take`, {
          method: 'POST',
          body: JSON.stringify(payload),
        })
      }
      throw error
    }
  },

  listReviewQueue(filters?: { status?: string; priority?: string; student_id?: number; subject_id?: number }) {
    const params = new URLSearchParams()
    if (filters?.status) params.set('status', filters.status)
    if (filters?.priority) params.set('priority', filters.priority)
    if (filters?.student_id) params.set('student_id', String(filters.student_id))
    if (filters?.subject_id) params.set('subject_id', String(filters.subject_id))
    const suffix = params.toString() ? `?${params.toString()}` : ''
    return request<ReviewQueueItem[]>(`/reviews${suffix}`)
  },

  getReview(id: number) {
    return request<ReviewQueueItem>(`/reviews/${id}`)
  },

  listReviewers() {
    return request<ReviewReviewer[]>('/reviews/reviewers')
  },

  listGradingJobs(status?: string) {
    const params = new URLSearchParams()
    if (status) params.set('status', status)
    const suffix = params.toString() ? `?${params.toString()}` : ''
    return request<GradingJob[]>(`/grading/jobs${suffix}`)
  },

  approveReview(reviewId: number, payload: ReviewApprovePayload) {
    return request<ReviewQueueItem>(`/reviews/${reviewId}/approve`, {
      method: 'POST',
      body: JSON.stringify(payload),
    })
  },

  rejectReview(reviewId: number, payload: ReviewRejectPayload) {
    return request<ReviewQueueItem>(`/reviews/${reviewId}/reject`, {
      method: 'POST',
      body: JSON.stringify(payload),
    })
  },

  regradeReview(reviewId: number, payload: ReviewRegradePayload) {
    return request<ReviewQueueItem>(`/reviews/${reviewId}/regrade`, {
      method: 'POST',
      body: JSON.stringify(payload),
    })
  },

  assignReview(reviewId: number, payload: ReviewAssignPayload) {
    return request<ReviewQueueItem>(`/reviews/${reviewId}/assign`, {
      method: 'POST',
      body: JSON.stringify(payload),
    })
  },

  bulkApproveReviews(payload: ReviewBulkPayload & { notes?: string; override_reason?: string }) {
    return request<ReviewBulkResponse>('/reviews/bulk/approve', {
      method: 'POST',
      body: JSON.stringify(payload),
    })
  },

  bulkAssignReviews(payload: ReviewBulkPayload & ReviewAssignPayload) {
    return request<ReviewBulkResponse>('/reviews/bulk/assign', {
      method: 'POST',
      body: JSON.stringify(payload),
    })
  },

  addReviewComment(reviewId: number, payload: ReviewCommentPayload) {
    return request<ReviewComment>(`/reviews/${reviewId}/comments`, {
      method: 'POST',
      body: JSON.stringify(payload),
    })
  },

  uploadSubmission(
    payload: { assignment_id: number; student_id: number; file: File; resubmission_of_submission_id?: number },
    onProgress?: (progress: number) => void,
  ) {
    return new Promise<SubmissionDetail>((resolve, reject) => {
      const formData = new FormData()
      formData.append('assignment_id', String(payload.assignment_id))
      formData.append('student_id', String(payload.student_id))
      if (payload.resubmission_of_submission_id) {
        formData.append('resubmission_of_submission_id', String(payload.resubmission_of_submission_id))
      }
      formData.append('file', payload.file)

      const xhr = new XMLHttpRequest()
      xhr.open('POST', `${API_BASE_URL}/submissions`)
      xhr.withCredentials = true
      const csrfToken = getCookie('homeschool_csrf')
      if (csrfToken) {
        xhr.setRequestHeader('x-csrf-token', csrfToken)
      }

      xhr.upload.addEventListener('progress', (event) => {
        if (event.lengthComputable) {
          onProgress?.(Math.round((event.loaded / event.total) * 100))
        }
      })

      xhr.onload = () => {
        if (xhr.status >= 200 && xhr.status < 300) {
          resolve(JSON.parse(xhr.responseText) as SubmissionDetail)
          return
        }

        try {
          const parsed = JSON.parse(xhr.responseText) as ApiErrorPayload
          reject(new ApiError(xhr.status, parsed.detail || parsed.message || 'Upload failed'))
        } catch {
          reject(new ApiError(xhr.status, 'Upload failed'))
        }
      }

      xhr.onerror = () => reject(new ApiError(500, 'Network error during upload'))
      xhr.send(formData)
    })
  },

  listSubmissions(params: { page?: number; page_size?: number } = {}) {
    const resolved = { page: 1, page_size: 100, ...params }
    const search = new URLSearchParams()
    Object.entries(resolved).forEach(([key, value]) => {
      if (value === undefined || value === null) return
      search.set(key, String(value))
    })
    const query = search.toString()
    return request<PaginatedResponse<Submission>>(`/submissions${query ? `?${query}` : ''}`).then((payload) => payload.items)
  },

  getSubmission(id: number) {
    return request<SubmissionDetail>(`/submissions/${id}`)
  },

  listPortfolioEntries(studentId: number, filters: PortfolioEntryFilters = {}) {
    const params = new URLSearchParams()
    Object.entries(filters).forEach(([key, value]) => {
      if (value === undefined || value === null || value === '' || value === 'all') {
        return
      }
      params.set(key, String(value))
    })
    const query = params.toString()
    return request<PortfolioEntry[]>(`/portfolio/${studentId}/entries${query ? `?${query}` : ''}`)
  },

  createPortfolioEntry(payload: PortfolioEntryPayload) {
    return request<PortfolioEntry>('/portfolio/entries', { method: 'POST', body: JSON.stringify(payload) })
  },

  getPortfolioEntry(id: number) {
    return request<PortfolioEntry>(`/portfolio/entries/${id}`)
  },

  updatePortfolioEntry(id: number, payload: PortfolioEntryPayload) {
    return request<PortfolioEntry>(`/portfolio/entries/${id}`, { method: 'PUT', body: JSON.stringify(payload) })
  },

  deletePortfolioEntry(id: number) {
    return request<void>(`/portfolio/entries/${id}`, { method: 'DELETE' })
  },

  attachPortfolioEntryFiles(id: number, files: File[]) {
    const formData = new FormData()
    files.forEach((file) => formData.append('files', file))
    return request<PortfolioEntry>(`/portfolio/entries/${id}/attach`, { method: 'POST', body: formData })
  },

  listPortfolioCollections(studentId?: number) {
    const query = studentId ? `?student_id=${studentId}` : ''
    return request<PortfolioCollection[]>(`/portfolio/collections${query}`)
  },

  createPortfolioCollection(payload: PortfolioCollectionPayload) {
    return request<PortfolioCollection>('/portfolio/collections', { method: 'POST', body: JSON.stringify(payload) })
  },

  getPortfolioCollection(id: number) {
    return request<PortfolioCollection>(`/portfolio/collections/${id}`)
  },

  updatePortfolioCollection(id: number, payload: PortfolioCollectionPayload) {
    return request<PortfolioCollection>(`/portfolio/collections/${id}`, { method: 'PUT', body: JSON.stringify(payload) })
  },

  deletePortfolioCollection(id: number) {
    return request<void>(`/portfolio/collections/${id}`, { method: 'DELETE' })
  },

  sharePortfolioCollection(id: number) {
    return request<PortfolioShareLink>(`/portfolio/collections/${id}/share`)
  },

  async getPublicPortfolioCollection(shareToken: string) {
    const response = await fetch(`${API_BASE_URL}/portfolio/public/${shareToken}`)
    if (!response.ok) {
      let message = `Request failed (${response.status})`
      try {
        const payload = (await response.json()) as ApiErrorPayload
        message = payload.detail || payload.message || message
      } catch {
        // ignore parse issues
      }
      throw new ApiError(response.status, message)
    }
    return (await response.json()) as PublicPortfolioCollection
  },
}
