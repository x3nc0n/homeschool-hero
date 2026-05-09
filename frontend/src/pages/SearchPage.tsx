import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { Search as SearchIcon } from 'lucide-react'
import { api } from '@/lib/api'
import { getRecentSearches, storeRecentSearch } from '@/lib/searchHistory'
import type { GradingPeriod, SearchEntityType, SearchResult, Student, Subject } from '@/types/api'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { EmptyState } from '@/components/common/EmptyState'
import { ErrorState } from '@/components/common/ErrorState'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { LoadingState } from '@/components/common/LoadingState'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'

const entityTypeLabels: Record<SearchEntityType, string> = {
  assignment: 'Assignments',
  grade: 'Grades',
  student: 'Students',
  subject: 'Subjects',
  attendance_note: 'Attendance notes',
  audit_log: 'Audit logs',
  curriculum: 'Curriculum',
  resource: 'Resources',
  note: 'Notes',
  notification: 'Notifications',
}

type SearchFormState = {
  q: string
  type: SearchEntityType | 'all'
  student_id: string
  subject_id: string
  grading_period_id: string
  status: string
  date_from: string
  date_to: string
}

function readQueryState(searchParams: URLSearchParams): SearchFormState {
  return {
    q: searchParams.get('q') || '',
    type: (searchParams.get('type') as SearchEntityType | 'all' | null) || 'all',
    student_id: searchParams.get('student_id') || 'all',
    subject_id: searchParams.get('subject_id') || 'all',
    grading_period_id: searchParams.get('grading_period_id') || 'all',
    status: searchParams.get('status') || '',
    date_from: searchParams.get('date_from') || '',
    date_to: searchParams.get('date_to') || '',
  }
}

function buildParams(state: SearchFormState, page = 1) {
  const params = new URLSearchParams()
  if (state.q.trim()) params.set('q', state.q.trim())
  if (state.type !== 'all') params.set('type', state.type)
  if (state.student_id !== 'all') params.set('student_id', state.student_id)
  if (state.subject_id !== 'all') params.set('subject_id', state.subject_id)
  if (state.grading_period_id !== 'all') params.set('grading_period_id', state.grading_period_id)
  if (state.status.trim()) params.set('status', state.status.trim())
  if (state.date_from) params.set('date_from', state.date_from)
  if (state.date_to) params.set('date_to', state.date_to)
  params.set('page', String(page))
  params.set('page_size', '10')
  return params
}

function formatResultDate(value?: string | null) {
  return value ? new Date(value).toLocaleString() : '—'
}

