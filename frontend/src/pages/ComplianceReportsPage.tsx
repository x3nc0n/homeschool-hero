import { useCallback, useEffect, useMemo, useState } from 'react'
import { Download, FileCheck2, FileText, RefreshCcw } from 'lucide-react'
import { api } from '@/lib/api'
import { useAuth } from '@/context/AuthContext'
import type {
  ComplianceReport,
  ComplianceReportSummary,
  ComplianceReportType,
  GradingPeriod,
  RequiredComplianceReport,
  SchoolYear,
  Student,
} from '@/types/api'
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

const reportTypeOptions: Array<{ value: ComplianceReportType; label: string; requiresPeriod?: boolean }> = [
  { value: 'annual_assessment', label: 'Annual assessment' },
  { value: 'quarterly_report', label: 'Quarterly progress report', requiresPeriod: true },
  { value: 'notice_of_intent', label: 'Notice of intent' },
  { value: 'attendance_log', label: 'Attendance log' },
  { value: 'portfolio_review', label: 'Portfolio review' },
]

function statusVariant(status: ComplianceReportSummary['status']) {
  if (status === 'final') return 'default'
  if (status === 'submitted') return 'secondary'
  return 'outline'
}

function pickActiveYear(years: SchoolYear[]) {
  return years.find((year) => year.is_active) || years[0] || null
}

function readArray<T>(value: unknown): T[] {
  return Array.isArray(value) ? (value as T[]) : []
}

function readObject(value: unknown): Record<string, unknown> {
  return value && typeof value === 'object' ? (value as Record<string, unknown>) : {}
}

function formatPercent(value: unknown) {
  if (value === null || value === undefined || value === '') return '—'
  const numeric = Number(value)
  return Number.isFinite(numeric) ? `${numeric.toFixed(1)}%` : String(value)
}

function formatNumber(value: unknown, digits = 2) {
  if (value === null || value === undefined || value === '') return '—'
  const numeric = Number(value)
  return Number.isFinite(numeric) ? numeric.toFixed(digits) : String(value)
}

