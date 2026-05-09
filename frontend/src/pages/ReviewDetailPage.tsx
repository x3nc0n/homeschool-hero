import { useCallback, useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { api } from '@/lib/api'
import type { ReviewQueueItem, ReviewReviewer } from '@/types/api'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { Badge } from '@/components/ui/badge'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { LoadingState } from '@/components/common/LoadingState'
import { ErrorState } from '@/components/common/ErrorState'

function label(value: string) {
  return value.replace(/_/g, ' ')
}

export function ReviewDetailPage() {
  const navigate = useNavigate()
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
      setError('Invalid review id')
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
      setError(loadError instanceof Error ? loadError.message : 'Unable to load review details')
    } finally {
      setLoading(false)
    }
  }, [reviewId])

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
      setError(actionError instanceof Error ? actionError.message : 'Unable to save review')
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
      setError(commentError instanceof Error ? commentError.message : 'Unable to add comment')
    } finally {
      setSaving(false)
    }
  }

  if (loading) return <LoadingState message="Loading review detail…" />
  if (error && !item) return <ErrorState message={error} onRetry={() => void load()} />
  if (!item) return <ErrorState message="Review not found" onRetry={() => navigate('/review')} />

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h2 className="text-2xl font-semibold">{item.assignment_title || `Submission #${item.submission_id}`}</h2>
          <p className="text-sm text-muted-foreground">
            {item.student_name || 'Student'} · {item.subject_name || 'Subject'} · review #{item.id}
          </p>
        </div>
        <div className="flex gap-2">
          <Badge variant="outline">{label(item.status)}</Badge>
          <Badge variant={item.priority === 'urgent' ? 'destructive' : 'secondary'}>{label(item.priority)}</Badge>
          <Button variant="outline" onClick={() => navigate('/review')}>
            Back to queue
          </Button>
        </div>
      </div>

      {error ? <ErrorState message={error} onRetry={() => void load()} /> : null}

      <div className="grid gap-4 xl:grid-cols-[1.4fr_1fr]">
        <Card>
          <CardHeader>
            <CardTitle>Submission review</CardTitle>
            <CardDescription>Compare the uploaded work, OCR output, and AI suggestion before finalizing.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid gap-4 lg:grid-cols-2">
              <div className="space-y-2">
                <h3 className="text-sm font-semibold">Submission image</h3>
                {item.submission_image_url ? (
                  <img alt="Submission" src={item.submission_image_url} className="max-h-[420px] w-full rounded-md border object-contain" />
                ) : (
                  <div className="rounded-md border border-dashed p-6 text-sm text-muted-foreground">Preview unavailable for this submission.</div>
                )}
              </div>
              <div className="space-y-2">
                <h3 className="text-sm font-semibold">OCR text</h3>
                <Textarea readOnly value={item.ocr_text || ''} className="min-h-[420px]" />
              </div>
            </div>

            {item.answer_key_result ? (
              <div className="rounded-lg border bg-muted/40 p-4 text-sm">
                <p className="font-medium">
                  Answer key suggestion: {item.answer_key_result.score}/{item.answer_key_result.max_score}
                </p>
                <p className="text-muted-foreground">
                  Answered {item.answer_key_result.answered_questions} of {item.answer_key_result.total_questions} question(s)
                </p>
              </div>
            ) : null}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Decision</CardTitle>
            <CardDescription>Approve, override, reject, or send back for re-grading.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid gap-3 md:grid-cols-2">
              <div className="space-y-2">
                <Label>Final score</Label>
                <Input type="number" value={score} onChange={(event) => setScore(event.target.value)} />
              </div>
              <div className="space-y-2">
                <Label>AI confidence</Label>
                <Input readOnly value={item.ai_confidence != null ? item.ai_confidence.toFixed(2) : '—'} />
              </div>
            </div>

            <div className="space-y-2">
              <Label>AI feedback</Label>
              <Textarea value={feedback} onChange={(event) => setFeedback(event.target.value)} />
            </div>
            <div className="space-y-2">
              <Label>Reviewer notes</Label>
              <Textarea value={notes} onChange={(event) => setNotes(event.target.value)} />
            </div>
            <div className="space-y-2">
              <Label>Override reason</Label>
              <Input value={overrideReason} onChange={(event) => setOverrideReason(event.target.value)} placeholder="Why are you changing or approving this grade?" />
            </div>
            <div className="space-y-2">
              <Label>Reject reason / resubmission note</Label>
              <Textarea value={rejectReason} onChange={(event) => setRejectReason(event.target.value)} />
            </div>
            <div className="space-y-2">
              <Label>Assign reviewer</Label>
              <div className="flex gap-2">
                <Select value={assignee} onValueChange={setAssignee}>
                  <SelectTrigger className="min-w-56"><SelectValue placeholder="Select reviewer" /></SelectTrigger>
                  <SelectContent>
                    {reviewers.map((reviewer) => (
                      <SelectItem key={reviewer.user_id} value={String(reviewer.user_id)}>
                        {reviewer.display_name} · {label(reviewer.role)}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <Button
                  variant="outline"
                  disabled={!assignee || saving}
                  onClick={() => void runAction(() => api.assignReview(item.id, { assigned_to_user_id: Number(assignee) }))}
                >
                  Assign
                </Button>
              </div>
            </div>

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
                Approve / save
              </Button>
              <Button
                variant="secondary"
                disabled={saving}
                onClick={() => void runAction(() => api.regradeReview(item.id, { reason: rejectReason || notes || undefined }))}
              >
                Re-grade
              </Button>
              <Button
                variant="destructive"
                disabled={saving}
                onClick={() => void runAction(() => api.rejectReview(item.id, { reason: rejectReason || undefined, notes: notes || undefined }))}
              >
                Reject / request resubmission
              </Button>
            </div>

            <div className="rounded-lg border p-3 text-sm">
              <p className="font-medium">Assignment</p>
              <p className="text-muted-foreground">{item.assignment_title || 'Unknown assignment'}</p>
              <p className="mt-2 font-medium">Assigned reviewer</p>
              <p className="text-muted-foreground">{item.assigned_to_name || 'Unassigned'}</p>
              <p className="mt-2 font-medium">Last review note</p>
              <p className="text-muted-foreground">{item.reviewer_notes || item.manual_review_reason || 'No notes yet.'}</p>
            </div>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Review comments</CardTitle>
          <CardDescription>Parents and tutors can leave notes for co-review and override decisions.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-3">
            {item.comments.length ? (
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
              <p className="text-sm text-muted-foreground">No comments yet.</p>
            )}
          </div>
          <div className="space-y-2">
            <Label>Add comment</Label>
            <Textarea value={comment} onChange={(event) => setComment(event.target.value)} placeholder="Leave a note for another parent or tutor…" />
            <Button variant="outline" disabled={saving || !comment.trim()} onClick={() => void submitComment()}>
              Add comment
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
