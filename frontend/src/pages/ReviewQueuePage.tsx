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
    }
  }, [activeItem])

  const submitDecision = async (action: ReviewAction) => {
    if (!activeItem) return

    await api.submitReviewDecision(activeItem.id, {
      action,
      score: score ? Number(score) : undefined,
      feedback,
      notes,
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
                <Textarea value={activeItem.ocr_text || ''} readOnly className="min-h-[380px]" />
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

            <div className="space-y-2">
              <Label>Feedback</Label>
              <Textarea value={feedback} onChange={(event) => setFeedback(event.target.value)} />
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
