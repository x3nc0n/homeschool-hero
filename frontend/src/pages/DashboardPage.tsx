import { useState } from 'react'
import {
  Activity,
  ChevronDown,
  ChevronUp,
  RefreshCcw,
} from 'lucide-react'
import { Link } from 'react-router-dom'
import { useAuth } from '@/context/AuthContext'
import { useDashboard } from '@/hooks/useDashboard'
import type { DashboardStudentSummary } from '@/types/api'
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

function formatTime(value: string) {
  const [hours, minutes] = value.split(':').map(Number)
  return new Date(2000, 0, 1, hours || 0, minutes || 0).toLocaleTimeString([], {
    hour: 'numeric',
    minute: '2-digit',
  })
}

function formatPercent(value?: number | null) {
  return value == null ? '—' : `${value.toFixed(1)}%`
}

function WidgetCard({
  title,
  description,
  sectionKey,
  collapsed,
  onToggle,
  children,
}: {
  title: string
  description: string
  sectionKey: string
  collapsed: Record<string, boolean>
  onToggle: (key: string) => void
  children: React.ReactNode
}) {
  const isCollapsed = Boolean(collapsed[sectionKey])

  return (
    <Card>
      <CardHeader>
        <div>
          <CardTitle>{title}</CardTitle>
          <CardDescription>{description}</CardDescription>
        </div>
        <CardAction>
          <Button size="sm" variant="ghost" onClick={() => onToggle(sectionKey)}>
            {isCollapsed ? <ChevronDown className="h-4 w-4" /> : <ChevronUp className="h-4 w-4" />}
            {isCollapsed ? 'Show' : 'Hide'}
          </Button>
        </CardAction>
      </CardHeader>
      {!isCollapsed ? <CardContent>{children}</CardContent> : null}
    </Card>
  )
}

function StudentSummaryCard({ summary }: { summary: DashboardStudentSummary }) {
  return (
    <Card size="sm">
      <CardHeader>
        <CardTitle>{summary.student_name}</CardTitle>
        <CardDescription>Student summary</CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="grid grid-cols-2 gap-3">
          <div className="rounded-lg border p-3">
            <p className="text-xs uppercase text-muted-foreground">GPA</p>
            <p className="text-lg font-semibold">{summary.current_gpa?.toFixed(2) ?? '—'}</p>
          </div>
          <div className="rounded-lg border p-3">
            <p className="text-xs uppercase text-muted-foreground">Attendance</p>
            <p className="text-lg font-semibold">{formatPercent(summary.attendance_rate)}</p>
          </div>
          <div className="rounded-lg border p-3">
            <p className="text-xs uppercase text-muted-foreground">Due soon</p>
            <p className="text-lg font-semibold">{summary.assignments_due_count}</p>
          </div>
          <div className="rounded-lg border p-3">
            <p className="text-xs uppercase text-muted-foreground">Pacing</p>
            <Badge variant={badgeVariant(summary.pacing_status)}>{summary.pacing_status?.replace('_', ' ') || 'No targets'}</Badge>
          </div>
        </div>
        <div className="flex items-center justify-between">
          <Badge variant={badgeVariant(summary.compliance_status)}>{summary.compliance_status?.replace('_', ' ') || 'No alerts'}</Badge>
          <Button asChild size="sm" variant="outline">
            <Link to={`/students/${summary.student_id}`}>View profile</Link>
          </Button>
        </div>
      </CardContent>
    </Card>
  )
}

