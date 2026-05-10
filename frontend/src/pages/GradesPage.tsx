import { useCallback, useEffect, useMemo, useState } from 'react'
import { RefreshCcw } from 'lucide-react'
import { useSearchParams } from 'react-router-dom'
import { api } from '@/lib/api'
import type { GradebookSummary, GradebookTrends, GradebookView, GradingPeriod, Student, Subject } from '@/types/api'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { LoadingState } from '@/components/common/LoadingState'
import { ErrorState } from '@/components/common/ErrorState'
import { EmptyState } from '@/components/common/EmptyState'
import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'

type GradeFilters = {
  student_id: string
  subject_id: string
  grading_period_id: string
}

function readInitialFilters(searchParams: URLSearchParams): GradeFilters {
  return {
    student_id: searchParams.get('student_id') || '',
    subject_id: searchParams.get('subject_id') || 'all',
    grading_period_id: searchParams.get('grading_period_id') || 'all',
  }
}

function TrendChart({ trends }: { trends: GradebookTrends['series'][number]['points'] }) {
  if (!trends.length) {
    return <p className="text-sm text-muted-foreground">No graded work yet.</p>
  }
  const width = 480
  const height = 180
  const padding = 20
  const maxX = Math.max(trends.length - 1, 1)
  const points = trends.map((point, index) => {
    const x = padding + (index / maxX) * (width - padding * 2)
    const y = height - padding - (point.overall_percent / 100) * (height - padding * 2)
    return `${x},${y}`
  })

  return (
    <svg viewBox={`0 0 ${width} ${height}`} className="h-44 w-full">
      <line x1={padding} y1={height - padding} x2={width - padding} y2={height - padding} stroke="currentColor" strokeOpacity="0.15" />
      <line x1={padding} y1={padding} x2={padding} y2={height - padding} stroke="currentColor" strokeOpacity="0.15" />
      <polyline fill="none" stroke="currentColor" strokeWidth="2.5" points={points.join(' ')} />
      {trends.map((point, index) => {
        const [x, y] = points[index].split(',').map(Number)
        return <circle key={point.assignment_id} cx={x} cy={y} r="3.5" fill="currentColor" />
      })}
    </svg>
  )
}

