import { type DragEvent, useCallback, useEffect, useMemo, useState } from 'react'
import { BookOpenText, Camera, Flag, Grip, Images, Link2, Pencil, Plus, Save, Share2, Trash2 } from 'lucide-react'
import { api } from '@/lib/api'
import type {
  Assignment,
  PortfolioCollection,
  PortfolioEntry,
  PortfolioEntryPayload,
  PortfolioEntryType,
  Student,
  Subject,
  Submission,
} from '@/types/api'
import { useAuth } from '@/context/AuthContext'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { EmptyState } from '@/components/common/EmptyState'
import { ErrorState } from '@/components/common/ErrorState'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { LoadingState } from '@/components/common/LoadingState'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Textarea } from '@/components/ui/textarea'

const entryTypeOptions: Array<{ value: PortfolioEntryType; label: string; icon: typeof BookOpenText }> = [
  { value: 'work_sample', label: 'Work sample', icon: Images },
  { value: 'journal', label: 'Journal', icon: BookOpenText },
  { value: 'milestone', label: 'Milestone', icon: Flag },
  { value: 'photo', label: 'Photo', icon: Camera },
  { value: 'note', label: 'Note', icon: Pencil },
]

type EntryFormState = {
  entry_type: PortfolioEntryType
  title: string
  description: string
  date: string
  subject_id: string
  assignment_id: string
  submission_id: string
  tags: string
  files: File[]
}

type CollectionFormState = {
  name: string
  description: string
  entry_ids: number[]
  is_public: boolean
}

function emptyEntryForm(): EntryFormState {
  return {
    entry_type: 'work_sample',
    title: '',
    description: '',
    date: new Date().toISOString().slice(0, 10),
    subject_id: 'none',
    assignment_id: 'none',
    submission_id: 'none',
    tags: '',
    files: [],
  }
}

function emptyCollectionForm(): CollectionFormState {
  return {
    name: '',
    description: '',
    entry_ids: [],
    is_public: false,
  }
}

function splitTags(value: string) {
  return value
    .split(',')
    .map((item) => item.trim().toLowerCase())
    .filter(Boolean)
}

function entryTypeLabel(type: PortfolioEntryType) {
  return entryTypeOptions.find((option) => option.value === type)?.label || type
}

function formatDateLabel(value: string) {
  return new Date(value).toLocaleDateString()
}

