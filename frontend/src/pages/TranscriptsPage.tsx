import { useCallback, useEffect, useMemo, useState } from 'react'
import { Download, FileText, RefreshCcw } from 'lucide-react'
import { api } from '@/lib/api'
import { useAuth } from '@/context/AuthContext'
import type { Student, Transcript, TranscriptEntry, TranscriptSummary } from '@/types/api'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { EmptyState } from '@/components/common/EmptyState'
import { ErrorState } from '@/components/common/ErrorState'
import { LoadingState } from '@/components/common/LoadingState'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Textarea } from '@/components/ui/textarea'

type EntryDraft = {
  credits: string
  is_honors: boolean
  is_ap: boolean
  notes: string
  subject_name: string
}

function statusVariant(status: TranscriptSummary['status']) {
  if (status === 'final') return 'default'
  if (status === 'archived') return 'secondary'
  return 'outline'
}

function formatGpa(value?: number | null) {
  return value === null || value === undefined ? '—' : value.toFixed(2)
}

function formatCredits(value?: number | null) {
  return value === null || value === undefined ? '—' : value.toFixed(2)
}

export function TranscriptsPage() {
  const { canManageGrading, role, studentId } = useAuth()
  const [students, setStudents] = useState<Student[]>([])
  const [transcripts, setTranscripts] = useState<TranscriptSummary[]>([])
  const [selectedStudentId, setSelectedStudentId] = useState<number | null>(null)
  const [selectedTranscriptId, setSelectedTranscriptId] = useState<number | null>(null)
  const [transcript, setTranscript] = useState<Transcript | null>(null)
  const [notesDraft, setNotesDraft] = useState('')
  const [entryDrafts, setEntryDrafts] = useState<Record<number, EntryDraft>>({})
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [statusMessage, setStatusMessage] = useState('')

  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const studentData = await api.listStudents()
      const resolvedStudentId =
        studentId && studentData.some((student) => student.id === studentId)
          ? studentId
          : selectedStudentId && studentData.some((student) => student.id === selectedStudentId)
            ? selectedStudentId
            : studentData[0]?.id || null
      setStudents(studentData)
      setSelectedStudentId(resolvedStudentId)

      if (!resolvedStudentId) {
        setTranscripts([])
        setSelectedTranscriptId(null)
        setTranscript(null)
        return
      }

      const transcriptData = await api.listTranscripts({ student_id: resolvedStudentId })
      setTranscripts(transcriptData)
      const nextSelectedId =
        selectedTranscriptId && transcriptData.some((item) => item.id === selectedTranscriptId)
          ? selectedTranscriptId
          : transcriptData[0]?.id || null
      setSelectedTranscriptId(nextSelectedId)
      if (nextSelectedId) {
        setTranscript(await api.getTranscript(nextSelectedId))
      } else {
        setTranscript(null)
      }
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : 'Unable to load transcripts')
    } finally {
      setLoading(false)
    }
  }, [selectedStudentId, selectedTranscriptId, studentId])

  const loadSelectedTranscript = useCallback(async (transcriptId: number | null) => {
    if (!transcriptId) {
      setTranscript(null)
      return
    }
    setTranscript(await api.getTranscript(transcriptId))
  }, [])

  useEffect(() => {
    void load()
  }, [load])

  useEffect(() => {
    if (!transcript) {
      setNotesDraft('')
      setEntryDrafts({})
      return
    }
    setNotesDraft(transcript.notes || '')
    setEntryDrafts(
      transcript.entries.reduce<Record<number, EntryDraft>>((accumulator, entry) => {
        accumulator[entry.id] = {
          credits: String(entry.credits ?? 0),
          is_honors: entry.is_honors,
          is_ap: entry.is_ap,
          notes: entry.notes || '',
          subject_name: entry.subject_name,
        }
        return accumulator
      }, {}),
    )
  }, [transcript])

  const entriesByYear = useMemo(() => {
    if (!transcript) return []
    const grouped = new Map<string, TranscriptEntry[]>()
    transcript.entries.forEach((entry) => {
      const current = grouped.get(entry.school_year_name) || []
      current.push(entry)
      grouped.set(entry.school_year_name, current)
    })
    return Array.from(grouped.entries())
  }, [transcript])

  const canEditDraft = canManageGrading && transcript?.status === 'draft'

  const refreshData = async () => {
    await load()
    if (selectedTranscriptId) {
      await loadSelectedTranscript(selectedTranscriptId)
    }
  }

  const generate = async () => {
    if (!selectedStudentId) return
    setSaving(true)
    setStatusMessage('')
    setError('')
    try {
      const generated = await api.generateTranscript({ student_id: selectedStudentId })
      setSelectedTranscriptId(generated.id)
      setTranscript(generated)
      setStatusMessage('Draft transcript generated.')
      await load()
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : 'Unable to generate transcript')
    } finally {
      setSaving(false)
    }
  }

  const saveDraft = async () => {
    if (!transcript) return
    setSaving(true)
    setStatusMessage('')
    setError('')
    try {
      const updated = await api.updateTranscript(transcript.id, {
        notes: notesDraft,
        entries: transcript.entries.map((entry) => ({
          entry_id: entry.id,
          credits: Number.parseFloat(entryDrafts[entry.id]?.credits || '0') || 0,
          is_honors: entryDrafts[entry.id]?.is_honors || false,
          is_ap: entryDrafts[entry.id]?.is_ap || false,
          notes: entryDrafts[entry.id]?.notes || '',
          subject_name: entryDrafts[entry.id]?.subject_name || entry.subject_name,
        })),
      })
      setTranscript(updated)
      setStatusMessage('Draft saved.')
      await load()
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : 'Unable to save transcript')
    } finally {
      setSaving(false)
    }
  }

  const finalize = async () => {
    if (!transcript) return
    setSaving(true)
    setStatusMessage('')
    setError('')
    try {
      const finalized = await api.finalizeTranscript(transcript.id)
      setTranscript(finalized)
      setStatusMessage('Transcript finalized.')
      await load()
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : 'Unable to finalize transcript')
    } finally {
      setSaving(false)
    }
  }

  const downloadPdf = (id: number) => {
    window.open(api.getTranscriptPdfUrl(id), '_blank', 'noopener,noreferrer')
  }

  if (loading) return <LoadingState message="Loading transcripts…" />
  if (error && !students.length) return <ErrorState message={error} onRetry={() => void load()} />
  if (!students.length) return <EmptyState title="No students yet" description="Add a student before generating transcripts." />

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <CardTitle>Transcripts</CardTitle>
          <CardDescription>Generate cumulative transcripts, adjust credits and course levels, then export a polished PDF.</CardDescription>
        </CardHeader>
        <CardContent className="grid gap-4 lg:grid-cols-[1fr,auto]">
          <div className="space-y-2">
            <Label>Student</Label>
            <Select value={selectedStudentId ? String(selectedStudentId) : ''} onValueChange={(value) => setSelectedStudentId(Number(value))}>
              <SelectTrigger>
                <SelectValue placeholder="Choose a student" />
              </SelectTrigger>
              <SelectContent>
                {students.map((student) => (
                  <SelectItem key={student.id} value={String(student.id)}>
                    {student.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="flex items-end gap-2">
            {canManageGrading ? (
              <Button onClick={() => void generate()} disabled={saving || !selectedStudentId}>
                <FileText className="mr-2 h-4 w-4" />
                Generate
              </Button>
            ) : null}
            <Button variant="outline" onClick={() => void refreshData()} disabled={saving}>
              <RefreshCcw className="mr-2 h-4 w-4" />
              Refresh
            </Button>
          </div>
        </CardContent>
      </Card>

      <div className="grid gap-4 xl:grid-cols-[1.05fr,1.75fr]">
        <Card>
          <CardHeader>
            <CardTitle>Generated transcripts</CardTitle>
            <CardDescription>{selectedStudentId ? 'Most recent transcript appears first.' : 'Choose a student to begin.'}</CardDescription>
          </CardHeader>
          <CardContent>
            {transcripts.length ? (
              <div className="space-y-3">
                {transcripts.map((item) => (
                  <button
                    key={item.id}
                    type="button"
                    className={`w-full rounded-lg border p-4 text-left transition hover:bg-muted/50 ${
                      selectedTranscriptId === item.id ? 'border-primary bg-primary/5' : ''
                    }`}
                    onClick={() => {
                      setSelectedTranscriptId(item.id)
                      void loadSelectedTranscript(item.id)
                    }}
                  >
                    <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
                      <div>
                        <p className="font-semibold">{item.student_name}</p>
                        <p className="text-sm text-muted-foreground">{new Date(item.generated_at).toLocaleString()}</p>
                      </div>
                      <Badge variant={statusVariant(item.status)}>{item.status}</Badge>
                    </div>
                    <div className="flex flex-wrap gap-4 text-sm text-muted-foreground">
                      <span>GPA {formatGpa(item.cumulative_gpa)}</span>
                      <span>Weighted {formatGpa(item.weighted_gpa)}</span>
                      <span>{formatCredits(item.total_credits)} credits</span>
                    </div>
                  </button>
                ))}
              </div>
            ) : (
              <EmptyState
                title="No transcripts yet"
                description={canManageGrading ? 'Generate a cumulative transcript for the selected student.' : 'No transcripts are available yet.'}
              />
            )}
          </CardContent>
        </Card>

        <div className="space-y-4">
          <Card>
            <CardHeader>
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <CardTitle>Transcript detail</CardTitle>
                  <CardDescription>
                    {transcript ? `${transcript.student_name} · ${transcript.entries.length} course entries` : 'Select a transcript to review.'}
                  </CardDescription>
                </div>
                {transcript ? (
                  <div className="flex flex-wrap gap-2">
                    <Badge variant={statusVariant(transcript.status)}>{transcript.status}</Badge>
                    <Button variant="outline" onClick={() => downloadPdf(transcript.id)}>
                      <Download className="mr-2 h-4 w-4" />
                      PDF
                    </Button>
                    {canEditDraft ? (
                      <>
                        <Button variant="outline" onClick={() => void saveDraft()} disabled={saving}>
                          Save draft
                        </Button>
                        <Button onClick={() => void finalize()} disabled={saving}>
                          Finalize
                        </Button>
                      </>
                    ) : null}
                  </div>
                ) : null}
              </div>
            </CardHeader>
            <CardContent className="space-y-4">
              {transcript ? (
                <>
                  <div className="grid gap-3 md:grid-cols-4">
                    <div className="rounded-lg border p-3">
                      <p className="text-sm text-muted-foreground">Cumulative GPA</p>
                      <p className="text-2xl font-semibold">{formatGpa(transcript.cumulative_gpa)}</p>
                    </div>
                    <div className="rounded-lg border p-3">
                      <p className="text-sm text-muted-foreground">Weighted GPA</p>
                      <p className="text-2xl font-semibold">{formatGpa(transcript.weighted_gpa)}</p>
                    </div>
                    <div className="rounded-lg border p-3">
                      <p className="text-sm text-muted-foreground">Total credits</p>
                      <p className="text-2xl font-semibold">{formatCredits(transcript.total_credits)}</p>
                    </div>
                    <div className="rounded-lg border p-3">
                      <p className="text-sm text-muted-foreground">Class rank</p>
                      <p className="text-2xl font-semibold">
                        {transcript.class_rank && transcript.class_size ? `${transcript.class_rank}/${transcript.class_size}` : 'N/A'}
                      </p>
                    </div>
                  </div>

                  <div className="grid gap-3 md:grid-cols-3">
                    <div className="rounded-lg border p-3">
                      <p className="text-sm text-muted-foreground">Honors weight</p>
                      <p className="font-medium">+{transcript.honors_weight_bonus.toFixed(2)}</p>
                    </div>
                    <div className="rounded-lg border p-3">
                      <p className="text-sm text-muted-foreground">AP weight</p>
                      <p className="font-medium">+{transcript.ap_weight_bonus.toFixed(2)}</p>
                    </div>
                    <div className="rounded-lg border p-3">
                      <p className="text-sm text-muted-foreground">Generated by</p>
                      <p className="font-medium">{transcript.generated_by_name || role || '—'}</p>
                    </div>
                  </div>

                  <div className="space-y-2">
                    <Label>Transcript notes</Label>
                    <Textarea value={notesDraft} onChange={(event) => setNotesDraft(event.target.value)} readOnly={!canEditDraft} rows={3} />
                  </div>

                  {entriesByYear.map(([yearName, entries]) => (
                    <Card key={yearName}>
                      <CardHeader className="pb-3">
                        <CardTitle className="text-lg">{yearName}</CardTitle>
                        <CardDescription>{entries.length} course entries</CardDescription>
                      </CardHeader>
                      <CardContent className="space-y-4">
                        <Table>
                          <TableHeader>
                            <TableRow>
                              <TableHead>Course</TableHead>
                              <TableHead>Credits</TableHead>
                              <TableHead>Grade</TableHead>
                              <TableHead>GPA</TableHead>
                              <TableHead>Weighted</TableHead>
                              <TableHead>Level</TableHead>
                            </TableRow>
                          </TableHeader>
                          <TableBody>
                            {entries.map((entry) => (
                              <TableRow key={entry.id}>
                                <TableCell className="font-medium">{entryDrafts[entry.id]?.subject_name || entry.subject_name}</TableCell>
                                <TableCell>{formatCredits(Number.parseFloat(entryDrafts[entry.id]?.credits || String(entry.credits)))}</TableCell>
                                <TableCell>{entry.letter_grade || '—'}</TableCell>
                                <TableCell>{formatGpa(entry.gpa_points)}</TableCell>
                                <TableCell>{formatGpa(entry.weighted_gpa_points)}</TableCell>
                                <TableCell>
                                  {entryDrafts[entry.id]?.is_ap ? 'AP' : entryDrafts[entry.id]?.is_honors ? 'Honors' : 'Standard'}
                                </TableCell>
                              </TableRow>
                            ))}
                          </TableBody>
                        </Table>

                        <div className="grid gap-4">
                          {entries.map((entry) => (
                            <div key={entry.id} className="rounded-lg border p-4">
                              <div className="grid gap-4 md:grid-cols-[2fr,1fr,auto,auto]">
                                <div className="space-y-2">
                                  <Label>Course name</Label>
                                  <Input
                                    value={entryDrafts[entry.id]?.subject_name || entry.subject_name}
                                    onChange={(event) =>
                                      setEntryDrafts((current) => ({
                                        ...current,
                                        [entry.id]: { ...(current[entry.id] || entryDrafts[entry.id]), subject_name: event.target.value },
                                      }))
                                    }
                                    readOnly={!canEditDraft}
                                  />
                                </div>
                                <div className="space-y-2">
                                  <Label>Credits</Label>
                                  <Input
                                    type="number"
                                    min="0"
                                    step="0.25"
                                    value={entryDrafts[entry.id]?.credits || String(entry.credits)}
                                    onChange={(event) =>
                                      setEntryDrafts((current) => ({
                                        ...current,
                                        [entry.id]: { ...(current[entry.id] || entryDrafts[entry.id]), credits: event.target.value },
                                      }))
                                    }
                                    readOnly={!canEditDraft}
                                  />
                                </div>
                                <label className="flex items-end gap-2 text-sm">
                                  <input
                                    type="checkbox"
                                    className="mb-2 h-4 w-4"
                                    checked={entryDrafts[entry.id]?.is_honors || false}
                                    onChange={(event) =>
                                      setEntryDrafts((current) => ({
                                        ...current,
                                        [entry.id]: { ...(current[entry.id] || entryDrafts[entry.id]), is_honors: event.target.checked },
                                      }))
                                    }
                                    disabled={!canEditDraft}
                                  />
                                  Honors
                                </label>
                                <label className="flex items-end gap-2 text-sm">
                                  <input
                                    type="checkbox"
                                    className="mb-2 h-4 w-4"
                                    checked={entryDrafts[entry.id]?.is_ap || false}
                                    onChange={(event) =>
                                      setEntryDrafts((current) => ({
                                        ...current,
                                        [entry.id]: { ...(current[entry.id] || entryDrafts[entry.id]), is_ap: event.target.checked },
                                      }))
                                    }
                                    disabled={!canEditDraft}
                                  />
                                  AP
                                </label>
                              </div>
                              <div className="mt-4 space-y-2">
                                <Label>Entry notes</Label>
                                <Textarea
                                  value={entryDrafts[entry.id]?.notes || ''}
                                  onChange={(event) =>
                                    setEntryDrafts((current) => ({
                                      ...current,
                                      [entry.id]: { ...(current[entry.id] || entryDrafts[entry.id]), notes: event.target.value },
                                    }))
                                  }
                                  readOnly={!canEditDraft}
                                  rows={2}
                                />
                              </div>
                            </div>
                          ))}
                        </div>
                      </CardContent>
                    </Card>
                  ))}
                </>
              ) : (
                <p className="text-sm text-muted-foreground">Choose a generated transcript to see course history, credits, and GPA totals.</p>
              )}

              {statusMessage ? <p className="text-sm text-emerald-600">{statusMessage}</p> : null}
              {error ? <p className="text-sm text-destructive">{error}</p> : null}
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  )
}
