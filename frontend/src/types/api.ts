export type AssignmentStatus = 'pending' | 'complete' | 'graded'
export type ReviewAction = 'approve' | 'modify' | 'reject'
export type FamilyRole = 'parent' | 'co-parent' | 'tutor' | 'student_viewer'
export type CapabilityName = 'ai_grading' | 'email' | 'backup' | 'ocr'
export type AuthProvider = 'local' | 'oidc' | 'saml'
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
export type TermType = 'semester' | 'quarter' | 'trimester' | 'custom'
export type CalendarEventType = 'holiday' | 'closure' | 'custom'

export interface ApiErrorPayload {
  detail?: string
  message?: string
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

export interface Assignment {
  id: number
  title: string
  description?: string
  due_date?: string
  status: AssignmentStatus
  subject_id?: number
  subject?: Subject
  created_at?: string
}

export interface Submission {
  id: number
  assignment_id: number
  student_id: number
  file_path?: string
  file_url?: string
  file_type?: string
  ocr_text?: string
  uploaded_at?: string
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
  submission_id?: number
  assignment_id?: number
  assignment_title?: string
  student_id?: number
  student_name?: string
  file_url?: string
  file_path?: string
  ocr_text?: string
  ai_grade?: number
  ai_feedback?: string
  ai_confidence?: number
}

export interface ReviewDecisionPayload {
  action: ReviewAction
  score?: number
  feedback?: string
  notes?: string
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
