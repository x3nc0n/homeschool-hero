export type AssignmentStatus = 'pending' | 'complete' | 'graded'
export type AssignmentCategory = 'homework' | 'quiz' | 'test' | 'project' | 'other'
export type AssignmentRecurrence = 'none' | 'daily' | 'weekly'
export type AssignmentTargetStatus = 'assigned' | 'submitted' | 'graded' | 'excused'
export type PortfolioEntryType = 'work_sample' | 'journal' | 'milestone' | 'photo' | 'note'
export type ReviewAction = 'approve' | 'modify' | 'reject'
export type GradingJobStatus =
  | 'pending'
  | 'ocr_processing'
  | 'ocr_complete'
  | 'ai_grading'
  | 'ai_complete'
  | 'review_needed'
  | 'reviewed'
  | 'final'
export type FamilyRole = 'parent' | 'co-parent' | 'tutor' | 'student_viewer'
export type CapabilityName = 'ai_grading' | 'email' | 'backup' | 'ocr'
export type AuthProvider = 'local' | 'oidc' | 'saml'
export type ScheduleOverrideType = 'cancel' | 'reschedule' | 'add'
export type AttendanceStatus = 'present' | 'absent' | 'tardy' | 'excused'
export type NotificationType =
  | 'due_date'
  | 'grading_complete'
  | 'backup_status'
  | 'security_alert'
  | 'invitation'
  | 'compliance_reminder'
export type AuditAction =
  | 'login'
  | 'logout'
  | 'role_change'
  | 'grade_create'
  | 'grade_update'
  | 'attendance_edit'
  | 'report_generate'
  | 'export'
  | 'restore'
  | 'config_change'
  | 'invitation_create'
  | 'invitation_accept'
  | 'portfolio_entry_create'
  | 'portfolio_entry_update'
  | 'portfolio_entry_delete'
  | 'portfolio_collection_create'
  | 'portfolio_collection_update'
  | 'portfolio_collection_delete'
  | 'portfolio_share'
export type TermType = 'semester' | 'quarter' | 'trimester' | 'custom'
export type CalendarEventType = 'holiday' | 'closure' | 'custom'
export type ResourceType = 'file' | 'link' | 'note'
export type LessonPlanStatus = 'planned' | 'in_progress' | 'completed' | 'skipped' | 'rescheduled'

export interface ApiErrorPayload {
  detail?: string
  message?: string
}

export interface GradeHistoryFilters {
  q?: string
  student_id?: number
  subject_id?: number
  grading_period_id?: number
  term_id?: number
  score_min?: number
  score_max?: number
  date_from?: string
  date_to?: string
}

export interface CapabilityStatus {
  name: CapabilityName
  enabled: boolean
  configured: boolean
  status: 'enabled' | 'disabled'
  reason: string
  details: Record<string, unknown>
  checked_at: string
}

export interface CapabilitiesResponse {
  status: 'ok' | 'degraded'
  capabilities: Record<CapabilityName, CapabilityStatus>
  optional_unavailable: CapabilityName[]
  auth: {
    current_provider: AuthProvider
    available_providers: AuthProvider[]
    local_enabled: boolean
    oidc_enabled: boolean
    saml_enabled: boolean
  }
}

export interface HealthResponse {
  status: 'ok' | 'degraded' | 'required_failure'
  required: Record<string, string>
  optional_unavailable: CapabilityName[]
  capabilities: Record<CapabilityName, CapabilityStatus>
  auth: CapabilitiesResponse['auth']
  required_failures?: Record<string, string>
}

export interface MetricsResponse {
  enabled: boolean
  requests_total: number
  request_duration_ms: {
    count: number
    total: number
    average: number
    max: number
  }
  slow_requests_total: number
  responses_by_status: Record<string, number>
  grading_jobs_total: number
  grading_jobs_by_status: Record<string, number>
  active_users: number
  backup_last_success?: {
    timestamp: string
    age_seconds: number
    size_bytes?: number | null
    artifact?: string | null
  } | null
}

export interface User {
  id: number
  email: string
  display_name: string
  is_active: boolean
  auth_provider: AuthProvider
}

