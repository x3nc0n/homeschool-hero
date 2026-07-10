import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { X } from 'lucide-react'
import { api } from '@/lib/api'
import type { ReviewPriority, ReviewQueueItem, ReviewReviewer, ReviewStatus } from '@/types/api'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Badge } from '@/components/ui/badge'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog'
import { LoadingState } from '@/components/common/LoadingState'
import { ErrorState } from '@/components/common/ErrorState'
import { EmptyState } from '@/components/common/EmptyState'

const openStatuses: ReviewStatus[] = ['pending_review', 'in_review', 'needs_regrade']
const priorityRank: Record<ReviewPriority, number> = { urgent: 0, high: 1, medium: 2, low: 3 }

export function ReviewQueuePage() {
  const navigate = useNavigate()
  const { t } = useTranslation('common')
  const [queue, setQueue] = useState<ReviewQueueItem[]>([])
  const [reviewers, setReviewers] = useState<ReviewReviewer[]>([])
  const [selectedIds, setSelectedIds] = useState<number[]>([])
  const [bulkReviewerId, setBulkReviewerId] = useState('')
  const [bulkApproveOpen, setBulkApproveOpen] = useState(false)
  const [search, setSearch] = useState('')
  const [statusFilter, setStatusFilter] = useState<ReviewStatus | 'all'>('pending_review')
  const [priorityFilter, setPriorityFilter] = useState<ReviewPriority | 'all'>('all')
  const [studentFilter, setStudentFilter] = useState('all')
  const [subjectFilter, setSubjectFilter] = useState('all')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  const statusLabels = useMemo<Record<ReviewStatus, string>>(
    () => ({
      pending_review: t('review.statusPendingReview'),
      in_review: t('review.statusInReview'),
      needs_regrade: t('review.statusNeedsRegrade'),
      approved: t('review.statusApproved'),
      rejected: t('review.statusRejected'),
    }),
    [t],
  )

  const priorityLabels = useMemo<Record<ReviewPriority, string>>(
    () => ({
      urgent: t('review.priorityUrgent'),
      high: t('review.priorityHigh'),
      medium: t('review.priorityMedium'),
      low: t('review.priorityLow'),
    }),
    [t],
  )

  const roleLabels: Record<string, string> = {
    parent: t('roles.parent'),
    'co-parent': t('roles.co-parent'),
    tutor: t('roles.tutor'),
    student_viewer: t('roles.student_viewer'),
  }

  const load = async () => {
    setLoading(true)
    setError('')
    try {
      const [queueData, reviewerData] = await Promise.all([api.listReviewQueue(), api.listReviewers()])
      setQueue(queueData)
      setReviewers(reviewerData)
    } catch (queueError) {
      setError(queueError instanceof Error ? queueError.message : t('review.errorLoadQueue'))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void load()
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  const students = useMemo(
    () =>
      Array.from(
        new Map(
          queue.filter((item) => item.student_id).map((item) => [String(item.student_id), item.student_name || `Student #${item.student_id}`]),
        ).entries(),
      ),
    [queue],
  )

  const subjects = useMemo(
    () =>
      Array.from(
        new Map(
          queue.filter((item) => item.subject_id).map((item) => [String(item.subject_id), item.subject_name || `Subject #${item.subject_id}`]),
        ).entries(),
      ),
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

  // Active filter chips
  const filterChips = useMemo(() => {
    const chips: Array<{ key: string; label: string; onRemove: () => void }> = []
    if (statusFilter !== 'all') {
      chips.push({
        key: 'status',
        label: statusLabels[statusFilter as ReviewStatus] ?? statusFilter.replace(/_/g, ' '),
        onRemove: () => setStatusFilter('all'),
      })
    }
    if (priorityFilter !== 'all') {
      chips.push({
        key: 'priority',
        label: priorityLabels[priorityFilter as ReviewPriority] ?? priorityFilter,
        onRemove: () => setPriorityFilter('all'),
      })
    }
    if (studentFilter !== 'all') {
      chips.push({
        key: 'student',
        label: students.find(([id]) => id === studentFilter)?.[1] ?? studentFilter,
        onRemove: () => setStudentFilter('all'),
      })
    }
    if (subjectFilter !== 'all') {
      chips.push({
        key: 'subject',
        label: subjects.find(([id]) => id === subjectFilter)?.[1] ?? subjectFilter,
        onRemove: () => setSubjectFilter('all'),
      })
    }
    if (search.trim()) {
      const q = search.trim()
      chips.push({
        key: 'search',
        label: `"${q.length > 20 ? q.slice(0, 20) + '…' : q}"`,
        onRemove: () => setSearch(''),
      })
    }
    return chips
  }, [statusFilter, priorityFilter, studentFilter, subjectFilter, search, students, subjects, statusLabels, priorityLabels])

  const clearAllFilters = () => {
    setStatusFilter('all')
    setPriorityFilter('all')
    setStudentFilter('all')
    setSubjectFilter('all')
    setSearch('')
  }

  const toggleSelection = (reviewId: number) => {
    setSelectedIds((current) => (current.includes(reviewId) ? current.filter((id) => id !== reviewId) : [...current, reviewId]))
  }

  const setAllVisible = (checked: boolean) => {
    setSelectedIds(checked ? filteredQueue.map((item) => item.id) : [])
  }

  const confirmBulkApprove = async () => {
    if (!selectedIds.length) return
    setBusy(true)
    try {
      await api.bulkApproveReviews({ review_ids: selectedIds })
      setSelectedIds([])
      await load()
    } catch (bulkError) {
      setError(bulkError instanceof Error ? bulkError.message : t('review.errorBulkApprove'))
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
      setError(bulkError instanceof Error ? bulkError.message : t('review.errorBulkAssign'))
    } finally {
      setBusy(false)
    }
  }

  if (loading) return <LoadingState message={t('review.loadingQueue')} />
  if (error) return <ErrorState message={error} onRetry={() => void load()} />
  if (!queue.length) return <EmptyState title={t('review.queueEmptyTitle')} description={t('review.queueEmptyDesc')} />

  return (
    <div className="space-y-4">
      {/* Bulk-approve confirmation dialog */}
      <AlertDialog open={bulkApproveOpen} onOpenChange={setBulkApproveOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>{t('review.bulkApproveTitle', { count: selectedIds.length })}</AlertDialogTitle>
            <AlertDialogDescription>{t('review.bulkApproveDesc', { count: selectedIds.length })}</AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>{t('review.bulkApproveCancel')}</AlertDialogCancel>
            <AlertDialogAction disabled={busy} onClick={() => void confirmBulkApprove()}>
              {t('review.bulkApproveConfirm', { count: selectedIds.length })}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      <Card>
        <CardHeader>
          <CardTitle>{t('review.queueTitle')}</CardTitle>
          <CardDescription>{t('review.queueDescription', { count: openCount })}</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {/* Filters */}
          <div className="grid gap-3 md:grid-cols-5">
            <Input
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder={t('review.search')}
            />
            <Select value={statusFilter} onValueChange={(value) => setStatusFilter(value as ReviewStatus | 'all')}>
              <SelectTrigger><SelectValue placeholder={t('review.colStatus')} /></SelectTrigger>
              <SelectContent>
                <SelectItem value="all">{t('review.allStatuses')}</SelectItem>
                <SelectItem value="pending_review">{t('review.statusPendingReview')}</SelectItem>
                <SelectItem value="in_review">{t('review.statusInReview')}</SelectItem>
                <SelectItem value="needs_regrade">{t('review.statusNeedsRegrade')}</SelectItem>
                <SelectItem value="approved">{t('review.statusApproved')}</SelectItem>
                <SelectItem value="rejected">{t('review.statusRejected')}</SelectItem>
              </SelectContent>
            </Select>
            <Select value={priorityFilter} onValueChange={(value) => setPriorityFilter(value as ReviewPriority | 'all')}>
              <SelectTrigger><SelectValue placeholder={t('review.colPriority')} /></SelectTrigger>
              <SelectContent>
                <SelectItem value="all">{t('review.allPriorities')}</SelectItem>
                <SelectItem value="urgent">{t('review.priorityUrgent')}</SelectItem>
                <SelectItem value="high">{t('review.priorityHigh')}</SelectItem>
                <SelectItem value="medium">{t('review.priorityMedium')}</SelectItem>
                <SelectItem value="low">{t('review.priorityLow')}</SelectItem>
              </SelectContent>
            </Select>
            <Select value={studentFilter} onValueChange={setStudentFilter}>
              <SelectTrigger><SelectValue placeholder={t('review.colStudent')} /></SelectTrigger>
              <SelectContent>
                <SelectItem value="all">{t('review.allStudents')}</SelectItem>
                {students.map(([value, labelValue]) => (
                  <SelectItem key={value} value={value}>{labelValue}</SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Select value={subjectFilter} onValueChange={setSubjectFilter}>
              <SelectTrigger><SelectValue placeholder={t('review.colSubject')} /></SelectTrigger>
              <SelectContent>
                <SelectItem value="all">{t('review.allSubjects')}</SelectItem>
                {subjects.map(([value, labelValue]) => (
                  <SelectItem key={value} value={value}>{labelValue}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {/* Active filter chips + showing count */}
          <div className="flex min-h-6 flex-wrap items-center gap-2">
            {filterChips.map((chip) => (
              <Badge key={chip.key} variant="secondary" className="h-6 gap-1 pr-1">
                {chip.label}
                <button
                  type="button"
                  onClick={chip.onRemove}
                  aria-label={`Remove ${chip.label} filter`}
                  className="rounded-sm p-0.5 opacity-60 hover:opacity-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                >
                  <X className="size-3" aria-hidden="true" />
                </button>
              </Badge>
            ))}
            {filterChips.length > 0 && (
              <button
                type="button"
                onClick={clearAllFilters}
                className="rounded-sm text-xs text-muted-foreground underline underline-offset-2 hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              >
                {t('review.clearAll')}
              </button>
            )}
            <span className="ml-auto text-xs text-muted-foreground">
              {t('review.showingCount', { shown: filteredQueue.length, total: queue.length })}
            </span>
          </div>

          {/* Bulk actions */}
          <div className="flex flex-wrap items-center gap-2 rounded-lg border p-3">
            <Badge variant="secondary">{t('review.selectedCount', { count: selectedIds.length })}</Badge>
            <Button
              size="sm"
              onClick={() => setBulkApproveOpen(true)}
              disabled={!selectedIds.length || busy}
            >
              {t('review.bulkApprove')}
            </Button>
            <Select value={bulkReviewerId} onValueChange={setBulkReviewerId}>
              <SelectTrigger className="min-w-56"><SelectValue placeholder={t('review.bulkAssign')} /></SelectTrigger>
              <SelectContent>
                {reviewers.map((reviewer) => (
                  <SelectItem key={reviewer.user_id} value={String(reviewer.user_id)}>
                    {reviewer.display_name} · {roleLabels[reviewer.role] ?? reviewer.role.replace(/_/g, ' ')}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Button
              size="sm"
              variant="outline"
              onClick={() => void runBulkAssign()}
              disabled={!selectedIds.length || !bulkReviewerId || busy}
            >
              {t('review.bulkAssignButton')}
            </Button>
          </div>

          {!filteredQueue.length ? (
            <EmptyState title={t('review.noMatchTitle')} description={t('review.noMatchDesc')} />
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="w-10">
                    <input
                      type="checkbox"
                      aria-label={t('review.selectAllVisible')}
                      checked={filteredQueue.length > 0 && selectedIds.length === filteredQueue.length}
                      onChange={(event) => setAllVisible(event.target.checked)}
                    />
                  </TableHead>
                  <TableHead>{t('review.colAssignment')}</TableHead>
                  <TableHead>{t('review.colStudent')}</TableHead>
                  <TableHead>{t('review.colSubject')}</TableHead>
                  <TableHead>{t('review.colStatus')}</TableHead>
                  <TableHead>{t('review.colPriority')}</TableHead>
                  <TableHead>{t('review.colConfidence')}</TableHead>
                  <TableHead>{t('review.colAssigned')}</TableHead>
                  <TableHead className="text-right">{t('review.openReview')}</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {filteredQueue.map((item) => (
                  <TableRow key={item.id}>
                    <TableCell>
                      <input
                        type="checkbox"
                        aria-label={t('review.selectItem', { id: item.id })}
                        checked={selectedIds.includes(item.id)}
                        onChange={() => toggleSelection(item.id)}
                      />
                    </TableCell>
                    <TableCell>
                      <div>
                        <p className="font-medium">{item.assignment_title || t('review.submission', { id: item.submission_id })}</p>
                        <p className="text-xs text-muted-foreground">#{item.id}</p>
                      </div>
                    </TableCell>
                    <TableCell>{item.student_name || '—'}</TableCell>
                    <TableCell>{item.subject_name || '—'}</TableCell>
                    <TableCell>
                      <Badge variant="outline">
                        {statusLabels[item.status] ?? item.status.replace(/_/g, ' ')}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      <Badge variant={item.priority === 'urgent' ? 'destructive' : 'secondary'}>
                        {priorityLabels[item.priority] ?? item.priority}
                      </Badge>
                    </TableCell>
                    <TableCell>{item.ai_confidence != null ? item.ai_confidence.toFixed(2) : '—'}</TableCell>
                    <TableCell>{item.assigned_to_name || t('review.unassigned')}</TableCell>
                    <TableCell className="text-right">
                      <Button size="sm" variant="outline" onClick={() => navigate(`/review/${item.id}`)}>
                        {t('review.openReview')}
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

