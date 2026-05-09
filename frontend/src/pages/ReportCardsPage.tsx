import { useCallback, useEffect, useMemo, useState } from 'react'
import { Download, FileText, RefreshCcw } from 'lucide-react'
import { api } from '@/lib/api'
import { useAuth } from '@/context/AuthContext'
import type { AttendanceSummary, GradebookView, GradingPeriod, ReportCard, ReportCardSummary, Student } from '@/types/api'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { EmptyState } from '@/components/common/EmptyState'
import { ErrorState } from '@/components/common/ErrorState'
import { LoadingState } from '@/components/common/LoadingState'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Textarea } from '@/components/ui/textarea'

type GradingPeriodOption = GradingPeriod & {
  school_year_id: number
  school_year_name: string
  term_name: string
}

function statusVariant(status: ReportCardSummary['status']) {
  if (status === 'final') return 'default'
  if (status === 'archived') return 'secondary'
  return 'outline'
}

function formatPercent(value?: number | null) {
  return value === null || value === undefined ? '—' : `${value.toFixed(1)}%`
}

function formatGpa(value?: number | null) {
  return value === null || value === undefined ? '—' : value.toFixed(2)
}

function pickCurrentPeriod(periods: GradingPeriodOption[]) {
  const today = new Date().toISOString().slice(0, 10)
  return periods.find((period) => period.start_date <= today && period.end_date >= today) || periods[0] || null
}