export interface Family {
  id: number
  name: string
}

export interface FamilyMembership {
  role: FamilyRole
  is_owner: boolean
  student_id?: number | null
}

export interface AuthSession {
  authenticated: boolean
  user: User
  family: Family
  membership: FamilyMembership
  message?: string
}

export interface BootstrapStatus {
  bootstrap_required: boolean
}

export interface RegisterPayload {
  family_name: string
  email: string
  display_name: string
  password: string
  timezone?: string
  grading_scale?: string
}

export interface AcceptInvitationPayload {
  token: string
  email: string
  display_name: string
  password: string
}

export interface Student {
  id: number
  name: string
  created_at?: string
}

export interface Subject {
  id: number
  name: string
  color?: string
  created_at?: string
}

export interface AssignmentHistoryEntry {
  timestamp: string
  change_type: string
  field: string
  before?: unknown
  after?: unknown
  student_id?: number | null
}

export interface AssignmentTarget {
  id: number
  assignment_id: number
  student_id: number
  due_date?: string | null
  status: AssignmentTargetStatus
  completed_at?: string | null
  student?: Student
  created_at?: string
  updated_at?: string
}

export interface AssignmentTargetInput {
  student_id: number
  due_date?: string
  status: AssignmentTargetStatus
}

export interface AnswerKeyQuestion {
  question_number: string
  correct_answer: string
  points: number
  partial_credit_rules?: string | null
}

export interface AnswerKey {
  id: number
  assignment_id: number
  family_id: number
  questions: AnswerKeyQuestion[]
  created_at?: string
  updated_at?: string
}

export interface AnswerKeyUpsertPayload {
  questions: AnswerKeyQuestion[]
}

export interface Assignment {
  id: number
  title: string
  description?: string
  due_date?: string
  status: AssignmentStatus
  category: AssignmentCategory
  grading_period_id?: number | null
  grading_period?: GradingPeriod | null
  weight: number
  max_score: number
  recurrence: AssignmentRecurrence
  recurrence_end_date?: string | null
  rubric_description?: string | null
  attachments: string[]
  lesson_plan_id?: number | null
  status_history: AssignmentHistoryEntry[]
  answer_key?: AnswerKey | null
  targets: AssignmentTarget[]
  subject_id?: number
  subject?: Subject
  created_at?: string
  updated_at?: string
}

export interface AssignmentListResponse {
  items: Assignment[]
  total: number
  page: number
  page_size: number
  total_pages: number
}

export interface AssignmentFilters {
  q?: string
  category?: AssignmentCategory | 'all'
  grading_period_id?: number
  subject_id?: number
  student_id?: number
  status?: AssignmentStatus | AssignmentTargetStatus | 'all'
  due_from?: string
  due_to?: string
  page?: number
  page_size?: number
}

export interface AssignmentUpsertPayload {
  title: string
  description?: string
  due_date?: string
  status: AssignmentStatus
  subject_id?: number
  category: AssignmentCategory
  grading_period_id?: number
  weight: number
  max_score: number
  recurrence: AssignmentRecurrence
  recurrence_end_date?: string
  rubric_description?: string
  attachments?: string[]
  lesson_plan_id?: number
  targets?: AssignmentTargetInput[]
}

export interface SubmissionVersion {
  id: number
  assignment_id: number
  student_id: number
  file_path?: string
  file_url?: string
  original_filename?: string
  file_name?: string
  file_type?: string
  file_size_bytes?: number
  image_width?: number | null
  image_height?: number | null
  page_count?: number | null
  submission_version?: number
  parent_submission_id?: number | null
  is_current?: boolean
  ocr_text?: string
  grading_job?: GradingJob | null
  uploaded_at?: string
}

export type Submission = SubmissionVersion

export interface SubmissionDetail extends SubmissionVersion {
  version_history: SubmissionVersion[]
}

export interface PortfolioAssignmentSummary {
  id: number
  title: string
  due_date?: string | null
}

