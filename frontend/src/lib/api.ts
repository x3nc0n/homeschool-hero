import type {
  AcceptInvitationPayload,
  AuditEventFilters,
  AuditEventListResponse,
  ApiErrorPayload,
  Assignment,
  CalendarEvent,
  AuthSession,
  BootstrapStatus,
  CapabilitiesResponse,
  CreateInvitationPayload,
  Grade,
  GradingPeriod,
  InstructionalDayCount,
  Invitation,
  Quiz,
  QuizAttempt,
  RegisterPayload,
  ReviewDecisionPayload,
  ReviewQueueItem,
  SchoolYear,
  SchoolYearDetail,
  Student,
  Subject,
  Submission,
  Term,
} from '@/types/api'

export const API_BASE_URL = import.meta.env.VITE_API_URL || '/api'

export class ApiError extends Error {
  status: number

  constructor(status: number, message: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
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

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    credentials: 'include',
    headers: {
      'Content-Type': 'application/json',
      ...(init?.headers || {}),
    },
    ...init,
  })

  if (!response.ok) {
    let message = `Request failed (${response.status})`
    try {
      const payload = await parseResponse<ApiErrorPayload>(response)
      message = payload.detail || payload.message || message
    } catch {
      // ignore parse issues
    }
    throw new ApiError(response.status, message)
  }

  return parseResponse<T>(response)
}

export const api = {
  getBootstrapStatus() {
    return request<BootstrapStatus>('/auth/bootstrap')
  },

  getCapabilities() {
    return request<CapabilitiesResponse>('/capabilities')
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

  createInvitation(payload: CreateInvitationPayload) {
    return request<Invitation>('/invitations', { method: 'POST', body: JSON.stringify(payload) })
  },

  revokeInvitation(id: number) {
    return request<void>(`/invitations/${id}/revoke`, { method: 'DELETE' })
  },

  listStudents() {
    return request<Student[]>('/students')
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

  createSubject(payload: Pick<Subject, 'name' | 'color'>) {
    return request<Subject>('/subjects', { method: 'POST', body: JSON.stringify(payload) })
  },

  updateSubject(id: number, payload: Partial<Pick<Subject, 'name' | 'color'>>) {
    return request<Subject>(`/subjects/${id}`, { method: 'PUT', body: JSON.stringify(payload) })
  },

  deleteSubject(id: number) {
    return request<void>(`/subjects/${id}`, { method: 'DELETE' })
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

  listAssignments() {
    return request<Assignment[]>('/assignments')
  },

  createAssignment(payload: Partial<Assignment>) {
    return request<Assignment>('/assignments', { method: 'POST', body: JSON.stringify(payload) })
  },

  updateAssignment(id: number, payload: Partial<Assignment>) {
    return request<Assignment>(`/assignments/${id}`, { method: 'PUT', body: JSON.stringify(payload) })
  },

  deleteAssignment(id: number) {
    return request<void>(`/assignments/${id}`, { method: 'DELETE' })
  },

  listGrades() {
    return request<Grade[]>('/grades')
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

  listReviewQueue() {
    return request<ReviewQueueItem[]>('/grading/review-queue')
  },

  submitReviewDecision(reviewId: number, payload: ReviewDecisionPayload) {
    return request<ReviewQueueItem>(`/grading/review/${reviewId}`, {
      method: 'POST',
      body: JSON.stringify(payload),
    })
  },

  uploadSubmission(
    payload: { assignment_id: number; student_id: number; file: File },
    onProgress?: (progress: number) => void,
  ) {
    return new Promise<Submission>((resolve, reject) => {
      const formData = new FormData()
      formData.append('assignment_id', String(payload.assignment_id))
      formData.append('student_id', String(payload.student_id))
      formData.append('file', payload.file)

      const xhr = new XMLHttpRequest()
      xhr.open('POST', `${API_BASE_URL}/submissions`)
      xhr.withCredentials = true

      xhr.upload.addEventListener('progress', (event) => {
        if (event.lengthComputable) {
          onProgress?.(Math.round((event.loaded / event.total) * 100))
        }
      })

      xhr.onload = () => {
        if (xhr.status >= 200 && xhr.status < 300) {
          resolve(JSON.parse(xhr.responseText) as Submission)
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
}