export function PortfolioPage() {
  const { studentId: scopedStudentId } = useAuth()
  const [students, setStudents] = useState<Student[]>([])
  const [subjects, setSubjects] = useState<Subject[]>([])
  const [assignments, setAssignments] = useState<Assignment[]>([])
  const [submissions, setSubmissions] = useState<Submission[]>([])
  const [entries, setEntries] = useState<PortfolioEntry[]>([])
  const [collections, setCollections] = useState<PortfolioCollection[]>([])
  const [selectedStudentId, setSelectedStudentId] = useState<number | null>(scopedStudentId)
  const [selectedEntryId, setSelectedEntryId] = useState<number | null>(null)
  const [editingEntryId, setEditingEntryId] = useState<number | null>(null)
  const [editingCollectionId, setEditingCollectionId] = useState<number | null>(null)
  const [entryForm, setEntryForm] = useState<EntryFormState>(emptyEntryForm())
  const [collectionForm, setCollectionForm] = useState<CollectionFormState>(emptyCollectionForm())
  const [filters, setFilters] = useState({
    type: 'all',
    subject_id: 'all',
    date_from: '',
    date_to: '',
    tags: '',
    view: 'grid',
  })
  const [shareUrl, setShareUrl] = useState('')
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  const loadMetadata = useCallback(async () => {
    const [studentData, subjectData, assignmentData, submissionData] = await Promise.all([
      api.listStudents(),
      api.listSubjects(),
      api.listAssignments({ page: 1, page_size: 100 }),
      api.listSubmissions(),
    ])
    setStudents(studentData)
    setSubjects(subjectData)
    setAssignments(assignmentData.items)
    setSubmissions(submissionData)
    const fallbackStudentId = scopedStudentId ?? studentData[0]?.id ?? null
    setSelectedStudentId((current) => current ?? fallbackStudentId)
  }, [scopedStudentId])

  const loadPortfolio = useCallback(async () => {
    if (!selectedStudentId) {
      setEntries([])
      setCollections([])
      setLoading(false)
      return
    }
    setLoading(true)
    setError('')
    try {
      const [entryData, collectionData] = await Promise.all([
        api.listPortfolioEntries(selectedStudentId, {
          type: filters.type as PortfolioEntryType | 'all',
          subject_id: filters.subject_id === 'all' ? undefined : Number(filters.subject_id),
          date_from: filters.date_from || undefined,
          date_to: filters.date_to || undefined,
          tags: filters.tags || undefined,
        }),
        api.listPortfolioCollections(selectedStudentId),
      ])
      setEntries(entryData)
      setCollections(collectionData)
      setSelectedEntryId((current) => current ?? entryData[0]?.id ?? null)
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : 'Unable to load portfolio')
    } finally {
      setLoading(false)
    }
  }, [filters.date_from, filters.date_to, filters.subject_id, filters.tags, filters.type, selectedStudentId])

  useEffect(() => {
    void loadMetadata()
  }, [loadMetadata])

  useEffect(() => {
    void loadPortfolio()
  }, [loadPortfolio])

  const selectedEntry = useMemo(
    () => entries.find((entry) => entry.id === selectedEntryId) ?? entries[0] ?? null,
    [entries, selectedEntryId],
  )

  const journalEntries = useMemo(
    () => entries.filter((entry) => entry.entry_type === 'journal'),
    [entries],
  )

  const availableAssignments = useMemo(
    () =>
      assignments.filter(
        (assignment) =>
          entryForm.subject_id === 'none' || assignment.subject_id === Number(entryForm.subject_id),
      ),
    [assignments, entryForm.subject_id],
  )

  const availableSubmissions = useMemo(
    () =>
      submissions.filter(
        (submission) =>
          submission.student_id === selectedStudentId &&
          (entryForm.assignment_id === 'none' || submission.assignment_id === Number(entryForm.assignment_id)),
      ),
    [entryForm.assignment_id, selectedStudentId, submissions],
  )

  const entryCountByType = useMemo(
    () =>
      Object.fromEntries(
        entryTypeOptions.map((option) => [option.value, entries.filter((entry) => entry.entry_type === option.value).length]),
      ),
    [entries],
  )

  const resetEntryForm = () => {
    setEditingEntryId(null)
    setEntryForm(emptyEntryForm())
  }

  const resetCollectionForm = () => {
    setEditingCollectionId(null)
    setCollectionForm(emptyCollectionForm())
    setShareUrl('')
  }

  const saveEntry = async () => {
    if (!selectedStudentId || !entryForm.title.trim()) return
    setSaving(true)
    setError('')
    try {
      const payload: PortfolioEntryPayload = {
        student_id: selectedStudentId,
        entry_type: entryForm.entry_type,
        title: entryForm.title.trim(),
        description: entryForm.description.trim() || undefined,
        date: entryForm.date,
        subject_id: entryForm.subject_id !== 'none' ? Number(entryForm.subject_id) : undefined,
        assignment_id: entryForm.assignment_id !== 'none' ? Number(entryForm.assignment_id) : undefined,
        submission_id: entryForm.submission_id !== 'none' ? Number(entryForm.submission_id) : undefined,
        tags: splitTags(entryForm.tags),
      }
      const saved = editingEntryId
        ? await api.updatePortfolioEntry(editingEntryId, payload)
        : await api.createPortfolioEntry(payload)

      if (entryForm.files.length) {
        await api.attachPortfolioEntryFiles(saved.id, entryForm.files)
      }

      resetEntryForm()
      await loadPortfolio()
      setSelectedEntryId(saved.id)
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : 'Unable to save entry')
    } finally {
      setSaving(false)
    }
  }

  const saveCollection = async () => {
    if (!selectedStudentId || !collectionForm.name.trim()) return
    setSaving(true)
    setError('')
    try {
      const payload = {
        student_id: selectedStudentId,
        name: collectionForm.name.trim(),
        description: collectionForm.description.trim() || undefined,
        entry_ids: collectionForm.entry_ids,
        is_public: collectionForm.is_public,
      }
      const collection = editingCollectionId
        ? await api.updatePortfolioCollection(editingCollectionId, payload)
        : await api.createPortfolioCollection(payload)
      setEditingCollectionId(collection.id)
      await loadPortfolio()
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : 'Unable to save collection')
    } finally {
      setSaving(false)
    }
  }

  const startEditingEntry = (entry: PortfolioEntry) => {
    setEditingEntryId(entry.id)
    setEntryForm({
      entry_type: entry.entry_type,
      title: entry.title,
      description: entry.description || '',
      date: entry.date,
      subject_id: entry.subject_id ? String(entry.subject_id) : 'none',
      assignment_id: entry.assignment_id ? String(entry.assignment_id) : 'none',
      submission_id: entry.submission_id ? String(entry.submission_id) : 'none',
      tags: entry.tags.join(', '),
      files: [],
    })
  }

  const startEditingCollection = (collection: PortfolioCollection) => {
    setEditingCollectionId(collection.id)
    setCollectionForm({
      name: collection.name,
      description: collection.description || '',
      entry_ids: collection.entry_ids,
      is_public: collection.is_public,
    })
    setShareUrl(collection.share_token ? `${window.location.origin}/portfolio/share/${collection.share_token}` : '')
  }

  const addEntryToCollection = (entryId: number) => {
    setCollectionForm((current) => ({
      ...current,
      entry_ids: current.entry_ids.includes(entryId) ? current.entry_ids : [...current.entry_ids, entryId],
    }))
  }

  const removeEntryFromCollection = (entryId: number) => {
    setCollectionForm((current) => ({
      ...current,
      entry_ids: current.entry_ids.filter((id) => id !== entryId),
    }))
  }

  const handleDrop = (event: DragEvent<HTMLDivElement>) => {
    event.preventDefault()
    const entryId = Number(event.dataTransfer.getData('text/plain'))
    if (entryId) {
      addEntryToCollection(entryId)
    }
  }

  if (loading) return <LoadingState message="Loading portfolio…" />
  if (error) return <ErrorState message={error} onRetry={() => void loadPortfolio()} />

  if (!students.length) {
    return <EmptyState title="No students yet" description="Add a student before building a portfolio or journal." />
  }

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <CardTitle>Portfolio and learning journal</CardTitle>
          <CardDescription>Capture work samples, journal entries, milestones, photos, and curated share collections.</CardDescription>
        </CardHeader>
        <CardContent className="grid gap-3 md:grid-cols-2 xl:grid-cols-6">
          <div className="space-y-2">
            <Label>Student</Label>
            <Select value={String(selectedStudentId)} onValueChange={(value) => setSelectedStudentId(Number(value))}>
              <SelectTrigger>
                <SelectValue />
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
          <div className="space-y-2">
            <Label>Entry type</Label>
            <Select value={filters.type} onValueChange={(value) => setFilters((current) => ({ ...current, type: value }))}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All types</SelectItem>
                {entryTypeOptions.map((option) => (
                  <SelectItem key={option.value} value={option.value}>
                    {option.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-2">
            <Label>Subject</Label>
            <Select value={filters.subject_id} onValueChange={(value) => setFilters((current) => ({ ...current, subject_id: value }))}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All subjects</SelectItem>
                {subjects.map((subject) => (
                  <SelectItem key={subject.id} value={String(subject.id)}>
                    {subject.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-2">
            <Label>From</Label>
            <Input type="date" value={filters.date_from} onChange={(event) => setFilters((current) => ({ ...current, date_from: event.target.value }))} />
          </div>
          <div className="space-y-2">
            <Label>To</Label>
            <Input type="date" value={filters.date_to} onChange={(event) => setFilters((current) => ({ ...current, date_to: event.target.value }))} />
          </div>
          <div className="space-y-2">
            <Label>Tags</Label>
            <Input value={filters.tags} onChange={(event) => setFilters((current) => ({ ...current, tags: event.target.value }))} placeholder="science, journal" />
          </div>
        </CardContent>
      </Card>

      <div className="grid gap-4 xl:grid-cols-[1.15fr_0.85fr]">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between gap-3">
            <div>
              <CardTitle>Entries</CardTitle>
              <CardDescription>
                {entries.length} total · {journalEntries.length} journal entry{journalEntries.length === 1 ? '' : 'ies'}
              </CardDescription>
            </div>
            <div className="flex gap-2">
              <Button variant={filters.view === 'grid' ? 'default' : 'outline'} size="sm" onClick={() => setFilters((current) => ({ ...current, view: 'grid' }))}>
                Grid
              </Button>
              <Button variant={filters.view === 'list' ? 'default' : 'outline'} size="sm" onClick={() => setFilters((current) => ({ ...current, view: 'list' }))}>
                List
              </Button>
            </div>
          </CardHeader>
          <CardContent>
            {entries.length ? (
              <div className={filters.view === 'grid' ? 'grid gap-3 md:grid-cols-2' : 'space-y-3'}>
                {entries.map((entry) => {
                  const typeMeta = entryTypeOptions.find((option) => option.value === entry.entry_type)
                  const Icon = typeMeta?.icon || BookOpenText
                  return (
                    <button
                      key={entry.id}
                      type="button"
                      draggable
                      onDragStart={(event) => event.dataTransfer.setData('text/plain', String(entry.id))}
                      onClick={() => setSelectedEntryId(entry.id)}
                      className={`rounded-xl border p-4 text-left transition ${selectedEntry?.id === entry.id ? 'border-primary bg-primary/5' : 'hover:border-primary/40'}`}
                    >
                      <div className="mb-3 flex items-start justify-between gap-3">
                        <div className="flex items-center gap-2">
                          <Icon className="h-4 w-4 text-primary" />
                          <div>
                            <p className="font-medium">{entry.title}</p>
                            <p className="text-xs text-muted-foreground">{formatDateLabel(entry.date)}</p>
                          </div>
                        </div>
                        <Grip className="h-4 w-4 text-muted-foreground" />
                      </div>
                      <div className="mb-2 flex flex-wrap gap-2">
                        <Badge variant="secondary">{entryTypeLabel(entry.entry_type)}</Badge>
                        {entry.subject?.name ? <Badge variant="outline">{entry.subject.name}</Badge> : null}
                      </div>
                      <p className="line-clamp-3 text-sm text-muted-foreground">{entry.description || 'No description yet.'}</p>
                      <div className="mt-3 flex flex-wrap gap-1">
                        {entry.tags.map((tag) => (
                          <span key={tag} className="rounded-full bg-muted px-2 py-0.5 text-xs text-muted-foreground">
                            #{tag}
                          </span>
                        ))}
                      </div>
                    </button>
                  )
                })}
              </div>
            ) : (
              <EmptyState title="No portfolio entries yet" description="Add a work sample, photo, or journal entry to start building the record." />
            )}
          </CardContent>
        </Card>

        <div className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>{editingEntryId ? 'Edit entry' : 'Add entry'}</CardTitle>
              <CardDescription>Journal entries support markdown or HTML in the description field.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="grid gap-3 md:grid-cols-2">
                <div className="space-y-2">
                  <Label>Type</Label>
                  <Select value={entryForm.entry_type} onValueChange={(value: PortfolioEntryType) => setEntryForm((current) => ({ ...current, entry_type: value }))}>
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {entryTypeOptions.map((option) => (
                        <SelectItem key={option.value} value={option.value}>
                          {option.label} ({entryCountByType[option.value] || 0})
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-2">
                  <Label>Date</Label>
                  <Input type="date" value={entryForm.date} onChange={(event) => setEntryForm((current) => ({ ...current, date: event.target.value }))} />
                </div>
              </div>
              <div className="space-y-2">
                <Label>Title</Label>
                <Input value={entryForm.title} onChange={(event) => setEntryForm((current) => ({ ...current, title: event.target.value }))} placeholder="Week 8 science reflection" />
              </div>
              <div className="space-y-2">
                <Label>Description</Label>
                <Textarea value={entryForm.description} onChange={(event) => setEntryForm((current) => ({ ...current, description: event.target.value }))} className="min-h-32" placeholder="Use markdown headings, bullet lists, or rich HTML snippets." />
              </div>
              <div className="grid gap-3 md:grid-cols-3">
                <div className="space-y-2">
                  <Label>Subject</Label>
                  <Select value={entryForm.subject_id} onValueChange={(value) => setEntryForm((current) => ({ ...current, subject_id: value }))}>
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="none">None</SelectItem>
                      {subjects.map((subject) => (
                        <SelectItem key={subject.id} value={String(subject.id)}>
                          {subject.name}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-2">
                  <Label>Assignment</Label>
                  <Select value={entryForm.assignment_id} onValueChange={(value) => setEntryForm((current) => ({ ...current, assignment_id: value }))}>
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="none">None</SelectItem>
                      {availableAssignments.map((assignment) => (
                        <SelectItem key={assignment.id} value={String(assignment.id)}>
                          {assignment.title}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-2">
                  <Label>Submission</Label>
                  <Select value={entryForm.submission_id} onValueChange={(value) => setEntryForm((current) => ({ ...current, submission_id: value }))}>
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="none">None</SelectItem>
                      {availableSubmissions.map((submission) => (
                        <SelectItem key={submission.id} value={String(submission.id)}>
                          Submission #{submission.id} · v{submission.submission_version || 1}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              </div>
              <div className="space-y-2">
                <Label>Tags</Label>
                <Input value={entryForm.tags} onChange={(event) => setEntryForm((current) => ({ ...current, tags: event.target.value }))} placeholder="science, field-trip, journal" />
              </div>
              <div className="space-y-2">
                <Label>Attachments</Label>
                <Input type="file" multiple onChange={(event) => setEntryForm((current) => ({ ...current, files: Array.from(event.target.files || []) }))} />
              </div>
              <div className="flex flex-wrap gap-2">
                <Button onClick={() => void saveEntry()} disabled={saving}>
                  {editingEntryId ? <Save className="mr-2 h-4 w-4" /> : <Plus className="mr-2 h-4 w-4" />}
                  {editingEntryId ? 'Update entry' : 'Create entry'}
                </Button>
                {editingEntryId ? (
                  <Button variant="outline" onClick={resetEntryForm}>
                    Cancel
                  </Button>
                ) : null}
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Entry detail</CardTitle>
            </CardHeader>
            <CardContent>
              {selectedEntry ? (
                <div className="space-y-3">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div>
                      <p className="text-lg font-semibold">{selectedEntry.title}</p>
                      <p className="text-sm text-muted-foreground">{formatDateLabel(selectedEntry.date)}</p>
                    </div>
                    <Badge>{entryTypeLabel(selectedEntry.entry_type)}</Badge>
                  </div>
                  <p className="whitespace-pre-wrap text-sm text-muted-foreground">{selectedEntry.description || 'No description provided.'}</p>
                  <div className="flex flex-wrap gap-2">
                    {selectedEntry.subject?.name ? <Badge variant="outline">{selectedEntry.subject.name}</Badge> : null}
                    {selectedEntry.assignment?.title ? <Badge variant="secondary">Assignment: {selectedEntry.assignment.title}</Badge> : null}
                    {selectedEntry.submission?.id ? <Badge variant="secondary">Submission #{selectedEntry.submission.id}</Badge> : null}
                  </div>
                  {selectedEntry.attachment_urls.length ? (
                    <div className="space-y-2">
                      <p className="text-sm font-medium">Attachments</p>
                      <div className="space-y-2">
                        {selectedEntry.attachment_urls.map((url, index) => (
                          <a key={url} className="flex items-center gap-2 text-sm text-primary hover:underline" href={url} target="_blank" rel="noreferrer">
                            <Link2 className="h-4 w-4" />
                            Attachment {index + 1}
                          </a>
                        ))}
                      </div>
                    </div>
                  ) : null}
                  <div className="flex flex-wrap gap-2">
                    <Button variant="outline" onClick={() => startEditingEntry(selectedEntry)}>
                      <Pencil className="mr-2 h-4 w-4" />
                      Edit
                    </Button>
                    <Button
                      variant="destructive"
                      onClick={() =>
                        void api.deletePortfolioEntry(selectedEntry.id).then(async () => {
                          setSelectedEntryId(null)
                          await loadPortfolio()
                        })
                      }
                    >
                      <Trash2 className="mr-2 h-4 w-4" />
                      Delete
                    </Button>
                  </div>
                </div>
              ) : (
                <EmptyState title="Select an entry" description="Choose an item to inspect attachments, dates, and linked work." />
              )}
            </CardContent>
          </Card>
        </div>
      </div>

      <div className="grid gap-4 xl:grid-cols-[1fr_1fr]">
        <Card>
          <CardHeader>
            <CardTitle>{editingCollectionId ? 'Edit collection' : 'Collection builder'}</CardTitle>
            <CardDescription>Drag entries into a curated collection and generate a share link for family or co-ops.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid gap-3 md:grid-cols-2">
              <div className="space-y-2">
                <Label>Name</Label>
                <Input value={collectionForm.name} onChange={(event) => setCollectionForm((current) => ({ ...current, name: event.target.value }))} placeholder="Spring portfolio" />
              </div>
              <div className="space-y-2">
                <Label>Share publicly</Label>
                <Select value={collectionForm.is_public ? 'yes' : 'no'} onValueChange={(value) => setCollectionForm((current) => ({ ...current, is_public: value === 'yes' }))}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="no">Private</SelectItem>
                    <SelectItem value="yes">Public link enabled</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>
            <div className="space-y-2">
              <Label>Description</Label>
              <Textarea value={collectionForm.description} onChange={(event) => setCollectionForm((current) => ({ ...current, description: event.target.value }))} placeholder="A short introduction for grandparents or co-op reviewers." />
            </div>
            <div className="grid gap-4 md:grid-cols-2">
              <div className="space-y-2">
                <Label>Available entries</Label>
                <div className="space-y-2">
                  {entries.map((entry) => (
                    <div key={entry.id} draggable onDragStart={(event) => event.dataTransfer.setData('text/plain', String(entry.id))} className="flex items-center justify-between rounded-lg border px-3 py-2 text-sm">
                      <span>{entry.title}</span>
                      <Button size="sm" variant="ghost" onClick={() => addEntryToCollection(entry.id)}>
                        Add
                      </Button>
                    </div>
                  ))}
                </div>
              </div>
              <div className="space-y-2">
                <Label>Collection entries</Label>
                <div onDragOver={(event) => event.preventDefault()} onDrop={handleDrop} className="min-h-40 rounded-xl border border-dashed p-3">
                  {collectionForm.entry_ids.length ? (
                    <div className="space-y-2">
                      {collectionForm.entry_ids.map((entryId) => {
                        const entry = entries.find((item) => item.id === entryId)
                        if (!entry) return null
                        return (
                          <div key={entry.id} className="flex items-center justify-between rounded-lg border px-3 py-2 text-sm">
                            <span>{entry.title}</span>
                            <Button size="sm" variant="ghost" onClick={() => removeEntryFromCollection(entry.id)}>
                              Remove
                            </Button>
                          </div>
                        )
                      })}
                    </div>
                  ) : (
                    <p className="text-sm text-muted-foreground">Drop entries here to build the collection.</p>
                  )}
                </div>
              </div>
            </div>
            <div className="flex flex-wrap gap-2">
              <Button onClick={() => void saveCollection()} disabled={saving}>
                <Save className="mr-2 h-4 w-4" />
                {editingCollectionId ? 'Update collection' : 'Create collection'}
              </Button>
              {editingCollectionId ? (
                <>
                  <Button
                    variant="outline"
                    onClick={() =>
                      void api.sharePortfolioCollection(editingCollectionId).then((response) => {
                        setShareUrl(response.url)
                      })
                    }
                  >
                    <Share2 className="mr-2 h-4 w-4" />
                    Share
                  </Button>
                  <Button variant="outline" onClick={resetCollectionForm}>
                    Cancel
                  </Button>
                </>
              ) : null}
            </div>
            {shareUrl ? (
              <div className="rounded-lg border bg-muted/20 p-3">
                <p className="mb-2 text-sm font-medium">Public share link</p>
                <div className="flex gap-2">
                  <Input value={shareUrl} readOnly />
                  <Button variant="outline" onClick={() => void navigator.clipboard.writeText(shareUrl)}>
                    Copy
                  </Button>
                </div>
              </div>
            ) : null}

            {collections.length ? (
              <div className="space-y-2">
                <p className="text-sm font-medium">Saved collections</p>
                {collections.map((collection) => (
                  <div key={collection.id} className="flex flex-wrap items-center justify-between gap-2 rounded-lg border px-3 py-2">
                    <div>
                      <p className="font-medium">{collection.name}</p>
                      <p className="text-xs text-muted-foreground">{collection.entries.length} entries</p>
                    </div>
                    <div className="flex gap-2">
                      {collection.is_public ? <Badge>Public</Badge> : <Badge variant="outline">Private</Badge>}
                      <Button size="sm" variant="outline" onClick={() => startEditingCollection(collection)}>
                        Edit
                      </Button>
                      <Button size="sm" variant="destructive" onClick={() => void api.deletePortfolioCollection(collection.id).then(loadPortfolio)}>
                        Delete
                      </Button>
                    </div>
                  </div>
                ))}
              </div>
            ) : null}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Journal timeline</CardTitle>
            <CardDescription>Review date-linked journal entries alongside milestone work.</CardDescription>
          </CardHeader>
          <CardContent>
            {journalEntries.length ? (
              <div className="space-y-4">
                {journalEntries.map((entry) => (
                  <div key={entry.id} className="rounded-xl border p-4">
                    <div className="mb-2 flex items-center justify-between gap-3">
                      <div>
                        <p className="font-medium">{entry.title}</p>
                        <p className="text-xs text-muted-foreground">{formatDateLabel(entry.date)}</p>
                      </div>
                      <Badge variant="secondary">Journal</Badge>
                    </div>
                    <p className="whitespace-pre-wrap text-sm text-muted-foreground">{entry.description || 'No journal body yet.'}</p>
                  </div>
                ))}
              </div>
            ) : (
              <EmptyState title="No journal entries yet" description="Switch the entry type to Journal to start building a learning timeline." />
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