export interface PortfolioEntry {
  id: number
  family_id: number
  student_id: number
  entry_type: PortfolioEntryType
  title: string
  description?: string | null
  date: string
  subject_id?: number | null
  assignment_id?: number | null
  submission_id?: number | null
  attachments: string[]
  attachment_urls: string[]
  tags: string[]
  created_by_user_id: number
  created_at: string
  updated_at: string
  student?: Student | null
  subject?: Subject | null
  assignment?: PortfolioAssignmentSummary | null
  submission?: SubmissionVersion | null
}

export interface PublicPortfolioEntry {
  id: number
  student_id: number
  entry_type: PortfolioEntryType
  title: string
  description?: string | null
  date: string
  subject_id?: number | null
  assignment_id?: number | null
  submission_id?: number | null
  attachments: string[]
  attachment_urls: string[]
  tags: string[]
  created_at: string
  updated_at: string
  subject?: Subject | null
  assignment?: PortfolioAssignmentSummary | null
  submission?: SubmissionVersion | null
}

export interface PortfolioEntryPayload {
  student_id: number
  entry_type: PortfolioEntryType
  title: string
  description?: string
  date: string
  subject_id?: number
  assignment_id?: number
  submission_id?: number
  tags?: string[]
}

export interface PortfolioEntryFilters {
  type?: PortfolioEntryType | 'all'
  subject_id?: number
  date_from?: string
  date_to?: string
  tags?: string
}

export interface PortfolioCollection {
  id: number
  family_id: number
  student_id: number
  name: string
  description?: string | null
  entry_ids: number[]
  is_public: boolean
  share_token?: string | null
  created_at: string
  entries: PortfolioEntry[]
}

export interface PublicPortfolioCollection {
  id: number
  student_id: number
  name: string
  description?: string | null
  is_public: boolean
  share_token: string
  created_at: string
  entries: PublicPortfolioEntry[]
}

export interface PortfolioCollectionPayload {
  student_id: number
  name: string
  description?: string
  entry_ids: number[]
  is_public: boolean
}

export interface PortfolioShareLink {
  collection_id: number
  share_token: string
  url: string
}

export interface Grade {
  id: number
  student_id: number
  subject_id?: number
  assignment_id?: number
  submission_id?: number
  score: number
  max_score: number
  letter_grade?: string
  notes?: string
  graded_by?: 'human' | 'ai' | 'ai+human'
  ai_confidence?: number
  created_at?: string
  student?: Student
  subject?: Subject
  assignment?: Assignment
}

export type QuizQuestionType = 'multiple_choice' | 'short_answer' | 'true_false'

export interface QuizQuestion {
  type: QuizQuestionType
  prompt: string
  options?: string[]
  correct_answer: string
}

export interface Quiz {
  id: number
  title: string
  subject_id?: number
  questions: QuizQuestion[]
  created_at?: string
}

export interface QuizAttempt {
  id: number
  quiz_id: number
  student_id: number
  answers: string[]
  score: number
  max_score: number
  completed_at?: string
}

export interface ReviewQueueItem {
  id: number
  family_id: number
  created_by_user_id: number
  submission_id?: number
  assignment_id?: number
  assignment_title?: string
  student_id?: number
  student_name?: string
  file_url?: string
  file_path?: string
  file_type?: string
  status: GradingJobStatus
  ocr_result?: string
  ai_grade?: number
  ai_feedback?: string
  ai_confidence?: number
  ai_response?: string
  answer_key_result?: {
    score: number
    max_score: number
    confidence: number
    answered_questions: number
    total_questions: number
    questions: Array<{
      question_number: string
      correct_answer: string
      student_answer?: string | null
      points: number
      awarded_points: number
      is_correct: boolean
      partial_credit_rules?: string | null
      similarity?: number
    }>
  } | null
  status_history?: Array<{
    timestamp: string
    status: GradingJobStatus | string
    detail?: string | null
    payload?: Record<string, unknown>
  }>
  human_override_details?: {
    reviewed_at?: string
    reviewed_by_user_id?: number
    action?: ReviewAction
    override_reason?: string | null
    notes?: string | null
    feedback?: string | null
    final_score?: number
    ai_score?: number | null
  } | null
  manual_review_reason?: string | null
  ocr_retry_count?: number
  ai_retry_count?: number
  error_message?: string | null
  created_at?: string
  completed_at?: string | null
}

