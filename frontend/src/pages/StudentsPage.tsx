import { useEffect, useState } from 'react'
import { Pencil, Plus, Trash2 } from 'lucide-react'
import { api } from '@/lib/api'
import type { Student } from '@/types/api'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { EmptyState } from '@/components/common/EmptyState'
import { ErrorState } from '@/components/common/ErrorState'
import { LoadingState } from '@/components/common/LoadingState'

export function StudentsPage() {
  const [students, setStudents] = useState<Student[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [draftName, setDraftName] = useState('')
  const [editingId, setEditingId] = useState<number | null>(null)

  const load = async () => {
    setLoading(true)
    setError('')
    try {
      setStudents(await api.listStudents())
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : 'Unable to load students')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void load()
  }, [])

  const saveStudent = async () => {
    if (!draftName.trim()) return

    if (editingId) {
      await api.updateStudent(editingId, { name: draftName.trim() })
      setEditingId(null)
    } else {
      await api.createStudent({ name: draftName.trim() })
    }

    setDraftName('')
    await load()
  }

  if (loading) return <LoadingState message="Loading students…" />
  if (error) return <ErrorState message={error} onRetry={() => void load()} />

  return (
    <Card>
      <CardHeader>
        <CardTitle>Students</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="flex flex-wrap gap-2">
          <Input
            className="max-w-sm"
            placeholder="Student name"
            value={draftName}
            onChange={(event) => setDraftName(event.target.value)}
          />
          <Button onClick={() => void saveStudent()}>
            <Plus className="mr-2 h-4 w-4" />
            {editingId ? 'Update' : 'Add'} student
          </Button>
        </div>

        {students.length ? (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Name</TableHead>
                <TableHead className="w-[180px]">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {students.map((student) => (
                <TableRow key={student.id}>
                  <TableCell>{student.name}</TableCell>
                  <TableCell className="space-x-2">
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => {
                        setDraftName(student.name)
                        setEditingId(student.id)
                      }}
                    >
                      <Pencil className="mr-2 h-3.5 w-3.5" />
                      Edit
                    </Button>
                    <Button size="sm" variant="destructive" onClick={() => void api.deleteStudent(student.id).then(load)}>
                      <Trash2 className="mr-2 h-3.5 w-3.5" />
                      Delete
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        ) : (
          <EmptyState title="No students yet" description="Add your first child profile to start tracking grades." />
        )}
      </CardContent>
    </Card>
  )
}
