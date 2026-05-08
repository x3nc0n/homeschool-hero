import { useEffect, useState } from 'react'
import { Pencil, Plus, Trash2 } from 'lucide-react'
import { api } from '@/lib/api'
import type { Subject } from '@/types/api'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { EmptyState } from '@/components/common/EmptyState'
import { ErrorState } from '@/components/common/ErrorState'
import { LoadingState } from '@/components/common/LoadingState'

const defaultColors = ['#3B82F6', '#F97316', '#22C55E', '#A855F7', '#EF4444']

export function SubjectsPage() {
  const [subjects, setSubjects] = useState<Subject[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [name, setName] = useState('')
  const [color, setColor] = useState(defaultColors[0])
  const [editingId, setEditingId] = useState<number | null>(null)

  const load = async () => {
    setLoading(true)
    setError('')
    try {
      setSubjects(await api.listSubjects())
    } catch (subjectError) {
      setError(subjectError instanceof Error ? subjectError.message : 'Unable to load subjects')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void load()
  }, [])

  const save = async () => {
    if (!name.trim()) return

    if (editingId) {
      await api.updateSubject(editingId, { name: name.trim(), color })
      setEditingId(null)
    } else {
      await api.createSubject({ name: name.trim(), color })
    }

    setName('')
    setColor(defaultColors[0])
    await load()
  }

  if (loading) return <LoadingState message="Loading subjects…" />
  if (error) return <ErrorState message={error} onRetry={() => void load()} />

  return (
    <Card>
      <CardHeader>
        <CardTitle>Subjects</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="flex flex-wrap items-center gap-2">
          <Input className="max-w-sm" value={name} onChange={(event) => setName(event.target.value)} placeholder="Subject name" />
          <Input type="color" value={color} onChange={(event) => setColor(event.target.value)} className="h-10 w-14 p-1" />
          <Button onClick={() => void save()}>
            <Plus className="mr-2 h-4 w-4" />
            {editingId ? 'Update' : 'Add'} subject
          </Button>
        </div>

        {subjects.length ? (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Subject</TableHead>
                <TableHead>Color</TableHead>
                <TableHead className="w-[180px]">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {subjects.map((subject) => (
                <TableRow key={subject.id}>
                  <TableCell>{subject.name}</TableCell>
                  <TableCell>
                    <span className="inline-flex items-center gap-2 text-xs">
                      <span className="h-3 w-3 rounded-full" style={{ backgroundColor: subject.color || '#999' }} />
                      {subject.color || '—'}
                    </span>
                  </TableCell>
                  <TableCell className="space-x-2">
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => {
                        setEditingId(subject.id)
                        setName(subject.name)
                        setColor(subject.color || defaultColors[0])
                      }}
                    >
                      <Pencil className="mr-2 h-3.5 w-3.5" />
                      Edit
                    </Button>
                    <Button size="sm" variant="destructive" onClick={() => void api.deleteSubject(subject.id).then(load)}>
                      <Trash2 className="mr-2 h-3.5 w-3.5" />
                      Delete
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        ) : (
          <EmptyState title="No subjects yet" description="Create a subject like Math or Science to organize assignments." />
        )}
      </CardContent>
    </Card>
  )
}
