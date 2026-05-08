import { useEffect, useMemo, useState } from 'react'
import { api } from '@/lib/api'
import type { Assignment, Grade, ReviewQueueItem } from '@/types/api'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { LoadingState } from '@/components/common/LoadingState'
import { ErrorState } from '@/components/common/ErrorState'

function average(values: number[]) {
  if (!values.length) return 0
  return values.reduce((sum, value) => sum + value, 0) / values.length
}

export function DashboardPage() {
  const [assignments, setAssignments] = useState<Assignment[]>([])
  const [grades, setGrades] = useState<Grade[]>([])
  const [queue, setQueue] = useState<ReviewQueueItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const load = async () => {
    setLoading(true)
    setError('')
    try {
      const [assignmentData, gradeData, queueData] = await Promise.all([
        api.listAssignments(),
        api.listGrades(),
        api.listReviewQueue(),
      ])
      setAssignments(assignmentData)
      setGrades(gradeData)
      setQueue(queueData)
    } catch (dashboardError) {
      setError(dashboardError instanceof Error ? dashboardError.message : 'Unable to load dashboard')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void load()
  }, [])

  const recentAssignments = useMemo(
    () =>
      [...assignments]
        .sort((a, b) => new Date(b.created_at || 0).getTime() - new Date(a.created_at || 0).getTime())
        .slice(0, 5),
    [assignments],
  )

  const gradeAverage = useMemo(() => average(grades.map((grade) => (grade.score / grade.max_score) * 100)), [grades])

  if (loading) return <LoadingState message="Loading dashboard…" />
  if (error) return <ErrorState message={error} onRetry={() => void load()} />

  return (
    <div className="space-y-4">
      <div className="grid gap-4 md:grid-cols-3">
        <Card>
          <CardHeader>
            <CardDescription>Recent assignments</CardDescription>
            <CardTitle>{assignments.length}</CardTitle>
          </CardHeader>
        </Card>
        <Card>
          <CardHeader>
            <CardDescription>Grade average</CardDescription>
            <CardTitle>{gradeAverage.toFixed(1)}%</CardTitle>
          </CardHeader>
        </Card>
        <Card>
          <CardHeader>
            <CardDescription>Pending reviews</CardDescription>
            <CardTitle>{queue.length}</CardTitle>
          </CardHeader>
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
            <p className="text-sm text-muted-foreground">No assignments yet. Add one in Assignments.</p>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
