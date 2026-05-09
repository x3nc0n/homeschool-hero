import { useCallback, useEffect, useMemo, useState } from 'react'
import { api } from '@/lib/api'
import type { Assignment, DashboardSummary, Grade, HealthResponse, ReviewQueueItem } from '@/types/api'
import { useAuth } from '@/context/AuthContext'
import { useCapabilities } from '@/context/CapabilitiesContext'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { LoadingState } from '@/components/common/LoadingState'
import { ErrorState } from '@/components/common/ErrorState'

function average(values: number[]) {
  if (!values.length) return 0
  return values.reduce((sum, value) => sum + value, 0) / values.length
}

export function DashboardPage() {
  const { canReviewQueue } = useAuth()
  const { status: capabilityStatus, optionalUnavailable } = useCapabilities()
  const [assignments, setAssignments] = useState<Assignment[]>([])
  const [grades, setGrades] = useState<Grade[]>([])
  const [queue, setQueue] = useState<ReviewQueueItem[]>([])
  const [dashboardSummary, setDashboardSummary] = useState<DashboardSummary | null>(null)
  const [health, setHealth] = useState<HealthResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const [assignmentData, gradeData, queueData, summaryData, healthData] = await Promise.all([
        api.listAssignments({ page: 1, page_size: 25 }),
        api.listGrades(),
        canReviewQueue ? api.listReviewQueue() : Promise.resolve([]),
        api.getDashboardSummary(),
        api.getHealth(),
      ])
      setAssignments(assignmentData.items)
      setGrades(gradeData)
      setQueue(queueData)
      setDashboardSummary(summaryData)
      setHealth(healthData)
    } catch (dashboardError) {
      setError(dashboardError instanceof Error ? dashboardError.message : 'Unable to load dashboard')
    } finally {
      setLoading(false)
    }
  }, [canReviewQueue])

  useEffect(() => {
    void load()
  }, [load])

  const recentAssignments = useMemo(
    () =>
      [...assignments]
        .sort((a, b) => new Date(b.created_at || 0).getTime() - new Date(a.created_at || 0).getTime())
        .slice(0, 5),
    [assignments],
  )

  const gradeAverage = useMemo(() => average(grades.map((grade) => (grade.score / grade.max_score) * 100)), [grades])
  const healthStatus = health?.status || capabilityStatus
  const systemHealth = dashboardSummary?.system_health
  const recentActivity = dashboardSummary?.recent_activity || []

  if (loading) return <LoadingState message="Loading dashboard…" />
  if (error) return <ErrorState message={error} onRetry={() => void load()} />

  const summaryCards = [
    { label: 'Recent assignments', value: assignments.length },
    { label: 'Grade average', value: `${gradeAverage.toFixed(1)}%` },
    ...(canReviewQueue ? [{ label: 'Pending reviews', value: queue.length }] : []),
  ]

  return (
    <div className="space-y-4">
      <div className={`grid gap-4 ${summaryCards.length === 3 ? 'md:grid-cols-3' : 'md:grid-cols-2'}`}>
        {summaryCards.map((card) => (
          <Card key={card.label}>
            <CardHeader>
              <CardDescription>{card.label}</CardDescription>
              <CardTitle>{card.value}</CardTitle>
            </CardHeader>
          </Card>
        ))}
      </div>

      <div className="grid gap-4 lg:grid-cols-[1.2fr_1fr]">
        <Card>
          <CardHeader>
            <CardTitle>Recent activity</CardTitle>
            <CardDescription>Latest auth, grading, and review events for this family.</CardDescription>
          </CardHeader>
          <CardContent>
            {recentActivity.length ? (
              <div className="space-y-3">
                {recentActivity.map((item) => (
                  <div key={item.id} className="flex items-start justify-between gap-3 rounded-md border p-3">
                    <div className="space-y-1">
                      <div className="flex items-center gap-2">
                        <p className="font-medium">{item.title}</p>
                        <Badge variant={item.status === 'failed' ? 'destructive' : 'secondary'}>{item.status}</Badge>
                      </div>
                      <p className="text-sm text-muted-foreground">{item.subtitle}</p>
                      <p className="text-xs text-muted-foreground">
                        {new Date(item.timestamp).toLocaleString()}
                      </p>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-sm text-muted-foreground">No recent activity yet.</p>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>System health</CardTitle>
            <CardDescription>Quick operator view of app health, grading load, and backups.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex items-center justify-between">
              <span className="text-sm text-muted-foreground">Overall status</span>
              <Badge variant={healthStatus === 'ok' ? 'secondary' : 'destructive'}>{healthStatus}</Badge>
            </div>
            <div className="grid gap-3 sm:grid-cols-2">
              <div className="rounded-md border p-3">
                <p className="text-xs uppercase text-muted-foreground">Active users (24h)</p>
                <p className="text-2xl font-semibold">{systemHealth?.active_users ?? 0}</p>
              </div>
              <div className="rounded-md border p-3">
                <p className="text-xs uppercase text-muted-foreground">Slow requests</p>
                <p className="text-2xl font-semibold">{systemHealth?.slow_requests_total ?? 0}</p>
              </div>
            </div>
            <div className="space-y-2">
              <p className="text-sm font-medium">Capability alerts</p>
              {optionalUnavailable.length ? (
                <div className="flex flex-wrap gap-2">
                  {optionalUnavailable.map((name) => (
                    <Badge key={name} variant="outline">
                      {name.replace('_', ' ')} unavailable
                    </Badge>
                  ))}
                </div>
              ) : (
                <p className="text-sm text-muted-foreground">All optional services are available.</p>
              )}
            </div>
            <div className="space-y-2">
              <p className="text-sm font-medium">Grading queue</p>
              <div className="flex flex-wrap gap-2">
                {Object.entries(systemHealth?.grading_jobs_by_status || {}).map(([status, count]) => (
                  <Badge key={status} variant="secondary">
                    {status}: {count}
                  </Badge>
                ))}
                {!Object.keys(systemHealth?.grading_jobs_by_status || {}).length && (
                  <p className="text-sm text-muted-foreground">No grading jobs recorded yet.</p>
                )}
              </div>
            </div>
            <div className="rounded-md border p-3">
              <p className="text-xs uppercase text-muted-foreground">Last backup</p>
              {systemHealth?.backup_last_success?.timestamp ? (
                <>
                  <p className="font-medium">{new Date(systemHealth.backup_last_success.timestamp).toLocaleString()}</p>
                  <p className="text-xs text-muted-foreground">
                    {systemHealth.backup_last_success.size_bytes
                      ? `${Math.round(systemHealth.backup_last_success.size_bytes / 1024)} KB`
                      : 'Size unavailable'}
                  </p>
                </>
              ) : (
                <p className="text-sm text-muted-foreground">
                  {systemHealth?.metrics_enabled ? 'No successful backups recorded yet.' : 'Metrics endpoint disabled.'}
                </p>
              )}
            </div>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Recent assignments</CardTitle>
          <CardDescription>Keep tabs on what needs grading and follow-up.</CardDescription>
        </CardHeader>
        <CardContent>
          {recentAssignments.length ? (
            <div className="space-y-2">
              {recentAssignments.map((assignment) => (
                <div key={assignment.id} className="flex flex-wrap items-center justify-between gap-2 rounded-md border p-3">
                  <div>
                    <p className="font-medium">{assignment.title}</p>
                    <p className="text-xs text-muted-foreground">
                      Due {assignment.due_date ? new Date(assignment.due_date).toLocaleDateString() : 'unscheduled'}
                    </p>
                  </div>
                  <Badge variant="secondary">{assignment.status}</Badge>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-sm text-muted-foreground">No assignments yet.</p>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
