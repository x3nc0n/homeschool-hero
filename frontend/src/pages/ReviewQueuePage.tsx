import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '@/lib/api'
import type { ReviewPriority, ReviewQueueItem, ReviewReviewer, ReviewStatus } from '@/types/api'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Badge } from '@/components/ui/badge'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { LoadingState } from '@/components/common/LoadingState'
import { ErrorState } from '@/components/common/ErrorState'
import { EmptyState } from '@/components/common/EmptyState'

const openStatuses: ReviewStatus[] = ['pending_review', 'in_review', 'needs_regrade']
const priorityRank: Record<ReviewPriority, number> = { urgent: 0, high: 1, medium: 2, low: 3 }

function label(value: string) {
  return value.replace(/_/g, ' ')
}

export function ReviewQueuePage() {
  const navigate = useNavigate()
  const [queue, setQueue] = useState<ReviewQueueItem[]>([])
  const [reviewers, setReviewers] = useState<ReviewReviewer[]>([])
  const [selectedIds, setSelectedIds] = useState<number[]>([])
  const [bulkReviewerId, setBulkReviewerId] = useState('')
  const [search, setSearch] = useState('')
  const [statusFilter, setStatusFilter] = useState<ReviewStatus | 'all'>('pending_review')
  const [priorityFilter, setPriorityFilter] = useState<ReviewPriority | 'all'>('all')
  const [studentFilter, setStudentFilter] = useState('all')
  const [subjectFilter, setSubjectFilter] = useState('all')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  const load = async () => {
    setLoading(true)
    setError('')
    try {
      const [queueData, reviewerData] = await Promise.all([
        api.listReviewQueue(),
        api.listReviewers(),
      ])
      setQueue(queueData)
      setReviewers(reviewerData)
    } catch (queueError) {
      setError(queueError instanceof Error ? queueError.message : 'Unable to load review queue')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void load()
  }, [])

  const students = useMemo(
    () => Array.from(new Map(queue.filter((item) => item.student_id).map((item) => [String(item.student_id), item.student_name || `Student #${item.student_id}`])).entries()),
    [queue],
  )
  const subjects = useMemo(
    () => Array.from(new Map(queue.filter((item) => item.subject_id).map((item) => [String(item.subject_id), item.subject_name || `Subject #${item.subject_id}`])).entries()),
    [queue],
  )

  const filteredQueue = useMemo(() => {
    const normalizedSearch = search.trim().toLowerCase()
    return [...queue]
      .filter((item) => (statusFilter === 'all' ? true : item.status === statusFilter))
      .filter((item) => (priorityFilter === 'all' ? true : item.priority === priorityFilter))
      .filter((item) => (studentFilter === 'all' ? true : String(item.student_id) === studentFilter))
      .filter((item) => (subjectFilter === 'all' ? true : String(item.subject_id) === subjectFilter))
      .filter((item) => {
        if (!normalizedSearch) return true
        return [item.assignment_title, item.student_name, item.subject_name, item.assigned_to_name]
          .filter(Boolean)
          .some((value) => value?.toLowerCase().includes(normalizedSearch))
      })
      .sort((left, right) => {
        const statusBiasLeft = openStatuses.includes(left.status) ? 0 : 1
        const statusBiasRight = openStatuses.includes(right.status) ? 0 : 1
        if (statusBiasLeft !== statusBiasRight) return statusBiasLeft - statusBiasRight
        const priorityDiff = priorityRank[left.priority] - priorityRank[right.priority]
        if (priorityDiff !== 0) return priorityDiff
        return new Date(left.created_at).getTime() - new Date(right.created_at).getTime()
      })
  }, [priorityFilter, queue, search, statusFilter, studentFilter, subjectFilter])

  const openCount = useMemo(() => queue.filter((item) => openStatuses.includes(item.status)).length, [queue])

  const toggleSelection = (reviewId: number) => {
    setSelectedIds((current) => (current.includes(reviewId) ? current.filter((id) => id !== reviewId) : [...current, reviewId]))
  }

  const setAllVisible = (checked: boolean) => {
    setSelectedIds(checked ? filteredQueue.map((item) => item.id) : [])
  }

  const runBulkApprove = async () => {
    if (!selectedIds.length) return
    setBusy(true)
    try {
      await api.bulkApproveReviews({ review_ids: selectedIds })
      setSelectedIds([])
      await load()
    } catch (bulkError) {
      setError(bulkError instanceof Error ? bulkError.message : 'Unable to approve selected reviews')
    } finally {
      setBusy(false)
    }
  }

  const runBulkAssign = async () => {
    if (!selectedIds.length || !bulkReviewerId) return
    setBusy(true)
    try {
      await api.bulkAssignReviews({ review_ids: selectedIds, assigned_to_user_id: Number(bulkReviewerId) })
      setSelectedIds([])
      await load()
    } catch (bulkError) {
      setError(bulkError instanceof Error ? bulkError.message : 'Unable to assign selected reviews')
    } finally {
      setBusy(false)
    }
  }

  if (loading) return <LoadingState message="Loading review queue…" />
  if (error) return <ErrorState message={error} onRetry={() => void load()} />
  if (!queue.length) return <EmptyState title="Review queue is clear" description="No AI grades are waiting for review." />

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <CardTitle>Review queue</CardTitle>
          <CardDescription>{openCount} active item(s) across your family review team.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-3 md:grid-cols-5">
            <Input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search assignment, student, subject…" />
            <Select value={statusFilter} onValueChange={(value) => setStatusFilter(value as ReviewStatus | 'all')}>
              <SelectTrigger><SelectValue placeholder="Status" /></SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All statuses</SelectItem>
                <SelectItem value="pending_review">Pending review</SelectItem>
                <SelectItem value="in_review">In review</SelectItem>
                <SelectItem value="needs_regrade">Needs regrade</SelectItem>
                <SelectItem value="approved">Approved</SelectItem>
                <SelectItem value="rejected">Rejected</SelectItem>
              </SelectContent>
            </Select>
            <Select value={priorityFilter} onValueChange={(value) => setPriorityFilter(value as ReviewPriority | 'all')}>
              <SelectTrigger><SelectValue placeholder="Priority" /></SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All priorities</SelectItem>
                <SelectItem value="urgent">Urgent</SelectItem>
                <SelectItem value="high">High</SelectItem>
                <SelectItem value="medium">Medium</SelectItem>
                <SelectItem value="low">Low</SelectItem>
              </SelectContent>
            </Select>
            <Select value={studentFilter} onValueChange={setStudentFilter}>
              <SelectTrigger><SelectValue placeholder="Student" /></SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All students</SelectItem>
                {students.map(([value, labelValue]) => (
                  <SelectItem key={value} value={value}>{labelValue}</SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Select value={subjectFilter} onValueChange={setSubjectFilter}>
              <SelectTrigger><SelectValue placeholder="Subject" /></SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All subjects</SelectItem>
                {subjects.map(([value, labelValue]) => (
                  <SelectItem key={value} value={value}>{labelValue}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="flex flex-wrap items-center gap-2 rounded-lg border p-3">
            <Badge variant="secondary">{selectedIds.length} selected</Badge>
            <Button size="sm" onClick={() => void runBulkApprove()} disabled={!selectedIds.length || busy}>
              Bulk approve
            </Button>
            <Select value={bulkReviewerId} onValueChange={setBulkReviewerId}>
              <SelectTrigger className="min-w-56"><SelectValue placeholder="Assign selected to…" /></SelectTrigger>
              <SelectContent>
                {reviewers.map((reviewer) => (
                  <SelectItem key={reviewer.user_id} value={String(reviewer.user_id)}>
                    {reviewer.display_name} · {label(reviewer.role)}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Button size="sm" variant="outline" onClick={() => void runBulkAssign()} disabled={!selectedIds.length || !bulkReviewerId || busy}>
              Bulk assign
            </Button>
          </div>

          {!filteredQueue.length ? (
            <EmptyState title="No matching reviews" description="Adjust your filters to see more queue items." />
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="w-10">
                    <input
                      type="checkbox"
                      aria-label="Select all visible review items"
                      checked={filteredQueue.length > 0 && selectedIds.length === filteredQueue.length}
                      onChange={(event) => setAllVisible(event.target.checked)}
                    />
                  </TableHead>
                  <TableHead>Assignment</TableHead>
                  <TableHead>Student</TableHead>
                  <TableHead>Subject</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Priority</TableHead>
                  <TableHead>AI confidence</TableHead>
                  <TableHead>Assigned</TableHead>
                  <TableHead className="text-right">Open</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {filteredQueue.map((item) => (
                  <TableRow key={item.id}>
                    <TableCell>
                      <input
                        type="checkbox"
                        aria-label={`Select review ${item.id}`}
                        checked={selectedIds.includes(item.id)}
                        onChange={() => toggleSelection(item.id)}
                      />
                    </TableCell>
                    <TableCell>
                      <div>
                        <p className="font-medium">{item.assignment_title || `Submission #${item.submission_id}`}</p>
                        <p className="text-xs text-muted-foreground">#{item.id}</p>
                      </div>
                    </TableCell>
                    <TableCell>{item.student_name || '—'}</TableCell>
                    <TableCell>{item.subject_name || '—'}</TableCell>
                    <TableCell><Badge variant="outline">{label(item.status)}</Badge></TableCell>
                    <TableCell><Badge variant={item.priority === 'urgent' ? 'destructive' : 'secondary'}>{label(item.priority)}</Badge></TableCell>
                    <TableCell>{item.ai_confidence != null ? item.ai_confidence.toFixed(2) : '—'}</TableCell>
                    <TableCell>{item.assigned_to_name || 'Unassigned'}</TableCell>
                    <TableCell className="text-right">
                      <Button size="sm" variant="outline" onClick={() => navigate(`/review/${item.id}`)}>
                        Open
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
