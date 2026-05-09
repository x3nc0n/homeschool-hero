import { RefreshCcw } from 'lucide-react'
import { Link, useParams } from 'react-router-dom'
import { useDashboard } from '@/hooks/useDashboard'
import { EmptyState } from '@/components/common/EmptyState'
import { ErrorState } from '@/components/common/ErrorState'
import { LoadingState } from '@/components/common/LoadingState'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardAction, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'

function badgeVariant(status?: string | null): 'secondary' | 'outline' | 'destructive' {
  if (!status) return 'outline'
  if (['healthy', 'ahead', 'present', 'on_track', 'compliant', 'graded'].includes(status)) return 'secondary'
  if (['warning', 'not_recorded', 'assigned', 'submitted', 'degraded'].includes(status)) return 'outline'
  return 'destructive'
}

function formatPercent(value?: number | null) {
  return value == null ? '—' : `${value.toFixed(1)}%`
}

function formatTime(value: string) {
  const [hours, minutes] = value.split(':').map(Number)
  return new Date(2000, 0, 1, hours || 0, minutes || 0).toLocaleTimeString([], {
    hour: 'numeric',
    minute: '2-digit',
  })
}

export function StudentDetailPage() {
  const params = useParams()
  const studentId = Number(params.studentId)
  const { dashboard, loading, error, reload } = useDashboard(Number.isFinite(studentId) ? studentId : undefined)

  if (!Number.isFinite(studentId)) {
    return <ErrorState message="Invalid student selected." />
  }

  if (loading) return <LoadingState message="Loading student dashboard…" />
  if (error) return <ErrorState message={error} onRetry={() => void reload()} />
  if (!dashboard) return <ErrorState message="Student dashboard is unavailable." onRetry={() => void reload()} />

  const summary = dashboard.student_summaries.find((item) => item.student_id === studentId) || dashboard.student_summaries[0]

  if (!summary) {
    return <EmptyState title="Student not found" description="Try returning to the roster and opening a different student." />
  }

  const attendance = dashboard.attendance_today.find((item) => item.student_id === summary.student_id)

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <div>
            <CardTitle>{summary.student_name}</CardTitle>
            <CardDescription>Detailed dashboard view for this student.</CardDescription>
          </div>
          <CardAction className="flex items-center gap-2">
            <Button asChild size="sm" variant="outline">
              <Link to="/students">Back to students</Link>
            </Button>
            <Button size="sm" variant="outline" onClick={() => void reload()}>
              <RefreshCcw className="h-4 w-4" />
              Refresh
            </Button>
          </CardAction>
        </CardHeader>
      </Card>

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <Card size="sm">
          <CardHeader>
            <CardDescription>Current GPA</CardDescription>
            <CardTitle>{summary.current_gpa?.toFixed(2) ?? '—'}</CardTitle>
          </CardHeader>
        </Card>
        <Card size="sm">
          <CardHeader>
            <CardDescription>Attendance rate</CardDescription>
            <CardTitle>{formatPercent(summary.attendance_rate)}</CardTitle>
          </CardHeader>
        </Card>
        <Card size="sm">
          <CardHeader>
            <CardDescription>Assignments due soon</CardDescription>
            <CardTitle>{summary.assignments_due_count}</CardTitle>
          </CardHeader>
        </Card>
        <Card size="sm">
          <CardHeader>
            <CardDescription>Pacing / compliance</CardDescription>
            <div className="flex flex-wrap gap-2">
              <Badge variant={badgeVariant(summary.pacing_status)}>{summary.pacing_status?.replace('_', ' ') || 'No pacing target'}</Badge>
              <Badge variant={badgeVariant(summary.compliance_status)}>{summary.compliance_status?.replace('_', ' ') || 'No compliance alert'}</Badge>
            </div>
          </CardHeader>
        </Card>
      </div>

      <div className="grid gap-4 xl:grid-cols-[minmax(0,2fr)_minmax(320px,1fr)]">
        <div className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Today’s schedule</CardTitle>
              <CardDescription>Blocks on the calendar for today.</CardDescription>
            </CardHeader>
            <CardContent>
              {dashboard.today_schedule.length ? (
                <div className="space-y-3">
                  {dashboard.today_schedule.map((item) => (
                    <div key={`${item.schedule_id}-${item.start_time}-${item.subject_name}`} className="rounded-lg border p-3">
                      <p className="font-medium">{item.subject_name}</p>
                      <p className="text-sm text-muted-foreground">
                        {formatTime(item.start_time)} – {formatTime(item.end_time)}
                        {item.location ? ` · ${item.location}` : ''}
                      </p>
                    </div>
                  ))}
                </div>
              ) : (
                <EmptyState title="No schedule today" description="Scheduled blocks will show up here once they are added." />
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Upcoming assignments</CardTitle>
              <CardDescription>Due in the next week.</CardDescription>
            </CardHeader>
            <CardContent>
              {dashboard.upcoming_assignments.length ? (
                <div className="space-y-3">
                  {dashboard.upcoming_assignments.map((item) => (
                    <div key={item.assignment_id} className="rounded-lg border p-3">
                      <div className="flex flex-wrap items-center gap-2">
                        <p className="font-medium">{item.title}</p>
                        {item.subject_name ? <Badge variant="outline">{item.subject_name}</Badge> : null}
                      </div>
                      <p className="text-sm text-muted-foreground">
                        Due {new Date(item.due_date).toLocaleDateString()} · {item.days_until_due} day{item.days_until_due === 1 ? '' : 's'} left
                      </p>
                    </div>
                  ))}
                </div>
              ) : (
                <EmptyState title="No assignments due soon" description="Upcoming due dates will appear here." />
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Recent grades</CardTitle>
              <CardDescription>Latest scored submissions for this student.</CardDescription>
            </CardHeader>
            <CardContent>
              {dashboard.recent_grades.length ? (
                <div className="space-y-3">
                  {dashboard.recent_grades.map((item) => (
                    <div key={item.grade_id} className="rounded-lg border p-3">
                      <div className="flex flex-wrap items-center gap-2">
                        <p className="font-medium">{item.assignment_title}</p>
                        {item.subject_name ? <Badge variant="outline">{item.subject_name}</Badge> : null}
                      </div>
                      <p className="text-sm text-muted-foreground">
                        {item.score}/{item.max_score} · {item.percent.toFixed(1)}%
                        {item.letter_grade ? ` · ${item.letter_grade}` : ''}
                      </p>
                    </div>
                  ))}
                </div>
              ) : (
                <EmptyState title="No grades yet" description="Grades will appear here after work is scored." />
              )}
            </CardContent>
          </Card>
        </div>

        <div className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Attendance today</CardTitle>
              <CardDescription>Today’s attendance status for this student.</CardDescription>
            </CardHeader>
            <CardContent>
              {attendance ? (
                <div className="rounded-lg border p-3">
                  <div className="flex items-center justify-between gap-3">
                    <p className="font-medium">{attendance.student_name}</p>
                    <Badge variant={badgeVariant(attendance.status)}>{attendance.status.replace('_', ' ')}</Badge>
                  </div>
                  <p className="mt-2 text-sm text-muted-foreground">
                    {attendance.instructional_hours ? `${attendance.instructional_hours} hours logged` : 'No hours logged yet'}
                  </p>
                </div>
              ) : (
                <EmptyState title="No attendance recorded" description="Attendance will appear here once it is captured." />
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Pacing alerts</CardTitle>
              <CardDescription>Any units that are behind pace.</CardDescription>
            </CardHeader>
            <CardContent>
              {dashboard.pacing_alerts.length ? (
                <div className="space-y-3">
                  {dashboard.pacing_alerts.map((item) => (
                    <div key={item.pacing_target_id} className="rounded-lg border p-3">
                      <p className="font-medium">{item.unit_name}</p>
                      <p className="text-sm text-muted-foreground">
                        {item.package_name} · {item.remaining_lessons} lessons remaining
                      </p>
                    </div>
                  ))}
                </div>
              ) : (
                <EmptyState title="No pacing alerts" description="This student is not currently behind pace." />
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Compliance warnings</CardTitle>
              <CardDescription>Any warning or non-compliant items for this student.</CardDescription>
            </CardHeader>
            <CardContent>
              {dashboard.compliance_warnings.length ? (
                <div className="space-y-3">
                  {dashboard.compliance_warnings.map((item, index) => (
                    <div key={`${item.rule_name}-${index}`} className="rounded-lg border p-3">
                      <div className="flex items-center justify-between gap-3">
                        <p className="font-medium">{item.rule_name}</p>
                        <Badge variant={badgeVariant(item.status)}>{item.status.replace('_', ' ')}</Badge>
                      </div>
                      <p className="mt-2 text-sm text-muted-foreground">
                        {item.current_value}/{item.required_value} {item.threshold_unit}
                      </p>
                    </div>
                  ))}
                </div>
              ) : (
                <EmptyState title="No compliance warnings" description="There are no active compliance flags for this student." />
              )}
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  )
}