export function SearchPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const [form, setForm] = useState<SearchFormState>(() => readQueryState(searchParams))
  const [results, setResults] = useState<SearchResult[]>([])
  const [facets, setFacets] = useState<Record<string, number>>({})
  const [students, setStudents] = useState<Student[]>([])
  const [subjects, setSubjects] = useState<Subject[]>([])
  const [gradingPeriods, setGradingPeriods] = useState<GradingPeriod[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [page, setPage] = useState(Number(searchParams.get('page') || '1'))
  const [totalPages, setTotalPages] = useState(0)
  const [total, setTotal] = useState(0)
  const [recentSearches, setRecentSearches] = useState<string[]>(() => getRecentSearches())

  const query = useMemo(() => readQueryState(searchParams), [searchParams])

  useEffect(() => {
    setForm(query)
    setPage(Number(searchParams.get('page') || '1'))
  }, [query, searchParams])

  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const schoolYears = await api.listSchoolYears()
      const schoolYearDetails = await Promise.all(schoolYears.map((year) => api.getSchoolYear(year.id)))
      const allGradingPeriods = schoolYearDetails.flatMap((year) => year.terms.flatMap((term) => term.grading_periods))
      const [response, studentData, subjectData] = await Promise.all([
        api.search({
          q: query.q || undefined,
          type: query.type === 'all' ? undefined : query.type,
          student_id: query.student_id === 'all' ? undefined : Number(query.student_id),
          subject_id: query.subject_id === 'all' ? undefined : Number(query.subject_id),
          grading_period_id: query.grading_period_id === 'all' ? undefined : Number(query.grading_period_id),
          status: query.status || undefined,
          date_from: query.date_from || undefined,
          date_to: query.date_to || undefined,
          page,
          page_size: 10,
        }),
        api.listStudents(),
        api.listSubjects(),
      ])
      setResults(response.items)
      setFacets(response.facets)
      setTotal(response.total)
      setTotalPages(response.total_pages)
      setStudents(studentData)
      setSubjects(subjectData)
      setGradingPeriods(allGradingPeriods)
      if (query.q) {
        storeRecentSearch(query.q)
        setRecentSearches(getRecentSearches())
      }
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : 'Unable to run search')
    } finally {
      setLoading(false)
    }
  }, [page, query])

  useEffect(() => {
    void load()
  }, [load])

  const applySearch = (nextPage = 1) => {
    setSearchParams(buildParams(form, nextPage))
  }

  if (loading) return <LoadingState message="Searching…" />
  if (error) return <ErrorState message={error} onRetry={() => void load()} />

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <CardTitle>Unified search</CardTitle>
          <CardDescription>Search assignments, grades, students, notes, curriculum, resources, and more from one place.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-4 xl:grid-cols-[2fr_repeat(5,minmax(0,1fr))]">
            <div className="space-y-2">
              <Label>Search</Label>
              <div className="flex gap-2">
                <Input
                  value={form.q}
                  onChange={(event) => setForm((current) => ({ ...current, q: event.target.value }))}
                  onKeyDown={(event) => {
                    if (event.key === 'Enter') applySearch()
                  }}
                  placeholder="Keyword, note, assignment, student…"
                />
                <Button onClick={() => applySearch()}>
                  <SearchIcon className="mr-2 h-4 w-4" />
                  Search
                </Button>
              </div>
            </div>
            <div className="space-y-2">
              <Label>Type</Label>
              <Select value={form.type} onValueChange={(value: SearchEntityType | 'all') => setForm((current) => ({ ...current, type: value }))}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All results</SelectItem>
                  {Object.entries(entityTypeLabels).map(([value, label]) => (
                    <SelectItem key={value} value={value}>
                      {label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label>Student</Label>
              <Select value={form.student_id} onValueChange={(value) => setForm((current) => ({ ...current, student_id: value }))}>
                <SelectTrigger>
                  <SelectValue />
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
              <Select value={form.subject_id} onValueChange={(value) => setForm((current) => ({ ...current, subject_id: value }))}>
                <SelectTrigger>
                  <SelectValue />
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
              <Select
                value={form.grading_period_id}
                onValueChange={(value) => setForm((current) => ({ ...current, grading_period_id: value }))}
              >
                <SelectTrigger>
                  <SelectValue />
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
              <Label>Status</Label>
              <Input value={form.status} onChange={(event) => setForm((current) => ({ ...current, status: event.target.value }))} placeholder="pending, graded, note…" />
            </div>
          </div>

          <div className="grid gap-4 md:grid-cols-2">
            <div className="space-y-2">
              <Label>From</Label>
              <Input type="date" value={form.date_from} onChange={(event) => setForm((current) => ({ ...current, date_from: event.target.value }))} />
            </div>
            <div className="space-y-2">
              <Label>To</Label>
              <Input type="date" value={form.date_to} onChange={(event) => setForm((current) => ({ ...current, date_to: event.target.value }))} />
            </div>
          </div>

          <div className="flex flex-wrap gap-2">
            <Button variant="outline" onClick={() => applySearch()}>
              Apply filters
            </Button>
            <Button
              variant="outline"
              onClick={() => {
                const cleared: SearchFormState = {
                  q: '',
                  type: 'all',
                  student_id: 'all',
                  subject_id: 'all',
                  grading_period_id: 'all',
                  status: '',
                  date_from: '',
                  date_to: '',
                }
                setForm(cleared)
                setSearchParams(buildParams(cleared))
              }}
            >
              Reset
            </Button>
            <p className="self-center text-sm text-muted-foreground">{total} matches</p>
          </div>

          {recentSearches.length ? (
            <div className="space-y-2">
              <Label>Recent searches</Label>
              <div className="flex flex-wrap gap-2">
                {recentSearches.map((item) => (
                  <Button
                    key={item}
                    variant="outline"
                    size="sm"
                    onClick={() => {
                      const next = { ...form, q: item }
                      setForm(next)
                      setSearchParams(buildParams(next))
                    }}
                  >
                    {item}
                  </Button>
                ))}
              </div>
            </div>
          ) : null}
        </CardContent>
      </Card>

      {Object.keys(facets).length ? (
        <div className="flex flex-wrap gap-2">
          <Button
            variant={query.type === 'all' ? 'default' : 'outline'}
            size="sm"
            onClick={() => {
              const next = { ...form, type: 'all' as const }
              setForm(next)
              setSearchParams(buildParams(next))
            }}
          >
            All ({total})
          </Button>
          {Object.entries(facets).map(([type, count]) => (
            <Button
              key={type}
              variant={query.type === type ? 'default' : 'outline'}
              size="sm"
              onClick={() => {
                const next = { ...form, type: type as SearchEntityType }
                setForm(next)
                setSearchParams(buildParams(next))
              }}
            >
              {entityTypeLabels[type as SearchEntityType] || type} ({count})
            </Button>
          ))}
        </div>
      ) : null}

      {results.length ? (
        <div className="space-y-3">
          {results.map((result) => (
            <Card key={`${result.entity_type}-${result.entity_id}`}>
              <CardContent className="space-y-3 p-4">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div className="space-y-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <h3 className="font-semibold">{result.title}</h3>
                      <Badge variant="secondary">{entityTypeLabels[result.entity_type]}</Badge>
                      {result.status ? <Badge variant="outline">{result.status}</Badge> : null}
                    </div>
                    <p className="text-sm text-muted-foreground">{result.snippet}</p>
                    <p className="text-xs text-muted-foreground">Updated {formatResultDate(result.created_at)}</p>
                  </div>
                  <Button asChild>
                    <Link to={result.link}>Open</Link>
                  </Button>
                </div>
              </CardContent>
            </Card>
          ))}
          <div className="flex items-center justify-between">
            <p className="text-sm text-muted-foreground">
              Page {page} of {Math.max(totalPages, 1)}
            </p>
            <div className="space-x-2">
              <Button variant="outline" disabled={page <= 1} onClick={() => applySearch(page - 1)}>
                Previous
              </Button>
              <Button variant="outline" disabled={totalPages > 0 ? page >= totalPages : true} onClick={() => applySearch(page + 1)}>
                Next
              </Button>
            </div>
          </div>
        </div>
      ) : (
        <EmptyState title="No matches found" description="Try a broader keyword or adjust the filters above." />
      )}
    </div>
  )
}