export type GradingJob = ReviewQueueItem

export interface ReviewDecisionPayload {
  action: ReviewAction
  score?: number
  feedback?: string
  notes?: string
  override_reason?: string
}

export interface Invitation {
  id: number
  email: string
  role: FamilyRole
  student_id?: number | null
  student_name?: string | null
  expires_at: string
  accepted_at?: string | null
  invite_link?: string | null
  invite_code?: string | null
  delivery_method: 'email' | 'link'
  email_sent: boolean
  is_expired: boolean
  created_at: string
}

export interface CreateInvitationPayload {
  email: string
  role: FamilyRole
  student_id?: number
  expires_in_days?: number
}

export interface AuditEvent {
  id: number
  family_id: number
  actor_user_id: number
  actor_display_name?: string | null
  actor_email?: string | null
  action: AuditAction
  target_entity_type: string
  target_entity_id?: string | null
  before_snapshot?: Record<string, unknown> | null
  after_snapshot?: Record<string, unknown> | null
  ip_address?: string | null
  user_agent?: string | null
  timestamp: string
}

export interface AuditEventListResponse {
  items: AuditEvent[]
  total: number
  page: number
  page_size: number
  total_pages: number
}

export interface AuditEventFilters {
  page?: number
  page_size?: number
  date_from?: string
  date_to?: string
  actor?: string
  action?: AuditAction | 'all'
  entity_type?: string
  entity_id?: string
}

export type SearchEntityType =
  | 'assignment'
  | 'grade'
  | 'student'
  | 'subject'
  | 'attendance_note'
  | 'audit_log'
  | 'curriculum'
  | 'resource'
  | 'note'
  | 'notification'

export interface SearchResult {
  entity_type: SearchEntityType
  entity_id: string
  title: string
  snippet: string
  link: string
  created_at?: string | null
  student_id?: number | null
  subject_id?: number | null
  status?: string | null
}

export interface SearchResponse {
  items: SearchResult[]
  total: number
  page: number
  page_size: number
  total_pages: number
  facets: Record<string, number>
}

export interface SearchFilters {
  q?: string
  type?: SearchEntityType | 'all'
  student_id?: number
  subject_id?: number
  term_id?: number
  grading_period_id?: number
  status?: string
  date_from?: string
  date_to?: string
  score_min?: number
  score_max?: number
  page?: number
  page_size?: number
}

export interface GradeHistoryItem {
  grade_id: number
  student_id: number
  student_name: string
  subject_id: number
  subject_name: string
  assignment_id: number
  assignment_title: string
  score: number
  max_score: number
  percent: number
  letter_grade?: string | null
  graded_by: 'human' | 'ai' | 'ai+human'
  created_at: string
  grading_period_id?: number | null
  grading_period_name?: string | null
  notes?: string | null
}

export interface DashboardActivityItem {
  id: string
  type: 'audit' | 'grading_job'
  timestamp: string
  title: string
  subtitle: string
  status: string
  details: Record<string, unknown>
}

export interface DashboardSummary {
  recent_activity: DashboardActivityItem[]
  system_health: {
    status: 'ok' | 'degraded'
    requests_total: number
    slow_requests_total: number
    grading_jobs_by_status: Record<string, number>
    active_users: number
    backup_last_success?: MetricsResponse['backup_last_success']
    metrics_enabled: boolean
    generated_at: string
  }
}

export interface Notification {
  id: number
  family_id: number
  user_id: number
  type: NotificationType
  title: string
  message: string
  read: boolean
  created_at: string
  link?: string | null
}

export interface NotificationListResponse {
  items: Notification[]
  total: number
  unread_count: number
  page: number
  page_size: number
  total_pages: number
}

export interface NotificationPreference {
  notification_type: NotificationType
  in_app_enabled: boolean
  email_enabled: boolean
}