export function DashboardPage() {
  const { role } = useAuth()
  const { dashboard, loading, error, reload } = useDashboard()
  const [collapsed, setCollapsed] = useState<Record<string, boolean>>({})

  if (loading) return <LoadingState message="Loading dashboard…" />
  if (error) return <ErrorState message={error} onRetry={() => void reload()} />
  if (!dashboard) return <ErrorState message="Dashboard is unavailable." onRetry={() => void reload()} />

  const isStudentView = role === 'student_viewer'
  const toggleSection = (sectionKey: string) =>
    setCollapsed((current) => ({
      ...current,
      [sectionKey]: !current[sectionKey],
    }))

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <div>
            <CardTitle>{isStudentView ? 'Your dashboard' : 'Family dashboard'}</CardTitle>
            <CardDescription>
              {isStudentView ? 'Today’s schedule, assignments, and recent grades in one place.' : 'A single view of schedule, assignments, grades, attendance, pacing, compliance, and system health.'}
            </CardDescription>
          </div>
          <CardAction className="flex items-center gap-2">
            <p className="hidden text-xs text-muted-foreground md:block">Updated {new Date(dashboard.generated_at).toLocaleString()}</p>
            <Button size="sm" variant="outline" onClick={() => void reload()}>
              <RefreshCcw className="h-4 w-4" />
              Refresh
            </Button>
          </CardAction>
        </CardHeader>
      </Card>

      {!isStudentView ? (
        <>
          <Card>
            <CardHeader>
              <CardTitle>Quick actions</CardTitle>
              <CardDescription>Jump straight into the most common family admin tasks.</CardDescription>
            </CardHeader>
            <CardContent className="flex flex-wrap gap-2">
              <Button asChild variant="outline">
                <Link to="/attendance">Add attendance</Link>
              </Button>
              <Button asChild variant="outline">
                <Link to="/assignments">Create assignment</Link>
              </Button>
              <Button asChild variant="outline">
                <Link to="/grades">Record grade</Link>
              </Button>
            </CardContent>
          </Card>

          <section className="space-y-3">
            <div>
              <h2 className="text-lg font-semibold">Student summary</h2>
              <p className="text-sm text-muted-foreground">Open a student profile for a focused view.</p>
            </div>
            {dashboard.student_summaries.length ? (
              <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
                {dashboard.student_summaries.map((summary) => (
                  <StudentSummaryCard key={summary.student_id} summary={summary} />
                ))}
              </div>
            ) : (
              <EmptyState title="No students yet" description="Add a student to start building your dashboard." />
            )}
          </section>
        </>
      ) : null}

      <div className={`grid gap-4 ${isStudentView ? 'xl:grid-cols-1' : 'xl:grid-cols-[minmax(0,2fr)_minmax(320px,1fr)]'}`}>
        <div className="space-y-4">
          <WidgetCard
            title="Today’s schedule"
            description="Scheduled blocks for today."
            sectionKey="schedule"
            collapsed={collapsed}
            onToggle={toggleSection}
          >
            {dashboard.today_schedule.length ? (
              <div className="space-y-3">
                {dashboard.today_schedule.map((item) => (
                  <div key={`${item.student_id}-${item.schedule_id}-${item.start_time}-${item.subject_name}`} className="flex flex-wrap items-start justify-between gap-3 rounded-lg border p-3">
                    <div>
                      <div className="flex flex-wrap items-center gap-2">
                        <p className="font-medium">{item.subject_name}</p>
                        {!isStudentView ? <Badge variant="outline">{item.student_name}</Badge> : null}
                        <Badge variant={badgeVariant(item.source === 'override' ? 'warning' : 'healthy')}>
                          {item.source === 'override' ? item.override_type?.replace('_', ' ') || 'override' : 'recurring'}
                        </Badge>
                      </div>
                      <p className="text-sm text-muted-foreground">
                        {formatTime(item.start_time)} – {formatTime(item.end_time)}
                        {item.location ? ` · ${item.location}` : ''}
                      </p>
                      {item.reason || item.notes ? <p className="mt-1 text-sm text-muted-foreground">{item.reason || item.notes}</p> : null}
                    </div>
                    <p className="text-xs text-muted-foreground">{item.schedule_name}</p>
                  </div>
                ))}
              </div>
            ) : (
              <EmptyState title="Nothing scheduled today" description="Add schedule blocks to see today’s plan here." />
            )}
          </WidgetCard>

          <WidgetCard
            title="Upcoming assignments"
            description="Due in the next 7 days."
            sectionKey="assignments"
            collapsed={collapsed}
            onToggle={toggleSection}
          >
            {dashboard.upcoming_assignments.length ? (
              <div className="space-y-3">
                {dashboard.upcoming_assignments.map((item) => (
                  <div key={`${item.assignment_id}-${item.student_id ?? 'all'}`} className="flex flex-wrap items-start justify-between gap-3 rounded-lg border p-3">
                    <div>
                      <div className="flex flex-wrap items-center gap-2">
                        <p className="font-medium">{item.title}</p>
                        {item.subject_name ? <Badge variant="outline">{item.subject_name}</Badge> : null}
                        {!isStudentView && item.student_name ? <Badge variant="outline">{item.student_name}</Badge> : null}
                      </div>
                      <p className="text-sm text-muted-foreground">
                        Due {new Date(item.due_date).toLocaleDateString()} · {item.days_until_due === 0 ? 'today' : `${item.days_until_due} day${item.days_until_due === 1 ? '' : 's'} left`}
                      </p>
                    </div>
                    <Badge variant={badgeVariant(item.status)}>{item.status.replace('_', ' ')}</Badge>
                  </div>
                ))}
              </div>
            ) : (
              <EmptyState title="No due dates coming up" description="Assignments due this week will appear here." />
            )}
          </WidgetCard>

          <WidgetCard
            title="Recent grades"
            description="Latest graded submissions."
            sectionKey="grades"
            collapsed={collapsed}
            onToggle={toggleSection}
          >
            {dashboard.recent_grades.length ? (
              <div className="space-y-3">
                {dashboard.recent_grades.map((item) => (
                  <div key={item.grade_id} className="flex flex-wrap items-start justify-between gap-3 rounded-lg border p-3">
                    <div>
                      <div className="flex flex-wrap items-center gap-2">
                        <p className="font-medium">{item.assignment_title}</p>
                        {item.subject_name ? <Badge variant="outline">{item.subject_name}</Badge> : null}
                        {!isStudentView ? <Badge variant="outline">{item.student_name}</Badge> : null}
                      </div>
                      <p className="text-sm text-muted-foreground">
                        {item.score}/{item.max_score} · {item.percent.toFixed(1)}%
                        {item.letter_grade ? ` · ${item.letter_grade}` : ''}
                      </p>
                    </div>
                    <p className="text-xs text-muted-foreground">{new Date(item.graded_at).toLocaleString()}</p>
                  </div>
                ))}
              </div>
            ) : (
              <EmptyState title="No graded work yet" description="Grades will show up as soon as submissions are scored." />
            )}
          </WidgetCard>
        </div>

        {!isStudentView ? (
          <div className="space-y-4">
            <WidgetCard
              title="Attendance snapshot"
              description="Today’s attendance status for each student."
              sectionKey="attendance"
              collapsed={collapsed}
              onToggle={toggleSection}
            >
              {dashboard.attendance_today.length ? (
                <div className="space-y-3">
                  {dashboard.attendance_today.map((item) => (
                    <div key={item.student_id} className="flex items-center justify-between gap-3 rounded-lg border p-3">
                      <div>
                        <p className="font-medium">{item.student_name}</p>
                        <p className="text-sm text-muted-foreground">
                          {item.instructional_hours ? `${item.instructional_hours} hours` : 'No hours logged'}
                        </p>
                      </div>
                      <Badge variant={badgeVariant(item.status)}>{item.status.replace('_', ' ')}</Badge>
                    </div>
                  ))}
                </div>
              ) : (
                <EmptyState title="No attendance yet" description="Today’s attendance entries will appear here." />
              )}
            </WidgetCard>

            <WidgetCard
              title="Pacing alerts"
              description="Students currently behind pace."
              sectionKey="pacing"
              collapsed={collapsed}
              onToggle={toggleSection}
            >
              {dashboard.pacing_alerts.length ? (
                <div className="space-y-3">
                  {dashboard.pacing_alerts.map((item) => (
                    <div key={item.pacing_target_id} className="rounded-lg border p-3">
                      <div className="flex flex-wrap items-center gap-2">
                        <p className="font-medium">{item.unit_name}</p>
                        <Badge variant="outline">{item.student_name}</Badge>
                      </div>
                      <p className="text-sm text-muted-foreground">
                        {item.package_name} · {item.remaining_lessons} lessons remaining
                      </p>
                      <p className="text-xs text-destructive">Target ended {new Date(item.target_end_date).toLocaleDateString()}</p>
                    </div>
                  ))}
                </div>
              ) : (
                <EmptyState title="No pacing alerts" description="Students who fall behind pace will show up here." />
              )}
            </WidgetCard>

            <WidgetCard
              title="Compliance warnings"
              description="Warning and non-compliant items that need attention."
              sectionKey="compliance"
              collapsed={collapsed}
              onToggle={toggleSection}
            >
              {dashboard.compliance_warnings.length ? (
                <div className="space-y-3">
                  {dashboard.compliance_warnings.map((item, index) => (
                    <div key={`${item.student_id}-${item.rule_name}-${index}`} className="rounded-lg border p-3">
                      <div className="flex flex-wrap items-center gap-2">
                        <p className="font-medium">{item.rule_name}</p>
                        <Badge variant="outline">{item.student_name}</Badge>
                        <Badge variant={badgeVariant(item.status)}>{item.status.replace('_', ' ')}</Badge>
                      </div>
                      <p className="text-sm text-muted-foreground">
                        {item.current_value}/{item.required_value} {item.threshold_unit}
                      </p>
                    </div>
                  ))}
                </div>
              ) : (
                <EmptyState title="No compliance warnings" description="Compliance risks will appear here when they need review." />
              )}
            </WidgetCard>

            <WidgetCard
              title="System status"
              description="Operator summary from the health checks."
              sectionKey="system"
              collapsed={collapsed}
              onToggle={toggleSection}
            >
              {dashboard.system_status ? (
                <div className="space-y-3">
                  <div className="flex items-center justify-between rounded-lg border p-3">
                    <div className="flex items-center gap-2">
                      <Activity className="h-4 w-4 text-muted-foreground" />
                      <p className="font-medium">Overall status</p>
                    </div>
                    <Badge variant={badgeVariant(dashboard.system_status.status)}>{dashboard.system_status.status}</Badge>
                  </div>
                  <div className="grid grid-cols-2 gap-3">
                    <div className="rounded-lg border p-3">
                      <p className="text-xs uppercase text-muted-foreground">Healthy</p>
                      <p className="text-lg font-semibold">{dashboard.system_status.healthy_services}</p>
                    </div>
                    <div className="rounded-lg border p-3">
                      <p className="text-xs uppercase text-muted-foreground">Degraded / unhealthy</p>
                      <p className="text-lg font-semibold">
                        {dashboard.system_status.degraded_services + dashboard.system_status.unhealthy_services}
                      </p>
                    </div>
                  </div>
                  {dashboard.system_status.affected_services.length ? (
                    <div className="rounded-lg border p-3">
                      <p className="mb-2 text-xs uppercase text-muted-foreground">Affected services</p>
                      <div className="flex flex-wrap gap-2">
                        {dashboard.system_status.affected_services.map((service) => (
                          <Badge key={service} variant="outline">
                            {service}
                          </Badge>
                        ))}
                      </div>
                    </div>
                  ) : null}
                </div>
              ) : (
                <EmptyState title="No system summary" description="System health data is only shown to parent and tutor roles." />
              )}
            </WidgetCard>
          </div>
        ) : null}
      </div>
    </div>
  )
}