function ReportPreview({ report }: { report: ComplianceReport }) {
  const data = readObject(report.data)

  if (report.report_type === 'annual_assessment') {
    const summary = readObject(data.summary)
    const grades = readArray<Record<string, unknown>>(data.subject_grades)
    const tests = readArray<Record<string, unknown>>(data.test_scores)
    const coverage = readObject(data.subject_coverage)
    return (
      <div className="space-y-4">
        <div className="grid gap-3 md:grid-cols-3">
          <div className="rounded-lg border p-3">
            <p className="text-sm text-muted-foreground">Overall average</p>
            <p className="text-2xl font-semibold">{formatPercent(summary.overall_percent)}</p>
          </div>
          <div className="rounded-lg border p-3">
            <p className="text-sm text-muted-foreground">Subjects</p>
            <p className="text-2xl font-semibold">{String(summary.subject_count || 0)}</p>
          </div>
          <div className="rounded-lg border p-3">
            <p className="text-sm text-muted-foreground">Assessments</p>
            <p className="text-2xl font-semibold">{String(summary.test_count || 0)}</p>
          </div>
        </div>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Subject</TableHead>
              <TableHead>Percent</TableHead>
              <TableHead>Letter</TableHead>
              <TableHead>GPA</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {grades.map((grade) => (
              <TableRow key={String(grade.subject_id)}>
                <TableCell>{String(grade.subject_name || 'Subject')}</TableCell>
                <TableCell>{formatPercent(grade.overall_percent)}</TableCell>
                <TableCell>{String(grade.letter_grade || '—')}</TableCell>
                <TableCell>{formatNumber(grade.gpa_points)}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
        <div className="space-y-2">
          <p className="text-sm font-medium">Assessment evidence</p>
          {tests.length ? (
            <div className="space-y-2">
              {tests.map((test, index) => (
                <div key={`${test.title}-${index}`} className="rounded-md border p-3 text-sm">
                  <p className="font-medium">{String(test.title || 'Assessment')}</p>
                  <p className="text-muted-foreground">
                    {String(test.subject_name || 'General')} · {String(test.date || '—')} · {formatPercent(test.percent)}
                  </p>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-sm text-muted-foreground">No assessments captured yet.</p>
          )}
        </div>
        <div className="rounded-lg border p-3 text-sm">
          <p className="font-medium">Subject coverage</p>
          <p className="mt-1 text-muted-foreground">
            {(readArray<string>(coverage.subjects).join(', ') || 'No subjects recorded') as string}
          </p>
          {readArray<string>(coverage.missing_subjects).length ? (
            <p className="mt-2 text-destructive">Missing: {readArray<string>(coverage.missing_subjects).join(', ')}</p>
          ) : null}
        </div>
      </div>
    )
  }

  if (report.report_type === 'quarterly_report') {
    const period = readObject(data.period)
    const grades = readArray<Record<string, unknown>>(data.subject_grades)
    const attendance = readObject(data.attendance_summary)
    return (
      <div className="space-y-4">
        <div className="rounded-lg border p-3">
          <p className="font-medium">
            {String(period.term_name || '')} {String(period.name || '')}
          </p>
          <p className="text-sm text-muted-foreground">
            {String(period.start_date || '—')} to {String(period.end_date || '—')}
          </p>
        </div>
        <div className="grid gap-3 md:grid-cols-3">
          <div className="rounded-lg border p-3">
            <p className="text-sm text-muted-foreground">Attendance rate</p>
            <p className="text-2xl font-semibold">{formatPercent(attendance.attendance_rate)}</p>
          </div>
          <div className="rounded-lg border p-3">
            <p className="text-sm text-muted-foreground">Recorded days</p>
            <p className="text-2xl font-semibold">{String(attendance.total_records || 0)}</p>
          </div>
          <div className="rounded-lg border p-3">
            <p className="text-sm text-muted-foreground">Instructional hours</p>
            <p className="text-2xl font-semibold">{formatNumber(attendance.total_hours)}</p>
          </div>
        </div>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Subject</TableHead>
              <TableHead>Percent</TableHead>
              <TableHead>Letter</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {grades.map((grade) => (
              <TableRow key={String(grade.subject_id)}>
                <TableCell>{String(grade.subject_name || 'Subject')}</TableCell>
                <TableCell>{formatPercent(grade.overall_percent)}</TableCell>
                <TableCell>{String(grade.letter_grade || '—')}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
    )
  }

  if (report.report_type === 'attendance_log') {
    const summary = readObject(data.summary)
    const records = readArray<Record<string, unknown>>(data.daily_records)
    return (
      <div className="space-y-4">
        <div className="grid gap-3 md:grid-cols-4">
          <div className="rounded-lg border p-3">
            <p className="text-sm text-muted-foreground">Recorded days</p>
            <p className="text-2xl font-semibold">{String(summary.total_records || 0)}</p>
          </div>
          <div className="rounded-lg border p-3">
            <p className="text-sm text-muted-foreground">Present</p>
            <p className="text-2xl font-semibold">{String(summary.present || 0)}</p>
          </div>
          <div className="rounded-lg border p-3">
            <p className="text-sm text-muted-foreground">Absent</p>
            <p className="text-2xl font-semibold">{String(summary.absent || 0)}</p>
          </div>
          <div className="rounded-lg border p-3">
            <p className="text-sm text-muted-foreground">Hours</p>
            <p className="text-2xl font-semibold">{formatNumber(summary.total_hours)}</p>
          </div>
        </div>
        <div className="max-h-[24rem] overflow-auto rounded-lg border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Date</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Hours</TableHead>
                <TableHead>Notes</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {records.map((record, index) => (
                <TableRow key={`${record.date}-${index}`}>
                  <TableCell>{String(record.date || '—')}</TableCell>
                  <TableCell>{String(record.status || '—')}</TableCell>
                  <TableCell>{formatNumber(record.instructional_hours)}</TableCell>
                  <TableCell>{String(record.notes || '—')}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      </div>
    )
  }

  if (report.report_type === 'portfolio_review') {
    const summary = readObject(data.summary)
    const entries = readArray<Record<string, unknown>>(data.entries)
    const counts = readObject(summary.counts_by_type)
    return (
      <div className="space-y-4">
        <div className="rounded-lg border p-3">
          <p className="font-medium">Portfolio counts</p>
          <div className="mt-2 flex flex-wrap gap-2">
            {Object.entries(counts).map(([key, value]) => (
              <Badge key={key} variant="outline">
                {key.replaceAll('_', ' ')}: {String(value)}
              </Badge>
            ))}
          </div>
        </div>
        <div className="space-y-2">
          {entries.map((entry) => (
            <div key={String(entry.id)} className="rounded-md border p-3 text-sm">
              <p className="font-medium">{String(entry.title || 'Entry')}</p>
              <p className="text-muted-foreground">
                {String(entry.date || '—')} · {String(entry.entry_type || '—')} · {String(entry.subject_name || 'No subject')}
              </p>
            </div>
          ))}
        </div>
      </div>
    )
  }

  const template = readObject(data.template)
  return (
    <div className="space-y-3">
      <div className="rounded-lg border p-3">
        <p className="font-medium">{String(template.title || 'Notice of intent')}</p>
        <p className="mt-1 text-sm text-muted-foreground">
          Generated {String(template.generated_on || '—')} · State {String(template.state_code || '—')}
        </p>
      </div>
      {readArray<string>(template.body).map((paragraph, index) => (
        <p key={index} className="text-sm text-muted-foreground">
          {paragraph}
        </p>
      ))}
      {readArray<string>(template.subjects).length ? (
        <p className="text-sm">
          <span className="font-medium">Subjects:</span> {readArray<string>(template.subjects).join(', ')}
        </p>
      ) : null}
    </div>
  )
}

export function ComplianceReportsPage() {
  const { canManageGrading, studentId } = useAuth()
  const [students, setStudents] = useState<Student[]>([])
  const [schoolYears, setSchoolYears] = useState<SchoolYear[]>([])
  const [periods, setPeriods] = useState<GradingPeriod[]>([])
  const [stateCode, setStateCode] = useState('CUSTOM')
  const [requiredReports, setRequiredReports] = useState<RequiredComplianceReport[]>([])
  const [reports, setReports] = useState<ComplianceReportSummary[]>([])
  const [selectedStudentId, setSelectedStudentId] = useState<number | null>(null)
  const [selectedYearId, setSelectedYearId] = useState<number | null>(null)
  const [selectedPeriodId, setSelectedPeriodId] = useState<number | null>(null)
  const [selectedType, setSelectedType] = useState<ComplianceReportType>('annual_assessment')
  const [selectedReportId, setSelectedReportId] = useState<number | null>(null)
  const [selectedReport, setSelectedReport] = useState<ComplianceReport | null>(null)
  const [notesDraft, setNotesDraft] = useState('')
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [statusMessage, setStatusMessage] = useState('')

  const selectedTypeConfig = useMemo(
    () => reportTypeOptions.find((option) => option.value === selectedType) || reportTypeOptions[0],
    [selectedType],
  )

  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const [studentData, schoolYearData, familyState] = await Promise.all([
        api.listStudents(),
        api.listSchoolYears(),
        api.getFamilyComplianceState(),
      ])
      const resolvedStudentId =
        studentId && studentData.some((student) => student.id === studentId)
          ? studentId
          : selectedStudentId && studentData.some((student) => student.id === selectedStudentId)
            ? selectedStudentId
            : studentData[0]?.id || null
      const resolvedYearId =
        selectedYearId && schoolYearData.some((year) => year.id === selectedYearId)
          ? selectedYearId
          : pickActiveYear(schoolYearData)?.id || null

      setStudents(studentData)
      setSchoolYears(schoolYearData)
      setStateCode(familyState.state_code)
      setSelectedStudentId(resolvedStudentId)
      setSelectedYearId(resolvedYearId)

      if (!resolvedYearId) {
        setPeriods([])
        setRequiredReports([])
        setReports([])
        setSelectedReport(null)
        setSelectedReportId(null)
        return
      }

      const schoolYearDetail = await api.getSchoolYear(resolvedYearId)
      const periodData = schoolYearDetail.terms.flatMap((term) =>
        term.grading_periods.map((period) => ({ ...period, name: `${term.name} · ${period.name}` })),
      )
      const nextPeriodId =
        selectedPeriodId && periodData.some((period) => period.id === selectedPeriodId) ? selectedPeriodId : periodData[0]?.id || null
      setPeriods(periodData)
      setSelectedPeriodId(nextPeriodId)

      const [required, reportData] = await Promise.all([
        api.listRequiredComplianceReports({
          state: familyState.state_code,
          student_id: resolvedStudentId || undefined,
          school_year_id: resolvedYearId,
        }),
        api.listComplianceReports({
          student_id: resolvedStudentId || undefined,
          school_year_id: resolvedYearId,
        }),
      ])
      setRequiredReports(required.items)
      setReports(reportData)

      const nextReportId =
        selectedReportId && reportData.some((report) => report.id === selectedReportId) ? selectedReportId : reportData[0]?.id || null
      setSelectedReportId(nextReportId)
      if (nextReportId) {
        const detail = await api.getComplianceReport(nextReportId)
        setSelectedReport(detail)
      } else {
        setSelectedReport(null)
      }
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : 'Unable to load compliance reports')
    } finally {
      setLoading(false)
    }
  }, [selectedPeriodId, selectedReportId, selectedStudentId, selectedYearId, studentId])

  useEffect(() => {
    void load()
  }, [load])

  useEffect(() => {
    setNotesDraft(selectedReport?.notes || '')
  }, [selectedReport])

  const outstandingCount = useMemo(
    () => requiredReports.reduce((total, item) => total + item.outstanding_count, 0),
    [requiredReports],
  )

  const refreshSelectedReport = async (reportId: number | null) => {
    if (!reportId) {
      setSelectedReport(null)
      return
    }
    const detail = await api.getComplianceReport(reportId)
    setSelectedReport(detail)
  }

  const generateReport = async () => {
    if (!selectedStudentId || !selectedYearId) return
    setSaving(true)
    setError('')
    setStatusMessage('')
    try {
      const created = await api.generateComplianceReport({
        student_id: selectedStudentId,
        school_year_id: selectedYearId,
        report_type: selectedType,
        grading_period_id: selectedTypeConfig.requiresPeriod ? selectedPeriodId : undefined,
        notes: notesDraft || undefined,
      })
      setSelectedReport(created)
      setSelectedReportId(created.id)
      setStatusMessage('Draft compliance report generated.')
      await load()
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : 'Unable to generate compliance report')
    } finally {
      setSaving(false)
    }
  }

  const finalizeReport = async () => {
    if (!selectedReport) return
    setSaving(true)
    setError('')
    setStatusMessage('')
    try {
      const finalized = await api.finalizeComplianceReport(selectedReport.id)
      setSelectedReport(finalized)
      setStatusMessage('Compliance report finalized.')
      await load()
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : 'Unable to finalize compliance report')
    } finally {
      setSaving(false)
    }
  }

  const visibleReports = useMemo(() => reports, [reports])

  const downloadPdf = (id: number) => {
    window.open(api.getComplianceReportPdfUrl(id), '_blank', 'noopener,noreferrer')
  }

  if (loading) return <LoadingState message="Loading compliance reports…" />
  if (error && !students.length) return <ErrorState message={error} onRetry={() => void load()} />
  if (!students.length) return <EmptyState title="No students yet" description="Add a student before generating compliance reports." />

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <CardTitle>Compliance reports</CardTitle>
          <CardDescription>
            Generate state-ready attendance, assessment, portfolio, quarterly, and notice reports for {stateCode}.
          </CardDescription>
        </CardHeader>
        <CardContent className="grid gap-4 lg:grid-cols-5">
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
          <div className="space-y-2">
            <Label>School year</Label>
            <Select value={selectedYearId ? String(selectedYearId) : ''} onValueChange={(value) => setSelectedYearId(Number(value))}>
              <SelectTrigger>
                <SelectValue placeholder="Choose a school year" />
              </SelectTrigger>
              <SelectContent>
                {schoolYears.map((year) => (
                  <SelectItem key={year.id} value={String(year.id)}>
                    {year.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-2">
            <Label>Report type</Label>
            <Select value={selectedType} onValueChange={(value) => setSelectedType(value as ComplianceReportType)}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {reportTypeOptions.map((option) => (
                  <SelectItem key={option.value} value={option.value}>
                    {option.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-2">
            <Label>{selectedTypeConfig.requiresPeriod ? 'Quarter / period' : 'Notes for new report'}</Label>
            {selectedTypeConfig.requiresPeriod ? (
              <Select value={selectedPeriodId ? String(selectedPeriodId) : ''} onValueChange={(value) => setSelectedPeriodId(Number(value))}>
                <SelectTrigger>
                  <SelectValue placeholder="Choose a grading period" />
                </SelectTrigger>
                <SelectContent>
                  {periods.map((period) => (
                    <SelectItem key={period.id} value={String(period.id)}>
                      {period.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            ) : (
              <Textarea value={notesDraft} onChange={(event) => setNotesDraft(event.target.value)} rows={2} />
            )}
          </div>
          <div className="flex items-end gap-2">
            {canManageGrading ? (
              <Button
                onClick={() => void generateReport()}
                disabled={saving || !selectedStudentId || !selectedYearId || (selectedTypeConfig.requiresPeriod && !selectedPeriodId)}
              >
                <FileText className="mr-2 h-4 w-4" />
                Generate
              </Button>
            ) : null}
            <Button variant="outline" onClick={() => void load()} disabled={saving}>
              <RefreshCcw className="mr-2 h-4 w-4" />
              Refresh
            </Button>
          </div>
        </CardContent>
      </Card>

      <div className="grid gap-4 xl:grid-cols-[1fr,1fr,1.5fr]">
        <Card>
          <CardHeader>
            <CardTitle>Required checklist</CardTitle>
            <CardDescription>
              {requiredReports.length - outstandingCount} complete items · {outstandingCount} outstanding obligations
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            {requiredReports.map((item) => (
              <div key={item.report_type} className="rounded-lg border p-3">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <p className="font-medium">{item.label}</p>
                  <Badge variant={item.is_complete ? 'secondary' : 'outline'}>
                    {item.completed_count}/{item.required_count} complete
                  </Badge>
                </div>
                <p className="mt-1 text-sm text-muted-foreground">{item.description}</p>
                <p className="mt-2 text-xs text-muted-foreground">
                  Generated {item.generated_count} · Outstanding {item.outstanding_count}
                </p>
              </div>
            ))}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Generated reports</CardTitle>
            <CardDescription>Drafts and finalized reports for the selected student and year.</CardDescription>
          </CardHeader>
          <CardContent>
            {visibleReports.length ? (
              <div className="space-y-3">
                {visibleReports.map((report) => (
                  <button
                    key={report.id}
                    type="button"
                    className={`w-full rounded-lg border p-4 text-left transition hover:bg-muted/50 ${
                      selectedReportId === report.id ? 'border-primary bg-primary/5' : ''
                    }`}
                    onClick={() => {
                      setSelectedReportId(report.id)
                      void refreshSelectedReport(report.id)
                    }}
                  >
                    <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
                      <div>
                        <p className="font-semibold">{report.title}</p>
                        <p className="text-sm text-muted-foreground">
                          {report.student_name} · {new Date(report.generated_at).toLocaleString()}
                        </p>
                      </div>
                      <Badge variant={statusVariant(report.status)}>{report.status}</Badge>
                    </div>
                    <p className="text-sm text-muted-foreground">
                      {report.period_label || report.school_year_name} · {report.state_code}
                    </p>
                  </button>
                ))}
              </div>
            ) : (
              <EmptyState title="No reports yet" description="Generate a report to preview it here before finalizing." />
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <CardTitle>Preview</CardTitle>
                <CardDescription>
                  {selectedReport ? `${selectedReport.student_name} · ${selectedReport.title}` : 'Select a report to preview its contents.'}
                </CardDescription>
              </div>
              {selectedReport ? (
                <div className="flex flex-wrap gap-2">
                  <Badge variant={statusVariant(selectedReport.status)}>{selectedReport.status}</Badge>
                  <Button variant="outline" onClick={() => downloadPdf(selectedReport.id)}>
                    <Download className="mr-2 h-4 w-4" />
                    PDF
                  </Button>
                  {canManageGrading && selectedReport.status === 'draft' ? (
                    <Button onClick={() => void finalizeReport()} disabled={saving}>
                      <FileCheck2 className="mr-2 h-4 w-4" />
                      Finalize
                    </Button>
                  ) : null}
                </div>
              ) : null}
            </div>
          </CardHeader>
          <CardContent className="space-y-4">
            {selectedReport ? <ReportPreview report={selectedReport} /> : <p className="text-sm text-muted-foreground">Choose a report to preview it.</p>}
            {selectedReport?.notes ? (
              <div className="rounded-lg border p-3 text-sm">
                <p className="font-medium">Notes</p>
                <p className="mt-1 text-muted-foreground">{selectedReport.notes}</p>
              </div>
            ) : null}
            {statusMessage ? <p className="text-sm text-emerald-600">{statusMessage}</p> : null}
            {error ? <p className="text-sm text-destructive">{error}</p> : null}
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