export interface AttendanceExcuse {
  id: number
  family_id: number
  attendance_record_id: number
  reason: string
  document_path?: string | null
  document_url?: string | null
  approved_by_user_id?: number | null
  approved_at?: string | null
  created_at?: string
  updated_at?: string
}

export interface AttendanceRecord {
  id: number
  family_id: number
  student_id: number
  date: string
  status: AttendanceStatus
  check_in_time?: string | null
  check_out_time?: string | null
  instructional_hours: string
  notes?: string | null
  student?: Student | null
  excuse?: AttendanceExcuse | null
  created_at?: string
  updated_at?: string
}

export interface AttendanceSummaryBucket {
  label: string
  start_date: string
  end_date: string
  total_records: number
  present: number
  absent: number
  tardy: number
  excused: number
  attendance_rate: number
  total_hours: string
}

export interface AttendanceSummary {
  student_id: number
  school_year_id?: number | null
  period: 'day' | 'week' | 'term' | 'year'
  total_records: number
  present: number
  absent: number
  tardy: number
  excused: number
  attendance_rate: number
  total_hours: string
  buckets: AttendanceSummaryBucket[]
}

export interface AttendanceHoursSummary {
  student_id: number
  school_year_id: number
  total_hours: string
  recorded_days: number
  average_hours_per_day: number
}

export interface GradingPeriod {
  id: number
  term_id: number
  family_id: number
  name: string
  start_date: string
  end_date: string
  created_at?: string
  updated_at?: string
}

export interface Term {
  id: number
  school_year_id: number
  family_id: number
  name: string
  start_date: string
  end_date: string
  term_type: TermType
  grading_periods: GradingPeriod[]
  created_at?: string
  updated_at?: string
}

export interface CalendarEvent {
  id: number
  family_id: number
  school_year_id: number
  date: string
  event_type: CalendarEventType
  name: string
  is_instructional_day: boolean
  notes?: string | null
  created_at?: string
  updated_at?: string
}

export interface SchoolYear {
  id: number
  family_id: number
  name: string
  start_date: string
  end_date: string
  is_active: boolean
  created_at?: string
  updated_at?: string
}

export interface SchoolYearDetail extends SchoolYear {
  terms: Term[]
  calendar_events: CalendarEvent[]
}

export interface InstructionalDayCount {
  school_year_id: number
  instructional_days: number
  weekday_days: number
  non_instructional_overrides: number
  instructional_overrides: number
}

export interface Schedule {
  id: number
  family_id: number
  student_id: number
  school_year_id: number
  name: string
  student: Student
  school_year: SchoolYear
  created_at?: string
  updated_at?: string
}

export interface ScheduleBlock {
  id: number
  schedule_id: number
  subject_id: number
  day_of_week: number
  start_time: string
  end_time: string
  location?: string | null
  notes?: string | null
  subject: Subject
  created_at?: string
  updated_at?: string
}

export interface ScheduleOverride {
  id: number
  schedule_id: number
  date: string
  original_block_id?: number | null
  override_type: ScheduleOverrideType
  subject_id?: number | null
  start_time?: string | null
  end_time?: string | null
  reason: string
  subject?: Subject | null
  created_at?: string
  updated_at?: string
}

export interface ScheduleDetail extends Schedule {
  blocks: ScheduleBlock[]
  overrides: ScheduleOverride[]
}

export interface AgendaItem {
  schedule_id: number
  schedule_name: string
  block_id?: number | null
  override_id?: number | null
  date: string
  day_of_week: number
  source: 'recurring' | 'override'
  override_type?: ScheduleOverrideType | null
  subject_id: number
  subject_name: string
  subject_color: string
  start_time: string
  end_time: string
  location?: string | null
  notes?: string | null
  reason?: string | null
}

export interface DailyAgenda {
  student_id: number
  date: string
  items: AgendaItem[]
}

export interface WeeklyAgenda {
  student_id: number
  week_start: string
  week_end: string
  days: DailyAgenda[]
}

export interface ResourceSummary {
  id: number
  name: string
  resource_type: ResourceType
  file_url?: string | null
  url?: string | null
  tags: string[]
}

