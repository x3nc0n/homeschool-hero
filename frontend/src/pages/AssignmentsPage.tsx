import { useEffect, useMemo, useState } from 'react'
import { Pencil, Plus, Trash2 } from 'lucide-react'
import { api } from '@/lib/api'
import type { Assignment, AssignmentStatus, Subject } from '@/types/api'
import { useAuth } from '@/context/AuthContext'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Textarea } from '@/components/ui/textarea'
import { Badge } from '@/components/ui/badge'
import { EmptyState } from '@/components/common/EmptyState'
import { LoadingState } from '@/components/common/LoadingState'
import { ErrorState } from '@/components/common/ErrorState'

const statuses: AssignmentStatus[] = ['pending', 'complete', 'graded']

export function AssignmentsPage() {
  const { canManageCurriculum } = useAuth()
  const [assignments, setAssignments] = useState<Assignment[]>([])
  const [subjects, setSubjects] = useState<Subject[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [editing, setEditing] = useState<Assignment | null>(null)
  const [form, setForm] = useState<{
    title: string
    description: string
    due_date: string
    status: AssignmentStatus
    subject_id: string
  }>({
    title: '',
    description: '',
    due_date: '',
    status: 'pending',
    subject_id: '',
  })

  const load = async () => {
    setLoading(true)
    setError('')
    try {
      const [assignmentData, subjectData] = await Promise.all([api.listAssignments(), api.listSubjects()])
      setAssignments(assignmentData)
      setSubjects(subjectData)
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : 'Unable to load assignments')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void load()
  }, [])

  const resetForm = () => {
    setEditing(null)
    setForm({ title: '', description: '', due_date: '', status: 'pending', subject_id: '' })
  }

  const save = async () => {
    if (!canManageCurriculum) return
    const payload = {
      title: form.title,
      description: form.description,
      due_date: form.due_date || undefined,
      status: form.status,
      subject_id: form.subject_id ? Number(form.subject_id) : undefined,
    }

    if (editing) {
      await api.updateAssignment(editing.id, payload)
    } else {
      await api.createAssignment(payload)
    }

    resetForm()
    await load()
  }

  const assignmentsWithSubject = useMemo(
    () =>
      assignments.map((assignment) => ({
        ...assignment,
        subjectName:
          assignment.subject?.name || subjects.find((subject) => subject.id === assignment.subject_id)?.name || 'Unassigned',
      })),
    [assignments, subjects],
  )

  if (loading) return <LoadingState message="Loading assignments…" />
  if (error) return <ErrorState message={error} onRetry={() => void load()} />

  return (
    <div className="space-y-4">
      {canManageCurriculum ? (
        <Card>
          <CardHeader>
            <CardTitle>{editing ? 'Edit assignment' : 'Create assignment'}</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid gap-4 md:grid-cols-2">
              <div className="space-y-2">
                <Label>Title</Label>
                <Input value={form.title} onChange={(event) => setForm((prev) => ({ ...prev, title: event.target.value }))} />
              </div>
              <div className="space-y-2">
                <Label>Subject</Label>
                <Select value={form.subject_id} onValueChange={(value) => setForm((prev) => ({ ...prev, subject_id: value }))}>
                  <SelectTrigger>
                    <SelectValue placeholder="Select subject" />
                  </SelectTrigger>
                  <SelectContent>
                    {subjects.map((subject) => (
                      <SelectItem key={subject.id} value={String(subject.id)}>
                        {subject.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label>Due date</Label>
                <Input
                  type="date"
                  value={form.due_date}
                  onChange={(event) => setForm((prev) => ({ ...prev, due_date: event.target.value }))}
                />
              </div>
              <div className="space-y-2">
                <Label>Status</Label>
                <Select value={form.status} onValueChange={(value: AssignmentStatus) => setForm((prev) => ({ ...prev, status: value }))}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {statuses.map((status) => (
                      <SelectItem key={status} value={status}>
                        {status}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>
            <div className="space-y-2">
              <Label>Description</Label>
              <Textarea
                value={form.description}
                onChange={(event) => setForm((prev) => ({ ...prev, description: event.target.value }))}
              />
            </div>
            <div className="flex flex-wrap gap-2">
              <Button onClick={() => void save()}>
                <Plus className="mr-2 h-4 w-4" />
                {editing ? 'Update' : 'Create'} assignment
              </Button>
              {editing ? (
                <Button variant="outline" onClick={resetForm}>
                  Cancel edit
                </Button>
              ) : null}
            </div>
          </CardContent>
        </Card>
      ) : null}

      <Card>
        <CardHeader>
          <CardTitle>Assignment list</CardTitle>
        </CardHeader>
        <CardContent>
          {assignmentsWithSubject.length ? (
            <div className="space-y-2">
              {assignmentsWithSubject.map((assignment) => (
                <div key={assignment.id} className="rounded-lg border p-3">
                  <div className="flex flex-wrap items-start justify-between gap-2">
                    <div>
                      <p className="font-semibold">{assignment.title}</p>
                      <p className="text-xs text-muted-foreground">
                        {assignment.subjectName} • Due {assignment.due_date ? new Date(assignment.due_date).toLocaleDateString() : 'TBD'}
                      </p>
                    </div>
                    <Badge variant="secondary">{assignment.status}</Badge>
                  </div>
                  {assignment.description ? <p className="mt-2 text-sm text-muted-foreground">{assignment.description}</p> : null}
                  {canManageCurriculum ? (
                    <div className="mt-3 flex flex-wrap gap-2">
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => {
                          setEditing(assignment)
                          setForm({
                            title: assignment.title,
                            description: assignment.description || '',
                            due_date: assignment.due_date?.slice(0, 10) || '',
                            status: assignment.status,
                            subject_id: assignment.subject_id ? String(assignment.subject_id) : '',
                          })
                        }}
                      >
                        <Pencil className="mr-2 h-3.5 w-3.5" />
                        Edit
                      </Button>
                      <Button size="sm" variant="destructive" onClick={() => void api.deleteAssignment(assignment.id).then(load)}>
                        <Trash2 className="mr-2 h-3.5 w-3.5" />
                        Delete
                      </Button>
                    </div>
                  ) : null}
                </div>
              ))}
            </div>
          ) : (
            <EmptyState title="No assignments yet" description="Create an assignment to begin collecting student work." />
          )}
        </CardContent>
      </Card>
    </div>
  )
}