export function ReportCardsPage() {
  const { canManageGrading, role, studentId } = useAuth()
  const [students, setStudents] = useState<Student[]>([])
  const [periods, setPeriods] = useState<GradingPeriodOption[]>([])
  const [reportCards, setReportCards] = useState<ReportCardSummary[]>([])
  const [selectedStudentId, setSelectedStudentId] = useState<number | null>(null)
  const [selectedPeriodId, setSelectedPeriodId] = useState<number | null>(null)
  const [selectedReportCardId, setSelectedReportCardId] = useState<number | null>(null)
  const [reportCard, setReportCard] = useState<ReportCard | null>(null)
  const [progressReport, setProgressReport] = useState<GradebookView | null>(null)
  const [progressAttendance, setProgressAttendance] = useState<AttendanceSummary | null>(null)
  const [notesDraft, setNotesDraft] = useState('')
  const [commentDrafts, setCommentDrafts] = useState<Record<number, string>>({})
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [statusMessage, setStatusMessage] = useState('')

  const selectedPeriod = useMemo(
    () => periods.find((period) => period.id === selectedPeriodId) || null,
    [periods, selectedPeriodId],
  )

  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const [studentData, schoolYears] = await Promise.all([api.listStudents(), api.listSchoolYears()])
      const schoolYearDetails = await Promise.all(schoolYears.map((year) => api.getSchoolYear(year.id)))
      const allPeriods = schoolYearDetails.flatMap((schoolYear) =>
        schoolYear.terms.flatMap((term) =>
          term.grading_periods.map((period) => ({
            ...period,
            school_year_id: schoolYear.id,
            school_year_name: schoolYear.name,
            term_name: term.name,
          })),
        ),
      )
      const resolvedStudentId =
        studentId && studentData.some((student) => student.id === studentId)
          ? studentId
          : selectedStudentId && studentData.some((student) => student.id === selectedStudentId)
            ? selectedStudentId
            : studentData[0]?.id || null
      const resolvedPeriodId =
        selectedPeriodId && allPeriods.some((period) => period.id === selectedPeriodId)
          ? selectedPeriodId
          : pickCurrentPeriod(allPeriods)?.id || null

      setStudents(studentData)
      setPeriods(allPeriods)
      setSelectedStudentId(resolvedStudentId)
      setSelectedPeriodId(resolvedPeriodId)

      if (!resolvedStudentId) {
        setReportCards([])
        setReportCard(null)
        setProgressReport(null)
        setProgressAttendance(null)
        setSelectedReportCardId(null)
        return
      }

      const [cards, gradebook, attendance] = await Promise.all([
        api.listReportCards({ student_id: resolvedStudentId }),
        resolvedPeriodId ? api.getGradebook(resolvedStudentId, { grading_period_id: resolvedPeriodId }) : Promise.resolve(null),
        resolvedPeriodId
          ? api.getAttendanceSummary(resolvedStudentId, 'term', allPeriods.find((period) => period.id === resolvedPeriodId)?.school_year_id)
          : Promise.resolve(null),
      ])
      setReportCards(cards)
      setProgressReport(gradebook)
      setProgressAttendance(attendance)

      const scopedCards = resolvedPeriodId ? cards.filter((card) => card.grading_period_id === resolvedPeriodId) : cards
      const nextSelectedId =
        selectedReportCardId && scopedCards.some((card) => card.id === selectedReportCardId)
          ? selectedReportCardId
          : scopedCards[0]?.id || null
      setSelectedReportCardId(nextSelectedId)
      if (nextSelectedId) {
        const detail = await api.getReportCard(nextSelectedId)
        setReportCard(detail)
      } else {
        setReportCard(null)
      }
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : 'Unable to load report cards')
    } finally {
      setLoading(false)
    }
  }, [selectedPeriodId, selectedReportCardId, selectedStudentId, studentId])

  const loadSelectedReportCard = useCallback(async (reportCardId: number | null) => {
    if (!reportCardId) {
      setReportCard(null)
      return
    }
    const detail = await api.getReportCard(reportCardId)
    setReportCard(detail)
  }, [])

  useEffect(() => {
    void load()
  }, [load])

  useEffect(() => {
    if (!reportCard) {
      setNotesDraft('')
      setCommentDrafts({})
      return
    }
    setNotesDraft(reportCard.notes || '')
    setCommentDrafts(
      reportCard.entries.reduce<Record<number, string>>((accumulator, entry) => {
        accumulator[entry.id] = entry.teacher_comments || ''
        return accumulator
      }, {}),
    )
  }, [reportCard])

  const visibleCards = useMemo(
    () =>
      reportCards.filter((card) => {
        if (selectedPeriodId && card.grading_period_id !== selectedPeriodId) return false
        return true
      }),
    [reportCards, selectedPeriodId],
  )

  const canEditDraft = canManageGrading && reportCard?.status === 'draft'

  const refreshData = async () => {
    await load()
    if (selectedReportCardId) {
      await loadSelectedReportCard(selectedReportCardId)
    }
  }

  const generate = async () => {
    if (!selectedStudentId || !selectedPeriodId) return
    setSaving(true)
    setStatusMessage('')
    setError('')
    try {
      const generated = await api.generateReportCard({ student_id: selectedStudentId, grading_period_id: selectedPeriodId })
      setSelectedReportCardId(generated.id)
      setReportCard(generated)
      setStatusMessage('Draft report card generated.')
      await load()
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : 'Unable to generate report card')
    } finally {
      setSaving(false)
    }
  }

  const saveDraft = async () => {
    if (!reportCard) return
    setSaving(true)
    setStatusMessage('')
    setError('')
    try {
      const updated = await api.updateReportCard(reportCard.id, {
        notes: notesDraft,
        entries: reportCard.entries.map((entry) => ({
          entry_id: entry.id,
          teacher_comments: commentDrafts[entry.id] || '',
        })),
      })
      setReportCard(updated)
      setStatusMessage('Draft saved.')
      await load()
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : 'Unable to save report card')
    } finally {
      setSaving(false)
    }
  }

  const finalize = async () => {
    if (!reportCard) return
    setSaving(true)
    setStatusMessage('')
    setError('')
    try {
      const finalized = await api.finalizeReportCard(reportCard.id)
      setReportCard(finalized)
      setStatusMessage('Report card finalized.')
      await load()
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : 'Unable to finalize report card')
    } finally {
      setSaving(false)
    }
  }

  const downloadPdf = (id: number) => {
    window.open(api.getReportCardPdfUrl(id), '_blank', 'noopener,noreferrer')
  }

  if (loading) return <LoadingState message="Loading report cards…" />
  if (error && !students.length) return <ErrorState message={error} onRetry={() => void load()} />
  if (!students.length) return <EmptyState title="No students yet" description="Add a student before generating report cards." />

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <CardTitle>Report cards</CardTitle>
          <CardDescription>Generate grading-period report cards, edit draft comments, and export clean PDFs.</CardDescription>
        </CardHeader>
        <CardContent className="grid gap-4 lg:grid-cols-4">
          <div className="space-y-2">
            <Label>Student</Label>
            <Select value={selectedStudentId ? String(selectedStudentId) : ''} onValueChange={(value) => setSelectedStudentId(Number(value))}>
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
          <div className="space-y-2 lg:col-span-2">
            <Label>Grading period</Label>
            <Select value={selectedPeriodId ? String(selectedPeriodId) : ''} onValueChange={(value) => setSelectedPeriodId(Number(value))}>
              <SelectTrigger>
                <SelectValue placeholder="Choose a grading period" />
              </SelectTrigger>
              <SelectContent>
                {periods.map((period) => (
                  <SelectItem key={period.id} value={String(period.id)}>
                    {period.school_year_name} · {period.term_name} · {period.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="flex items-end gap-2">
            {canManageGrading ? (
              <Button onClick={() => void generate()} disabled={saving || !selectedStudentId || !selectedPeriodId}>
                <FileText className="mr-2 h-4 w-4" />
                Generate
              </Button>
            ) : null}
            <Button variant="outline" onClick={() => void refreshData()} disabled={saving}>
              <RefreshCcw className="mr-2 h-4 w-4" />
              Refresh
            </Button>
          </div>
        </CardContent>
      </Card>

      <div className="grid gap-4 xl:grid-cols-[1.1fr,1.5fr]">
        <Card>
          <CardHeader>
            <CardTitle>Generated report cards</CardTitle>
            <CardDescription>{selectedStudentId ? 'Filtered for the selected student and period.' : 'Choose a student to begin.'}</CardDescription>
          </CardHeader>
          <CardContent>
            {visibleCards.length ? (
              <div className="space-y-3">
                {visibleCards.map((card) => (
                  <button
                    key={card.id}
                    type="button"
                    className={`w-full rounded-lg border p-4 text-left transition hover:bg-muted/50 ${
                      selectedReportCardId === card.id ? 'border-primary bg-primary/5' : ''
                    }`}
                    onClick={() => {
                      setSelectedReportCardId(card.id)
                      void loadSelectedReportCard(card.id)
                    }}
                  >
                    <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
                      <div>
                        <p className="font-semibold">{card.grading_period_name}</p>
                        <p className="text-sm text-muted-foreground">
                          {card.school_year_name} · {new Date(card.generated_at).toLocaleString()}
                        </p>
                      </div>
                      <Badge variant={statusVariant(card.status)}>{card.status}</Badge>
                    </div>
                    <div className="flex flex-wrap gap-4 text-sm text-muted-foreground">
                      <span>GPA {formatGpa(card.gpa)}</span>
                      <span>Average {formatPercent(card.overall_percentage)}</span>
                      <span>{card.entry_count} subjects</span>
                    </div>
                  </button>
                ))}
              </div>
            ) : (
              <EmptyState
                title="No report cards yet"
                description={canManageGrading ? 'Generate a draft for the selected grading period.' : 'No report cards are available yet.'}
              />
            )}
          </CardContent>
        </Card>

        <div className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Progress report snapshot</CardTitle>
              <CardDescription>
                Live grades and attendance for {selectedPeriod ? `${selectedPeriod.term_name} · ${selectedPeriod.name}` : 'the selected period'}.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {progressReport?.subjects.length ? (
                <>
                  <div className="grid gap-3 md:grid-cols-3">
                    <div className="rounded-lg border p-3">
                      <p className="text-sm text-muted-foreground">Current GPA</p>
                      <p className="text-2xl font-semibold">{formatGpa(progressReport.gpa)}</p>
                    </div>
                    <div className="rounded-lg border p-3">
                      <p className="text-sm text-muted-foreground">Attendance rate</p>
                      <p className="text-2xl font-semibold">{progressAttendance ? `${progressAttendance.attendance_rate.toFixed(1)}%` : '—'}</p>
                    </div>
                    <div className="rounded-lg border p-3">
                      <p className="text-sm text-muted-foreground">Instructional hours</p>
                      <p className="text-2xl font-semibold">{progressAttendance?.total_hours || '—'}</p>
                    </div>
                  </div>
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Subject</TableHead>
                        <TableHead>Grade</TableHead>
                        <TableHead>Percent</TableHead>
                        <TableHead>GPA</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {progressReport.subjects.map((subject) => (
                        <TableRow key={subject.subject_id}>
                          <TableCell>{subject.subject_name}</TableCell>
                          <TableCell>{subject.letter_grade || '—'}</TableCell>
                          <TableCell>{formatPercent(subject.overall_percent)}</TableCell>
                          <TableCell>{formatGpa(subject.gpa_points)}</TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </>
              ) : (
                <p className="text-sm text-muted-foreground">No graded work is available for the selected period yet.</p>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <CardTitle>Report card detail</CardTitle>
                  <CardDescription>
                    {reportCard ? `${reportCard.student_name} · ${reportCard.school_year_name} · ${reportCard.grading_period_name}` : 'Select a report card to review.'}
                  </CardDescription>
                </div>
                {reportCard ? (
                  <div className="flex flex-wrap gap-2">
                    <Badge variant={statusVariant(reportCard.status)}>{reportCard.status}</Badge>
                    <Button variant="outline" onClick={() => downloadPdf(reportCard.id)}>
                      <Download className="mr-2 h-4 w-4" />
                      PDF
                    </Button>
                    {canEditDraft ? (
                      <>
                        <Button variant="outline" onClick={() => void saveDraft()} disabled={saving}>
                          Save draft
                        </Button>
                        <Button onClick={() => void finalize()} disabled={saving}>
                          Finalize
                        </Button>
                      </>
                    ) : null}
                  </div>
                ) : null}
              </div>
            </CardHeader>
            <CardContent className="space-y-4">
              {reportCard ? (
                <>
                  <div className="grid gap-3 md:grid-cols-4">
                    <div className="rounded-lg border p-3">
                      <p className="text-sm text-muted-foreground">Generated</p>
                      <p className="font-medium">{new Date(reportCard.generated_at).toLocaleString()}</p>
                    </div>
                    <div className="rounded-lg border p-3">
                      <p className="text-sm text-muted-foreground">GPA</p>
                      <p className="font-medium">{formatGpa(reportCard.gpa)}</p>
                    </div>
                    <div className="rounded-lg border p-3">
                      <p className="text-sm text-muted-foreground">Average</p>
                      <p className="font-medium">{formatPercent(reportCard.overall_percentage)}</p>
                    </div>
                    <div className="rounded-lg border p-3">
                      <p className="text-sm text-muted-foreground">Generated by</p>
                      <p className="font-medium">{reportCard.generated_by_name || role || '—'}</p>
                    </div>
                  </div>

                  <div className="space-y-2">
                    <Label>Report notes</Label>
                    <Textarea value={notesDraft} onChange={(event) => setNotesDraft(event.target.value)} readOnly={!canEditDraft} rows={3} />
                  </div>

                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Subject</TableHead>
                        <TableHead>Grade</TableHead>
                        <TableHead>Percent</TableHead>
                        <TableHead>GPA</TableHead>
                        <TableHead>Attendance</TableHead>
                        <TableHead>Categories</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {reportCard.entries.map((entry) => (
                        <TableRow key={entry.id}>
                          <TableCell>{entry.subject?.name || `Subject ${entry.subject_id}`}</TableCell>
                          <TableCell>{entry.letter_grade || '—'}</TableCell>
                          <TableCell>{formatPercent(entry.percentage)}</TableCell>
                          <TableCell>{formatGpa(entry.gpa_points)}</TableCell>
                          <TableCell>
                            {entry.attendance_summary.attendance_rate.toFixed(1)}% · {entry.attendance_summary.present}P/{entry.attendance_summary.absent}A
                          </TableCell>
                          <TableCell>
                            {Object.entries(entry.category_breakdown).length
                              ? Object.entries(entry.category_breakdown)
                                  .map(([name, value]) => `${name.replace('_', ' ')} ${value.toFixed(1)}%`)
                                  .join(', ')
                              : '—'}
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>

                  <div className="grid gap-4">
                    {reportCard.entries.map((entry) => (
                      <div key={entry.id} className="space-y-2 rounded-lg border p-4">
                        <div className="flex flex-wrap items-center justify-between gap-2">
                          <div>
                            <p className="font-medium">{entry.subject?.name || `Subject ${entry.subject_id}`}</p>
                            <p className="text-sm text-muted-foreground">
                              {entry.attendance_summary.total_records} attendance records · {entry.attendance_summary.total_hours.toFixed(2)} hours
                            </p>
                          </div>
                          <Badge variant="outline">{entry.letter_grade || 'In progress'}</Badge>
                        </div>
                        <Textarea
                          value={commentDrafts[entry.id] || ''}
                          onChange={(event) => setCommentDrafts((current) => ({ ...current, [entry.id]: event.target.value }))}
                          readOnly={!canEditDraft}
                          rows={3}
                        />
                      </div>
                    ))}
                  </div>
                </>
              ) : (
                <p className="text-sm text-muted-foreground">Choose a generated report card to see grades, attendance, and comments.</p>
              )}

              {statusMessage ? <p className="text-sm text-emerald-600">{statusMessage}</p> : null}
              {error ? <p className="text-sm text-destructive">{error}</p> : null}
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  )
}