export interface CurriculumLesson {
  id: number
  unit_id: number
  name: string
  description?: string | null
  sequence_order: number
  estimated_duration_minutes?: number | null
  standards_tags: string[]
  resources: ResourceSummary[]
  created_at?: string
  updated_at?: string
}

export interface CurriculumUnit {
  id: number
  package_id: number
  name: string
  description?: string | null
  sequence_order: number
  standards_tags: string[]
  lessons: CurriculumLesson[]
  created_at?: string
  updated_at?: string
}

export interface CurriculumPackage {
  id: number
  family_id: number
  school_year_id: number
  name: string
  description?: string | null
  subject_id: number
  created_by_user_id: number
  created_at?: string
  updated_at?: string
}

export interface CurriculumPackageDetail extends CurriculumPackage {
  units: CurriculumUnit[]
}

export interface LessonPlanLessonPackageSummary {
  id: number
  name: string
  subject_id: number
}

export interface LessonPlanLessonUnitSummary {
  id: number
  name: string
  sequence_order: number
  package: LessonPlanLessonPackageSummary
}

export interface LessonPlanLessonSummary {
  id: number
  unit_id: number
  name: string
  description?: string | null
  sequence_order: number
  estimated_duration_minutes?: number | null
  standards_tags: string[]
  resources: ResourceSummary[]
  unit: LessonPlanLessonUnitSummary
}

export interface LessonPlan {
  id: number
  family_id: number
  curriculum_lesson_id: number
  student_id: number
  school_year_id: number
  target_date: string
  estimated_duration_minutes?: number | null
  status: LessonPlanStatus
  completed_at?: string | null
  notes?: string | null
  assignment_ids: number[]
  curriculum_lesson: LessonPlanLessonSummary
  student: Student
  school_year: SchoolYear
  created_at?: string
  updated_at?: string
}

export interface LessonPlanFilters {
  student_id?: number
  school_year_id?: number
  subject_id?: number
  status?: LessonPlanStatus | 'all'
  start_date?: string
  end_date?: string
}

export interface LessonPlanUpsertPayload {
  curriculum_lesson_id: number
  student_id: number
  school_year_id: number
  target_date: string
  estimated_duration_minutes?: number
  status: LessonPlanStatus
  notes?: string
}

export interface LessonPlanGenerationPayload {
  package_id: number
  student_id: number
  school_year_id?: number
  start_date?: string
  default_duration_minutes?: number
  overwrite_existing?: boolean
}

export interface LessonPlanBulkStatusPayload {
  lesson_plan_ids: number[]
  status: LessonPlanStatus
  target_date?: string
  notes?: string
}

export interface PacingTargetUnitSummary {
  id: number
  package_id: number
  name: string
  sequence_order: number
  package: LessonPlanLessonPackageSummary
}

export interface PacingTarget {
  id: number
  family_id: number
  curriculum_unit_id: number
  student_id: number
  target_start_date: string
  target_end_date: string
  actual_completion_date?: string | null
  curriculum_unit: PacingTargetUnitSummary
  student: Student
  created_at?: string
  updated_at?: string
}

export interface PacingTargetUpsertPayload {
  curriculum_unit_id: number
  student_id: number
  target_start_date: string
  target_end_date: string
}

export interface PacingStatusItem {
  pacing_target_id: number
  curriculum_unit_id: number
  unit_name: string
  package_id: number
  package_name: string
  subject_id: number
  target_start_date: string
  target_end_date: string
  actual_completion_date?: string | null
  status: 'ahead' | 'on_track' | 'behind'
  total_lessons: number
  planned_lessons: number
  completed_lessons: number
  remaining_lessons: number
}

export interface PacingStatusSummary {
  student_id: number
  subject_id?: number | null
  items: PacingStatusItem[]
}

export interface Resource {
  id: number
  family_id: number
  name: string
  description?: string | null
  resource_type: ResourceType
  file_path?: string | null
  file_url?: string | null
  url?: string | null
  tags: string[]
  metadata: Record<string, unknown>
  lesson_ids: number[]
  created_by_user_id: number
  created_at?: string
  updated_at?: string
}
