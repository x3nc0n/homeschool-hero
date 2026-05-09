import { useCallback, useEffect, useMemo, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { api } from '@/lib/api'
import type { GradeHistoryItem, GradingPeriod, Student, Subject } from '@/types/api'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { LoadingState } from '@/components/common/LoadingState'
import { ErrorState } from '@/components/common/ErrorState'
import { EmptyState } from '@/components/common/EmptyState'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'

type GradeFilters = {
  q: string
  student_id: string
  subject_id: string
  grading_period_id: string
  score_min: string
  score_max: string
  date_from: string
  date_to: string
}

function readInitialFilters(searchParams: URLSearchParams): GradeFilters {
  return {
    q: searchParams.get('q') || searchParams.get('search') || '',
    student_id: searchParams.get('student_id') || 'all',
    subject_id: searchParams.get('subject_id') || 'all',
    grading_period_id: searchParams.get('grading_period_id') || 'all',
    score_min: searchParams.get('score_min') || '',
    score_max: searchParams.get('score_max') || '',
    date_from: searchParams.get('date_from') || '',
    date_to: searchParams.get('date_to') || '',
  }
}

export function GradesPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const [grades, setGrades] = useState<GradeHistoryItem[]>([])
  const [students, setStudents] = useState<Student[]>([])
  const [subjects, setSubjects] = useState<Subject[]>([])
  const [gradingPeriods, setGradingPeriods] = useState<GradingPeriod[]>([])
  const [filters, setFilters] = useState<GradeFilters>(() => readInitialFilters(searchParams))
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const schoolYears = await api.listSchoolYears()
      const schoolYearDetails = await Promise.all(schoolYears.map((year) => api.getSchoolYear(year.id)))
      const allGradingPeriods = schoolYearDetails.flatMap((year) => year.terms.flatMap((term) => term.grading_periods))
      const [gradeData, studentData, subjectData] = await Promise.all([
        api.listGradeHistory({
          q: filters.q || undefined,
          student_id: filters.student_id === 'all' ? undefined : Number(filters.student_id),
          subject_id: filters.subject_id === 'all' ? undefined : Number(filters.subject_id),
          grading_period_id: filters.grading_period_id === 'all' ? undefined : Number(filters.grading_period_id),
          score_min: filters.score_min ? Number(filters.score_min) : undefined,
          score_max: filters.score_max ? Number(filters.score_max) : undefined,
          date_from: filters.date_from || undefined,
          date_to: filters.date_to || undefined,
        }),
        api.listStudents(),
        api.listSubjects(),
      ])
      setGrades(gradeData)
      setStudents(studentData)
      setSubjects(subjectData)
      setGradingPeriods(allGradingPeriods)
    } catch (gradeError) {
      setError(gradeError instanceof Error ? gradeError.message : 'Unable to load grade book')
    } finally {
      setLoading(false)
    }
  }, [filters])

  useEffect(() => {
    void load()
  }, [load])

  useEffect(() => {
    const params = new URLSearchParams()
    Object.entries(filters).forEach(([key, value]) => {
      if (!value || value === 'all') return
      params.set(key === 'q' ? 'search' : key, value)
    })
    setSearchParams(params, { replace: true })
  }, [filters, setSearchParams])

  const averageByStudent = useMemo(() => {
    const buckets = new Map<number, { total: number; count: number }>()
    grades.forEach((grade) => {
      const current = buckets.get(grade.student_id) || { total: 0, count: 0 }
      current.total += grade.percent
      current.count += 1
      buckets.set(grade.student_id, current)
    })
    return Array.from(buckets.entries()).map(([studentId, bucket]) => ({
      studentId,
      average: bucket.total / bucket.count,
    }))
  }, [grades])

  if (loading) return <LoadingState message="Loading grade book…" />
  if (error) return <ErrorState message={error} onRetry={() => void load()} />
  if (!grades.length) return <EmptyState title="No grades yet" description="Grades will appear after submissions are scored." />

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <CardTitle>Grade book</CardTitle>
          <CardDescription>Filter by keyword, student, subject, grading period, score range, and date.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-4 xl:grid-cols-3">
            <div className="space-y-2 xl:col-span-3">
              <Label>Search</Label>
              <Input value={filters.q} onChange={(event) => setFilters((current) => ({ ...current, q: event.target.value }))} placeholder="Assignment title, subject, notes, or student" />
            </div>
            <div className="space-y-2">
              <Label>Student</Label>
              <Select value={filters.student_id} onValueChange={(value) => setFilters((current) => ({ ...current, student_id: value }))}>
                <SelectTrigger>
                  <SelectValue placeholder="All students" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All students</SelectItem>
                  {students.map((student) => (
                    <SelectItem key={student.id} value={String(student.id)}>
                      {student.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label>Subject</Label>
              <Select value={filters.subject_id} onValueChange={(value) => setFilters((current) => ({ ...current, subject_id: value }))}>
                <SelectTrigger>
                  <SelectValue placeholder="All subjects" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All subjects</SelectItem>
                  {subjects.map((subject) => (
                    <SelectItem key={subject.id} value={String(subject.id)}>
                      {subject.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label>Grading period</Label>
              <Select value={filters.grading_period_id} onValueChange={(value) => setFilters((current) => ({ ...current, grading_period_id: value }))}>
                <SelectTrigger>
                  <SelectValue placeholder="All periods" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All periods</SelectItem>
                  {gradingPeriods.map((gradingPeriod) => (
                    <SelectItem key={gradingPeriod.id} value={String(gradingPeriod.id)}>
                      {gradingPeriod.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label>Min grade %</Label>
              <Input type="number" min="0" max="100" value={filters.score_min} onChange={(event) => setFilters((current) => ({ ...current, score_min: event.target.value }))} />
            </div>
            <div className="space-y-2">
              <Label>Max grade %</Label>
              <Input type="number" min="0" max="100" value={filters.score_max} onChange={(event) => setFilters((current) => ({ ...current, score_max: event.target.value }))} />
            </div>
            <div className="space-y-2">
              <Label>From</Label>
              <Input type="date" value={filters.date_from} onChange={(event) => setFilters((current) => ({ ...current, date_from: event.target.value }))} />
            </div>
            <div className="space-y-2">
              <Label>To</Label>
              <Input type="date" value={filters.date_to} onChange={(event) => setFilters((current) => ({ ...current, date_to: event.target.value }))} />
            </div>
          </div>

          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Student</TableHead>
                <TableHead>Assignment</TableHead>
                <TableHead>Subject</TableHead>
                <TableHead>Period</TableHead>
                <TableHead>Score</TableHead>
                <TableHead>Letter</TableHead>
                <TableHead>Graded</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {grades.map((grade) => (
                <TableRow key={grade.grade_id}>
                  <TableCell>{grade.student_name || students.find((student) => student.id === grade.student_id)?.name || grade.student_id}</TableCell>
                  <TableCell>
                    <div className="font-medium">{grade.assignment_title}</div>
                    {grade.notes ? <div className="text-xs text-muted-foreground">{grade.notes}</div> : null}
                  </TableCell>
                  <TableCell>{grade.subject_name || subjects.find((subject) => subject.id === grade.subject_id)?.name || '—'}</TableCell>
                  <TableCell>{grade.grading_period_name || '—'}</TableCell>
                  <TableCell>
                    {grade.score}/{grade.max_score} ({grade.percent.toFixed(1)}%)
                  </TableCell>
                  <TableCell>{grade.letter_grade || '—'}</TableCell>
                  <TableCell>{new Date(grade.created_at).toLocaleDateString()}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Averages</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2">
          {averageByStudent.map((entry) => (
            <div key={entry.studentId} className="flex items-center justify-between rounded-md border p-3 text-sm">
              <span>{students.find((student) => student.id === entry.studentId)?.name || `Student #${entry.studentId}`}</span>
              <span className="font-semibold">{entry.average.toFixed(1)}%</span>
            </div>
          ))}
        </CardContent>
      </Card>
    </div>
  )
}
