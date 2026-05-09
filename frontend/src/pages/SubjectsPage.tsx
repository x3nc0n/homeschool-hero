import { useEffect, useMemo, useState } from 'react'
import { Pencil, Plus, Save, Trash2 } from 'lucide-react'
import { api } from '@/lib/api'
import type { GradeCategory, GradeScale, Subject, SubjectGradingMode } from '@/types/api'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { EmptyState } from '@/components/common/EmptyState'
import { ErrorState } from '@/components/common/ErrorState'
import { LoadingState } from '@/components/common/LoadingState'

const defaultColors = ['#3b82f6', '#f97316', '#22c55e', '#a855f7', '#ef4444']
const defaultCategoryNames = ['homework', 'quiz', 'test']

type SubjectForm = {
  name: string
  color: string
  grading_mode: SubjectGradingMode
  grade_scale_id: string
}

const defaultForm: SubjectForm = {
  name: '',
  color: defaultColors[0],
  grading_mode: 'points',
  grade_scale_id: 'default',
}

export function SubjectsPage() {
  const [subjects, setSubjects] = useState<Subject[]>([])
  const [scales, setScales] = useState<GradeScale[]>([])
  const [categories, setCategories] = useState<GradeCategory[]>([])
  const [loading, setLoading] = useState(true)
  const [settingsLoading, setSettingsLoading] = useState(false)
  const [error, setError] = useState('')
  const [settingsMessage, setSettingsMessage] = useState('')
  const [form, setForm] = useState<SubjectForm>(defaultForm)
  const [editingId, setEditingId] = useState<number | null>(null)
  const [selectedSubjectId, setSelectedSubjectId] = useState<number | null>(null)

  const selectedSubject = useMemo(
    () => subjects.find((subject) => subject.id === selectedSubjectId) ?? subjects[0] ?? null,
    [selectedSubjectId, subjects],
  )

  const load = async (preferredSubjectId?: number | null) => {
    setLoading(true)
    setError('')
    try {
      const [subjectData, scaleData] = await Promise.all([api.listSubjects(), api.listGradeScales()])
      setSubjects(subjectData)
      setScales(scaleData)
      const nextSubjectId =
        preferredSubjectId && subjectData.some((subject) => subject.id === preferredSubjectId)
          ? preferredSubjectId
          : subjectData[0]?.id ?? null
      setSelectedSubjectId(nextSubjectId)
    } catch (subjectError) {
      setError(subjectError instanceof Error ? subjectError.message : 'Unable to load subjects')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void load()
  }, [])

  useEffect(() => {
    const loadCategories = async () => {
      if (!selectedSubject) {
        setCategories([])
        return
      }
      setSettingsLoading(true)
      try {
        setCategories(await api.getGradeCategories(selectedSubject.id))
      } catch (categoryError) {
        setError(categoryError instanceof Error ? categoryError.message : 'Unable to load grade categories')
      } finally {
        setSettingsLoading(false)
      }
    }
    void loadCategories()
  }, [selectedSubject])

  const saveSubject = async () => {
    if (!form.name.trim()) return
    const payload = {
      name: form.name.trim(),
      color: form.color,
      grading_mode: form.grading_mode,
      grade_scale_id: form.grade_scale_id === 'default' ? null : Number(form.grade_scale_id),
    }

    if (editingId) {
      await api.updateSubject(editingId, payload)
    } else {
      await api.createSubject(payload)
    }

    setEditingId(null)
    setForm(defaultForm)
    await load(editingId)
  }

  const saveCategories = async () => {
    if (!selectedSubject) return
    setSettingsLoading(true)
    setSettingsMessage('')
    setError('')
    try {
      const normalized = categories.map((category) => ({
        id: category.id,
        name: category.name.trim().toLowerCase(),
        weight: Number(category.weight),
        drop_lowest: Number(category.drop_lowest || 0),
      }))
      await api.upsertGradeCategories(selectedSubject.id, normalized)
      setSettingsMessage('Grade categories updated.')
      setCategories(await api.getGradeCategories(selectedSubject.id))
    } catch (categoryError) {
      setError(categoryError instanceof Error ? categoryError.message : 'Unable to save grade categories')
    } finally {
      setSettingsLoading(false)
    }
  }

  if (loading) return <LoadingState message="Loading subjects…" />
  if (error && !subjects.length) return <ErrorState message={error} onRetry={() => void load(selectedSubjectId)} />

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <CardTitle>Subjects</CardTitle>
          <CardDescription>Manage subjects, grading mode, and subject-level grade scale overrides.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-3 lg:grid-cols-5">
            <Input
              className="lg:col-span-2"
              value={form.name}
              onChange={(event) => setForm((current) => ({ ...current, name: event.target.value }))}
              placeholder="Subject name"
            />
            <Input
              type="color"
              value={form.color}
              onChange={(event) => setForm((current) => ({ ...current, color: event.target.value }))}
              className="h-10 w-full p-1"
            />
            <Select
              value={form.grading_mode}
              onValueChange={(value) => setForm((current) => ({ ...current, grading_mode: value as SubjectGradingMode }))}
            >
              <SelectTrigger>
                <SelectValue placeholder="Grading mode" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="points">Points-based</SelectItem>
                <SelectItem value="percentage">Percentage-based</SelectItem>
              </SelectContent>
            </Select>
            <Select value={form.grade_scale_id} onValueChange={(value) => setForm((current) => ({ ...current, grade_scale_id: value }))}>
              <SelectTrigger>
                <SelectValue placeholder="Family default scale" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="default">Family default scale</SelectItem>
                {scales.map((scale) => (
                  <SelectItem key={scale.id} value={String(scale.id)}>
                    {scale.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <Button onClick={() => void saveSubject()}>
            <Plus className="mr-2 h-4 w-4" />
            {editingId ? 'Update' : 'Add'} subject
          </Button>

          {subjects.length ? (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Subject</TableHead>
                  <TableHead>Mode</TableHead>
                  <TableHead>Scale</TableHead>
                  <TableHead>Color</TableHead>
                  <TableHead className="w-[210px]">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {subjects.map((subject) => (
                  <TableRow key={subject.id}>
                    <TableCell>
                      <button type="button" className="font-medium hover:underline" onClick={() => setSelectedSubjectId(subject.id)}>
                        {subject.name}
                      </button>
                    </TableCell>
                    <TableCell>{subject.grading_mode === 'percentage' ? 'Percentage' : 'Points'}</TableCell>
                    <TableCell>{scales.find((scale) => scale.id === subject.grade_scale_id)?.name || 'Family default'}</TableCell>
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
                          setSelectedSubjectId(subject.id)
                          setForm({
                            name: subject.name,
                            color: subject.color || defaultColors[0],
                            grading_mode: subject.grading_mode || 'points',
                            grade_scale_id: subject.grade_scale_id ? String(subject.grade_scale_id) : 'default',
                          })
                        }}
                      >
                        <Pencil className="mr-2 h-3.5 w-3.5" />
                        Edit
                      </Button>
                      <Button
                        size="sm"
                        variant="destructive"
                        onClick={() => void api.deleteSubject(subject.id).then(() => load(selectedSubjectId === subject.id ? null : selectedSubjectId))}
                      >
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

      <Card>
        <CardHeader>
          <CardTitle>Grade categories</CardTitle>
          <CardDescription>
            {selectedSubject
              ? `Configure weighted categories and drop-lowest rules for ${selectedSubject.name}.`
              : 'Create a subject first to configure the gradebook.'}
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {!selectedSubject ? (
            <EmptyState title="No subject selected" description="Select a subject above to edit grade categories." />
          ) : settingsLoading && !categories.length ? (
            <LoadingState message="Loading category settings…" />
          ) : (
            <>
              <div className="grid gap-3 md:grid-cols-4">
                {categories.map((category, index) => (
                  <div key={`${category.id ?? category.name}-${index}`} className="rounded-lg border p-3 space-y-3">
                    <div className="space-y-2">
                      <Label>Name</Label>
                      <Input
                        value={category.name}
                        onChange={(event) =>
                          setCategories((current) =>
                            current.map((item, itemIndex) =>
                              itemIndex === index ? { ...item, name: event.target.value } : item,
                            ),
                          )
                        }
                      />
                    </div>
                    <div className="space-y-2">
                      <Label>Weight</Label>
                      <Input
                        type="number"
                        min="0"
                        max="1"
                        step="0.05"
                        value={category.weight}
                        onChange={(event) =>
                          setCategories((current) =>
                            current.map((item, itemIndex) =>
                              itemIndex === index ? { ...item, weight: Number(event.target.value) } : item,
                            ),
                          )
                        }
                      />
                    </div>
                    <div className="space-y-2">
                      <Label>Drop lowest</Label>
                      <Input
                        type="number"
                        min="0"
                        value={category.drop_lowest}
                        onChange={(event) =>
                          setCategories((current) =>
                            current.map((item, itemIndex) =>
                              itemIndex === index ? { ...item, drop_lowest: Number(event.target.value) } : item,
                            ),
                          )
                        }
                      />
                    </div>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => setCategories((current) => current.filter((_, itemIndex) => itemIndex !== index))}
                    >
                      <Trash2 className="mr-2 h-3.5 w-3.5" />
                      Remove
                    </Button>
                  </div>
                ))}
              </div>
              <div className="flex flex-wrap gap-2">
                <Button
                  variant="outline"
                  onClick={() =>
                    setCategories((current) => [
                      ...current,
                      { name: defaultCategoryNames[current.length] || `category_${current.length + 1}`, weight: 0, drop_lowest: 0 },
                    ])
                  }
                >
                  <Plus className="mr-2 h-4 w-4" />
                  Add category
                </Button>
                <Button onClick={() => void saveCategories()} disabled={settingsLoading || !categories.length}>
                  <Save className="mr-2 h-4 w-4" />
                  Save categories
                </Button>
              </div>
              <p className="text-xs text-muted-foreground">
                Current total weight:{' '}
                {categories.reduce((total, category) => total + Number(category.weight || 0), 0).toFixed(2)} (must equal 1.00)
              </p>
            </>
          )}
          {settingsMessage ? <p className="text-sm text-muted-foreground">{settingsMessage}</p> : null}
          {error ? <p className="text-sm text-destructive">{error}</p> : null}
        </CardContent>
      </Card>
    </div>
  )
}
