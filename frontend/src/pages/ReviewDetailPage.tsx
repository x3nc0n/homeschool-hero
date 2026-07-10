import { useCallback, useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { Collapsible as CollapsiblePrimitive } from 'radix-ui'
import { ChevronDown } from 'lucide-react'
import { api } from '@/lib/api'
import type { ReviewPriority, ReviewQueueItem, ReviewReviewer, ReviewStatus } from '@/types/api'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { Badge } from '@/components/ui/badge'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { LoadingState } from '@/components/common/LoadingState'
import { ErrorState } from '@/components/common/ErrorState'
import { cn } from '@/lib/utils'

function ConfidenceBand({ confidence }: { confidence: number | undefined }) {
  const { t } = useTranslation('common')
  if (confidence == null) {
    return <span className="text-sm text-muted-foreground">{t('review.confidenceNone')}</span>
  }
  const pct = confidence.toFixed(2)
  if (confidence >= 0.85) {
    return (
      <span className="inline-flex items-center gap-1.5 text-sm font-medium text-emerald-700 dark:text-emerald-400">
        <span className="size-2 shrink-0 rounded-full bg-emerald-500" aria-hidden="true" />
        {t('review.confidenceHigh')} · {pct}
      </span>
    )
  }
  if (confidence >= 0.6) {
    return (
      <div className="space-y-0.5">
        <span className="inline-flex items-center gap-1.5 text-sm font-medium text-amber-700 dark:text-amber-400">
          <span className="size-2 shrink-0 rounded-full bg-amber-500" aria-hidden="true" />
          {t('review.confidenceMedium')} · {pct}
        </span>
        <p className="text-xs text-muted-foreground">{t('review.confidenceGuidanceMedium')}</p>
      </div>
    )
  }
  return (
    <div className="space-y-0.5">
      <span className="inline-flex items-center gap-1.5 text-sm font-medium text-destructive">
        <span className="size-2 shrink-0 rounded-full bg-destructive" aria-hidden="true" />
        {t('review.confidenceLow')} · {pct}
      </span>
      <p className="text-xs text-muted-foreground">{t('review.confidenceGuidanceLow')}</p>
    </div>
  )
}

export function ReviewDetailPage() {
  const navigate = useNavigate()
  const { t } = useTranslation('common')
  const params = useParams<{ reviewId: string }>()
  const reviewId = Number(params.reviewId)

  const [item, setItem] = useState<ReviewQueueItem | null>(null)
  const [reviewers, setReviewers] = useState<ReviewReviewer[]>([])
  const [score, setScore] = useState('')
  const [feedback, setFeedback] = useState('')
  const [notes, setNotes] = useState('')
  const [overrideReason, setOverrideReason] = useState('')
  const [rejectReason, setRejectReason] = useState('')
  const [comment, setComment] = useState('')
  const [assignee, setAssignee] = useState('')
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [moreOpen, setMoreOpen] = useState(false)

  const statusLabels: Record<ReviewStatus, string> = {
    pending_review: t('review.statusPendingReview'),
    in_review: t('review.statusInReview'),
    needs_regrade: t('review.statusNeedsRegrade'),
    approved: t('review.statusApproved'),
    rejected: t('review.statusRejected'),
  }

  const priorityLabels: Record<ReviewPriority, string> = {
    urgent: t('review.priorityUrgent'),
    high: t('review.priorityHigh'),
    medium: t('review.priorityMedium'),
    low: t('review.priorityLow'),
  }

  const roleLabels: Record<string, string> = {
    parent: t('roles.parent'),
    'co-parent': t('roles.co-parent'),
    tutor: t('roles.tutor'),
    student_viewer: t('roles.student_viewer'),
  }

  const syncForm = (reviewItem: ReviewQueueItem) => {
    setScore(reviewItem.ai_suggested_grade != null ? String(reviewItem.ai_suggested_grade) : '')
    setFeedback(reviewItem.ai_feedback || '')
    setNotes(reviewItem.reviewer_notes || '')
    setOverrideReason('')
    setRejectReason(reviewItem.manual_review_reason || '')
    setAssignee(reviewItem.assigned_to_user_id ? String(reviewItem.assigned_to_user_id) : '')
  }

  const load = useCallback(async () => {
    if (!reviewId) {
      setError(t('review.errorInvalidId'))
      setLoading(false)
      return
    }
    setLoading(true)
    setError('')
    try {
      const [reviewData, reviewerData] = await Promise.all([api.getReview(reviewId), api.listReviewers()])
      setItem(reviewData)
      setReviewers(reviewerData)
      syncForm(reviewData)
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : t('review.errorLoadDetail'))
    } finally {
      setLoading(false)
    }
  }, [reviewId, t])

  useEffect(() => {
    void load()
  }, [load])

  const refreshItem = (next: ReviewQueueItem) => {
    setItem(next)
    syncForm(next)
  }

  const runAction = async (runner: () => Promise<ReviewQueueItem>) => {
    setSaving(true)
    setError('')
    try {
      refreshItem(await runner())
    } catch (actionError) {
      setError(actionError instanceof Error ? actionError.message : t('review.errorSave'))
    } finally {
      setSaving(false)
    }
  }

  const submitComment = async () => {
    if (!item || !comment.trim()) return
    setSaving(true)
    setError('')
    try {
      await api.addReviewComment(item.id, { body: comment.trim() })
      setComment('')
      refreshItem(await api.getReview(item.id))
    } catch (commentError) {
      setError(commentError instanceof Error ? commentError.message : t('review.errorAddComment'))
    } finally {
      setSaving(false)
    }
  }

  if (loading) return <LoadingState message={t('review.loadingDetail')} />
  if (error && !item) return <ErrorState message={error} onRetry={() => void load()} />
  if (!item) return <ErrorState message={t('review.detailNotFound')} onRetry={() => navigate('/review')} />

  const itemTitle = item.assignment_title || t('review.submission', { id: item.submission_id })

  return (
    <div className="space-y-4">
      {/* Page header */}
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h2 className="text-2xl font-semibold">{itemTitle}</h2>
          <p className="text-sm text-muted-foreground">
            {item.student_name || t('review.colStudent')} · {item.subject_name || t('review.colSubject')} · review #{item.id}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Badge variant="outline">{statusLabels[item.status] ?? item.status.replace(/_/g, ' ')}</Badge>
          <Badge variant={item.priority === 'urgent' ? 'destructive' : 'secondary'}>
            {priorityLabels[item.priority] ?? item.priority}
          </Badge>
          <Button variant="outline" onClick={() => navigate('/review')}>
            {t('review.backToQueue')}
          </Button>
        </div>
      </div>

      {error ? <ErrorState message={error} onRetry={() => void load()} /> : null}

      <div className="grid gap-4 xl:grid-cols-[1.4fr_1fr]">
        {/* Left — submission evidence */}
        <Card>
          <CardHeader>
            <CardTitle>{t('review.submissionReviewTitle')}</CardTitle>
            <CardDescription>{t('review.submissionReviewDesc')}</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid gap-4 lg:grid-cols-2">
              <div className="space-y-2">
                <h3 className="text-sm font-semibold">{t('review.submissionImageLabel')}</h3>
                {item.submission_image_url ? (
                  <img
                    alt={t('review.submissionImageLabel')}
                    src={item.submission_image_url}
                    className="max-h-[420px] w-full rounded-md border object-contain"
                  />
                ) : (
                  <div className="rounded-md border border-dashed p-6 text-sm text-muted-foreground">
                    {t('review.submissionImageUnavailable')}
                  </div>
                )}
              </div>
              <div className="space-y-2">
                <h3 className="text-sm font-semibold">{t('review.ocrTextLabel')}</h3>
                <Textarea readOnly value={item.ocr_text || ''} className="min-h-[420px]" />
              </div>
            </div>

            {item.answer_key_result ? (
              <div className="rounded-lg border bg-muted/40 p-4 text-sm">
                <p className="font-medium">
                  {t('review.answerKeySuggestion', {
                    score: item.answer_key_result.score,
                    max: item.answer_key_result.max_score,
                  })}
                </p>
                <p className="text-muted-foreground">
                  {t('review.answerKeyAnswered', {
                    answered: item.answer_key_result.answered_questions,
                    total: item.answer_key_result.total_questions,
                  })}
                </p>
              </div>
            ) : null}
          </CardContent>
        </Card>

        {/* Right — decision */}
        <Card>
          <CardHeader>
            <CardTitle>{t('review.decisionTitle')}</CardTitle>
            <CardDescription>{t('review.decisionDesc')}</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {/* AI confidence band */}
            <div className="rounded-lg border bg-muted/30 px-3 py-2.5">
              <ConfidenceBand confidence={item.ai_confidence} />
            </div>

            {/* Primary actions — at top per distill spec (80% approve path) */}
            <div className="flex flex-wrap gap-2">
              <Button
                disabled={saving}
                onClick={() =>
                  void runAction(() =>
                    api.approveReview(item.id, {
                      score: score ? Number(score) : undefined,
                      feedback,
                      notes,
                      override_reason: overrideReason || undefined,
                    }),
                  )
                }
              >
                {t('review.approveButton')}
              </Button>
              <Button
                variant="secondary"
                disabled={saving}
                onClick={() =>
                  void runAction(() => api.regradeReview(item.id, { reason: rejectReason || notes || undefined }))
                }
              >
                {t('review.regradeButton')}
              </Button>
            </div>

            <hr className="border-border" />

            {/* Always-visible fields: score + notes */}
            <div className="space-y-2">
              <Label htmlFor="rdp-score">{t('review.finalScore')}</Label>
              <Input
                id="rdp-score"
                type="number"
                value={score}
                onChange={(e) => setScore(e.target.value)}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="rdp-notes">{t('review.reviewerNotes')}</Label>
              <Textarea id="rdp-notes" value={notes} onChange={(e) => setNotes(e.target.value)} />
            </div>

            {/* Progressive disclosure: override / reject / assign */}
            <CollapsiblePrimitive.Root open={moreOpen} onOpenChange={setMoreOpen}>
              <CollapsiblePrimitive.Trigger asChild>
                <Button
                  variant="ghost"
                  size="sm"
                  className="w-full justify-start gap-1.5 px-0 text-muted-foreground hover:text-foreground"
                >
                  <ChevronDown
                    className={cn('size-4 shrink-0 transition-transform duration-200', moreOpen && 'rotate-180')}
                    aria-hidden="true"
                  />
                  {moreOpen ? t('review.lessOptions') : t('review.moreOptions')}
                </Button>
              </CollapsiblePrimitive.Trigger>
              <CollapsiblePrimitive.Content className="space-y-4 pt-1">
                <div className="space-y-2">
                  <Label htmlFor="rdp-feedback">{t('review.aiFeedback')}</Label>
                  <Textarea id="rdp-feedback" value={feedback} onChange={(e) => setFeedback(e.target.value)} />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="rdp-override">{t('review.overrideReason')}</Label>
                  <Input
                    id="rdp-override"
                    value={overrideReason}
                    onChange={(e) => setOverrideReason(e.target.value)}
                    placeholder={t('review.overrideReasonHint')}
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="rdp-reject">{t('review.rejectReason')}</Label>
                  <Textarea id="rdp-reject" value={rejectReason} onChange={(e) => setRejectReason(e.target.value)} />
                </div>
                <div className="space-y-2">
                  <Label>{t('review.assignReviewer')}</Label>
                  <div className="flex gap-2">
                    <Select value={assignee} onValueChange={setAssignee}>
                      <SelectTrigger className="min-w-0 flex-1">
                        <SelectValue placeholder={t('review.selectReviewer')} />
                      </SelectTrigger>
                      <SelectContent>
                        {reviewers.map((reviewer) => (
                          <SelectItem key={reviewer.user_id} value={String(reviewer.user_id)}>
                            {reviewer.display_name} · {roleLabels[reviewer.role] ?? reviewer.role.replace(/_/g, ' ')}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                    <Button
                      variant="outline"
                      disabled={!assignee || saving}
                      onClick={() =>
                        void runAction(() =>
                          api.assignReview(item.id, { assigned_to_user_id: Number(assignee) }),
                        )
                      }
                    >
                      {t('review.assignButton')}
                    </Button>
                  </div>
                </div>
                <Button
                  variant="destructive"
                  disabled={saving}
                  onClick={() =>
                    void runAction(() =>
                      api.rejectReview(item.id, {
                        reason: rejectReason || undefined,
                        notes: notes || undefined,
                      }),
                    )
                  }
                >
                  {t('review.rejectButton')}
                </Button>
              </CollapsiblePrimitive.Content>
            </CollapsiblePrimitive.Root>

            {/* Summary info */}
            <div className="space-y-2 rounded-lg border p-3 text-sm">
              <div>
                <p className="font-medium">{t('review.summaryAssignment')}</p>
                <p className="text-muted-foreground">{item.assignment_title || t('review.summaryAssignmentUnknown')}</p>
              </div>
              <div>
                <p className="font-medium">{t('review.summaryAssignedReviewer')}</p>
                <p className="text-muted-foreground">{item.assigned_to_name || t('review.unassigned')}</p>
              </div>
              <div>
                <p className="font-medium">{t('review.summaryLastNote')}</p>
                <p className="text-muted-foreground">
                  {item.reviewer_notes || item.manual_review_reason || t('review.summaryNoNotes')}
                </p>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Comments */}
      <Card>
        <CardHeader>
          <CardTitle>{t('review.commentsTitle')}</CardTitle>
          <CardDescription>{t('review.commentsDesc')}</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-3">
            {item.comments.length > 0 ? (
              item.comments.map((entry) => (
                <div key={entry.id} className="rounded-lg border p-3">
                  <div className="flex items-center justify-between gap-2">
                    <p className="font-medium">{entry.author_name}</p>
                    <p className="text-xs text-muted-foreground">{new Date(entry.created_at).toLocaleString()}</p>
                  </div>
                  <p className="mt-2 text-sm text-muted-foreground">{entry.body}</p>
                </div>
              ))
            ) : (
              <p className="text-sm text-muted-foreground">{t('review.noComments')}</p>
            )}
          </div>
          <div className="space-y-2">
            <Label htmlFor="rdp-comment">{t('review.addCommentLabel')}</Label>
            <Textarea
              id="rdp-comment"
              value={comment}
              onChange={(e) => setComment(e.target.value)}
              placeholder={t('review.addCommentPlaceholder')}
            />
            <Button
              variant="outline"
              disabled={saving || !comment.trim()}
              onClick={() => void submitComment()}
            >
              {t('review.addCommentButton')}
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}