export function GradesPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const [gradebook, setGradebook] = useState<GradebookView | null>(null)
  const [summary, setSummary] = useState<GradebookSummary | null>(null)
  const [trends, setTrends] = useState<GradebookTrends | null>(null)
  const [students, setStudents] = useState<Student[]>([])
  const [subjects, setSubjects] = useState<Subject[]>([])
  const [gradingPeriods, setGradingPeriods] = useState<GradingPeriod[]>([])
  const [filters, setFilters] = useState<GradeFilters>(() => readInitialFilters(searchParams))
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [error, setError] = useState('')

  const selectedStudentId = filters.student_id ? Number(filters.student_id) : undefined

  const loadReferenceData = useCallback(async () => {
    const schoolYears = await api.listSchoolYears()
    const schoolYearDetails = await Promise.all(schoolYears.map((year) => api.getSchoolYear(year.id)))
    const allGradingPeriods = schoolYearDetails.flatMap((year) => year.terms.flatMap((term) => term.grading_periods))
    const [studentData, subjectData] = await Promise.all([api.listStudents(), api.listSubjects()])
    return { studentData, subjectData, allGradingPeriods }
  }, [])

  const load = useCallback(
    async (recalculate = false) => {
      setLoading(true)
      setRefreshing(recalculate)
      setError('')
      try {
        const { studentData, subjectData, allGradingPeriods } = await loadReferenceData()
        setStudents(studentData)
        setSubjects(subjectData)
        setGradingPeriods(allGradingPeriods)
        const resolvedStudentId = selectedStudentId || studentData[0]?.id
        if (!resolvedStudentId) {
          setGradebook(null)
          setSummary(null)
          setTrends(null)
          return
        }
        if (!selectedStudentId) {
          setFilters((current) => ({ ...current, student_id: String(resolvedStudentId) }))
        }

        const query = {
          subject_id: filters.subject_id === 'all' ? undefined : Number(filters.subject_id),
          grading_period_id: filters.grading_period_id === 'all' ? undefined : Number(filters.grading_period_id),
        }

        if (recalculate) {
          await api.recalculateGradebook({ student_id: resolvedStudentId, ...query })
        }

        const [detail, summaryData, trendData] = await Promise.all([
          api.getGradebook(resolvedStudentId, query),
          api.getGradebookSummary(resolvedStudentId),
          api.getGradeTrends(resolvedStudentId, query),
        ])
        setGradebook(detail)
        setSummary(summaryData)
        setTrends(trendData)
      } catch (gradeError) {
        setError(gradeError instanceof Error ? gradeError.message : 'Unable to load grade book')
      } finally {
        setLoading(false)
        setRefreshing(false)
      }
    },
    [filters.grading_period_id, filters.subject_id, loadReferenceData, selectedStudentId],
  )

  useEffect(() => {
    void load()
  }, [load])

  useEffect(() => {
    setSearchParams((current) => {
      const params = new URLSearchParams(current)
      params.delete('student_id')
      params.delete('subject_id')
      params.delete('grading_period_id')

      Object.entries(filters).forEach(([key, value]) => {
        if (!value || value === 'all') return
        params.set(key, value)
      })

      return params
    }, { replace: true })
  }, [filters, setSearchParams])

  const filteredSummarySubjects = useMemo(() => {
    if (!summary) return []
    if (filters.subject_id === 'all') return summary.subjects
    return summary.subjects.filter((subject) => subject.subject_id === Number(filters.subject_id))
  }, [filters.subject_id, summary])

  if (loading) return <LoadingState message="Loading grade book…" />
  if (error && !gradebook) return <ErrorState message={error} onRetry={() => void load()} />
  if (!students.length) return <EmptyState title="No students yet" description="Add a student before opening the gradebook." />
  if (!gradebook || !gradebook.subjects.length) {
    return <EmptyState title="No graded work yet" description="Grades will appear here after assignments are scored." />
  }

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <CardTitle>Gradebook</CardTitle>
          <CardDescription>Weighted categories, running grades, GPA, and trends by subject.</CardDescription>
        </CardHeader>
        <CardContent className="grid gap-4 lg:grid-cols-4">
          <div className="space-y-2">
            <Label>Student</Label>
            <Select value={filters.student_id} onValueChange={(value) => setFilters((current) => ({ ...current, student_id: value }))}>
              <SelectTrigger>
                <SelectValue placeholder="Choose a student" />
              </SelectTrigger>
              <SelectContent>
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
          <div className="flex items-end">
            <Button variant="outline" onClick={() => void load(true)} disabled={refreshing}>
              <RefreshCcw className="mr-2 h-4 w-4" />
              {refreshing ? 'Refreshing…' : 'Recalculate'}
            </Button>
          </div>
        </CardContent>
      </Card>

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <Card>
          <CardHeader>
            <CardTitle>Overall GPA</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-3xl font-bold">{summary?.gpa?.toFixed(2) ?? '—'}</p>
          </CardContent>
        </Card>
        {filteredSummarySubjects.map((subject) => (
          <Card key={subject.subject_id}>
            <CardHeader>
              <CardTitle>{subject.subject_name}</CardTitle>
              <CardDescription>{subject.graded_assignments}/{subject.assignments} graded</CardDescription>
            </CardHeader>
            <CardContent>
              <p className="text-2xl font-bold">{subject.overall_percent?.toFixed(1) ?? '—'}%</p>
              <p className="text-sm text-muted-foreground">
                {subject.letter_grade || '—'} · GPA {subject.gpa_points?.toFixed(2) ?? '—'}
              </p>
            </CardContent>
          </Card>
        ))}
      </div>

      {gradebook.subjects.map((subject) => {
        const trendSeries = trends?.series.find((series) => series.subject_id === subject.subject_id)
        return (
          <div key={subject.subject_id} className="space-y-4">
            <Card>
              <CardHeader>
                <CardTitle>{subject.subject_name}</CardTitle>
                <CardDescription>
                  {subject.overall_percent?.toFixed(1) ?? '—'}% · {subject.letter_grade || '—'} · GPA {subject.gpa_points?.toFixed(2) ?? '—'} ·{' '}
                  {subject.grading_mode === 'percentage' ? 'Percentage mode' : 'Points mode'}
                </CardDescription>
              </CardHeader>
              <CardContent>
                <TrendChart trends={trendSeries?.points ?? []} />
              </CardContent>
            </Card>

            {subject.categories.map((category) => (
              <Card key={`${subject.subject_id}-${category.name}`}>
                <CardHeader>
                  <CardTitle className="capitalize">{category.name.replace('_', ' ')}</CardTitle>
                  <CardDescription>
                    Weight {(category.weight * 100).toFixed(0)}% · Average {category.average_percent?.toFixed(1) ?? '—'}% · Drop lowest {category.drop_lowest}
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  {category.items.length ? (
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead>Assignment</TableHead>
                          <TableHead>Due</TableHead>
                          <TableHead>Score</TableHead>
                          <TableHead>Running total</TableHead>
                          <TableHead>Status</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {category.items.map((item) => (
                          <TableRow key={item.assignment_id}>
                            <TableCell>
                              <div className="font-medium">{item.assignment_title}</div>
                              {item.is_dropped ? <div className="text-xs text-muted-foreground">Dropped from category average</div> : null}
                            </TableCell>
                            <TableCell>{item.due_date ? new Date(item.due_date).toLocaleDateString() : '—'}</TableCell>
                            <TableCell>{item.score !== null && item.score !== undefined ? `${item.score}/${item.max_score} (${item.percent?.toFixed(1)}%)` : 'Not graded'}</TableCell>
                            <TableCell>{item.running_overall_percent !== null && item.running_overall_percent !== undefined ? `${item.running_overall_percent.toFixed(1)}%` : '—'}</TableCell>
                            <TableCell>{item.status}</TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  ) : (
                    <p className="text-sm text-muted-foreground">No assignments in this category yet.</p>
                  )}
                </CardContent>
              </Card>
            ))}
          </div>
        )
      })}

      {error ? <p className="text-sm text-destructive">{error}</p> : null}
    </div>
  )
}
