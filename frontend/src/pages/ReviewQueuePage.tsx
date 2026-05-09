import { useEffect, useState } from 'react'
import { api } from '@/lib/api'
import { useCapabilities } from '@/context/CapabilitiesContext'
import type { ReviewAction, ReviewQueueItem } from '@/types/api'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { Badge } from '@/components/ui/badge'
import { LoadingState } from '@/components/common/LoadingState'
import { ErrorState } from '@/components/common/ErrorState'
import { EmptyState } from '@/components/common/EmptyState'

export function ReviewQueuePage() {
  const [queue, setQueue] = useState<ReviewQueueItem[]>([])
  const [activeId, setActiveId] = useState<number | null>(null)
  const [score, setScore] = useState('')
  const [feedback, setFeedback] = useState('')
  const [notes, setNotes] = useState('')
  const [overrideReason, setOverrideReason] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const { capabilities } = useCapabilities()

  const load = async () => {
    setLoading(true)
    setError('')
    try {
      const data = await api.listReviewQueue()
      setQueue(data)
      if (data[0]) {
        setActiveId(data[0].id)
      }
    } catch (queueError) {
      setError(queueError instanceof Error ? queueError.message : 'Unable to load review queue')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void load()
  }, [])

  const activeItem = queue.find((item) => item.id === activeId)

  useEffect(() => {
    if (activeItem) {
      setScore(activeItem.ai_grade != null ? String(activeItem.ai_grade) : '')
      setFeedback(activeItem.ai_feedback || '')
      setNotes('')
      setOverrideReason(activeItem.manual_review_reason || '')
    }
  }, [activeItem])

  const submitDecision = async (action: ReviewAction) => {
    if (!activeItem) return

    await api.submitReviewDecision(activeItem.id, {
      action,
      score: score ? Number(score) : undefined,
      feedback,
      notes,
      override_reason: overrideReason || undefined,
    })

    const next = queue.filter((item) => item.id !== activeItem.id)
    setQueue(next)
    setActiveId(next[0]?.id || null)
  }

  if (loading) return <LoadingState message="Loading review queue…" />
  if (error) return <ErrorState message={error} onRetry={() => void load()} />
  if (!queue.length) return <EmptyState title="Review queue is clear" description="No AI grades are waiting for your review." />

  return (
    <div className="grid gap-4 lg:grid-cols-4">
      <Card className="lg:col-span-1">
        <CardHeader>
          <CardTitle>Queue items</CardTitle>
          <CardDescription>{queue.length} pending</CardDescription>
        </CardHeader>
        <CardContent className="space-y-2">
          {queue.map((item) => (
            <button
              key={item.id}
              type="button"
              onClick={() => setActiveId(item.id)}
              className={`w-full rounded-md border p-3 text-left text-sm ${activeId === item.id ? 'border-primary bg-primary/10' : ''}`}
            >
              <p className="font-semibold">{item.assignment_title || `Submission #${item.submission_id || item.id}`}</p>
              <p className="text-xs text-muted-foreground">{item.student_name || 'Unknown student'}</p>
              <Badge variant="secondary" className="mt-2">
                AI confidence {(item.ai_confidence ?? 0).toFixed(2)}
              </Badge>
              <p className="mt-2 text-xs text-muted-foreground">{item.status.replace(/_/g, ' ')}</p>
            </button>
          ))}
        </CardContent>
      </Card>

      {activeItem ? (
        <Card className="lg:col-span-3">
          <CardHeader>
            <CardTitle>Human review</CardTitle>
            <CardDescription>Review OCR text and AI suggestion before finalizing.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid gap-4 md:grid-cols-2">
              <div className="space-y-2">
                <h3 className="text-sm font-semibold">Original submission</h3>
                {activeItem.file_url || activeItem.file_path ? (
                  <img
                    alt="Original submission"
                    src={activeItem.file_url || activeItem.file_path}
                    className="max-h-[380px] w-full rounded-md border object-contain"
                  />
                ) : (
                  <div className="rounded-md border border-dashed p-6 text-sm text-muted-foreground">
                    No image preview path returned by API.
                  </div>
                )}
              </div>
              <div className="space-y-2">
                <h3 className="text-sm font-semibold">OCR text</h3>
                <Textarea value={activeItem.ocr_result || ''} readOnly className="min-h-[380px]" />
              </div>
            </div>

            <div className="grid gap-4 md:grid-cols-2">
              <div className="space-y-2">
                <Label>Final score</Label>
                <Input type="number" value={score} onChange={(event) => setScore(event.target.value)} />
              </div>
              <div className="space-y-2">
                <Label>AI confidence</Label>
                <Input readOnly value={String(activeItem.ai_confidence ?? '')} />
              </div>
            </div>

            {activeItem.answer_key_result ? (
              <div className="rounded-md border bg-muted/30 p-3 text-sm">
                <p className="font-medium">
                  Answer key suggestion: {activeItem.answer_key_result.score}/{activeItem.answer_key_result.max_score}
                </p>
                <p className="text-muted-foreground">
                  Answered {activeItem.answer_key_result.answered_questions} of {activeItem.answer_key_result.total_questions} question(s)
                </p>
                <div className="mt-3 space-y-2">
                  {activeItem.answer_key_result.questions.map((question) => (
                    <div key={question.question_number} className="rounded-md bg-background p-2">
                      <p className="font-medium">Question {question.question_number}</p>
                      <p className="text-xs text-muted-foreground">Expected: {question.correct_answer}</p>
                      <p className="text-xs text-muted-foreground">Student: {question.student_answer || 'No answer detected'}</p>
                      <p className="text-xs text-muted-foreground">
                        Awarded {question.awarded_points}/{question.points} point(s)
                      </p>
                    </div>
                  ))}
                </div>
              </div>
            ) : null}

            <div className="space-y-2">
              <Label>Feedback</Label>
              <Textarea value={feedback} onChange={(event) => setFeedback(event.target.value)} />
            </div>
            <div className="space-y-2">
              <Label>Override reason</Label>
              <Input value={overrideReason} onChange={(event) => setOverrideReason(event.target.value)} placeholder="Why are you approving, adjusting, or re-queuing this grade?" />
            </div>
            <div className="space-y-2">
              <Label>Review notes</Label>
              <Textarea value={notes} onChange={(event) => setNotes(event.target.value)} />
            </div>

            <div className="flex flex-wrap gap-2">
              <Button onClick={() => void submitDecision('approve')}>Approve AI grade</Button>
              <Button variant="secondary" onClick={() => void submitDecision('modify')}>
                Save modifications
              </Button>
              <Button
                variant="destructive"
                onClick={() => void submitDecision('reject')}
                disabled={!capabilities.ai_grading.enabled}
              >
                Reject and re-grade
              </Button>
            </div>
            {!capabilities.ai_grading.enabled ? (
              <p className="text-sm text-muted-foreground">
                Re-grade is disabled because AI grading is currently unavailable.
              </p>
            ) : null}
          </CardContent>
        </Card>
      ) : null}
    </div>
  )
}
