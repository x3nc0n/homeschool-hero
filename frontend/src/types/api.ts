export type AssignmentStatus = 'pending' | 'complete' | 'graded'
export type ReviewAction = 'approve' | 'modify' | 'reject'
export type FamilyRole = 'parent' | 'co-parent' | 'tutor' | 'student_viewer'
export type CapabilityName = 'ai_grading' | 'email' | 'backup' | 'ocr'

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
}

export interface User {
  id: number
  email: string
  display_name: string
  is_active: boolean
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
