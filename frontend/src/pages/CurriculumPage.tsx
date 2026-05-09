import { useCallback, useEffect, useMemo, useState } from 'react'
import { api } from '@/lib/api'
import type { CurriculumPackageDetail, SchoolYear, Subject } from '@/types/api'
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

type PackageForm = {
  school_year_id: string
  subject_id: string
  name: string
  description: string
}

type UnitForm = {
  name: string
  description: string
  sequence_order: string
  standards_tags: string
}

type LessonForm = {
  name: string
  description: string
  sequence_order: string
  estimated_duration_minutes: string
  standards_tags: string
}

type CloneForm = {
  source_package_id: string
  target_school_year_id: string
  name: string
}

function splitTags(value: string) {
  return value
    .split(',')
    .map((item) => item.trim())
    .filter(Boolean)
}

function emptyPackageForm(schoolYearId = '', subjectId = ''): PackageForm {
  return { school_year_id: schoolYearId, subject_id: subjectId, name: '', description: '' }
}

function emptyUnitForm(): UnitForm {
  return { name: '', description: '', sequence_order: '1', standards_tags: '' }
}

function emptyLessonForm(): LessonForm {
  return { name: '', description: '', sequence_order: '1', estimated_duration_minutes: '45', standards_tags: '' }
}

function emptyCloneForm(sourcePackageId = '', targetSchoolYearId = ''): CloneForm {
  return { source_package_id: sourcePackageId, target_school_year_id: targetSchoolYearId, name: '' }
}

export function CurriculumPage() {
  const [schoolYears, setSchoolYears] = useState<SchoolYear[]>([])
  const [subjects, setSubjects] = useState<Subject[]>([])
  const [packages, setPackages] = useState<CurriculumPackageDetail[]>([])
  const [selectedSchoolYearId, setSelectedSchoolYearId] = useState<number | null>(null)
  const [selectedPackageId, setSelectedPackageId] = useState<number | null>(null)
  const [selectedUnitId, setSelectedUnitId] = useState<number | null>(null)
  const [editingPackageId, setEditingPackageId] = useState<number | null>(null)
  const [editingUnitId, setEditingUnitId] = useState<number | null>(null)
  const [editingLessonId, setEditingLessonId] = useState<number | null>(null)
  const [packageForm, setPackageForm] = useState<PackageForm>(emptyPackageForm())
  const [unitForm, setUnitForm] = useState<UnitForm>(emptyUnitForm())
  const [lessonForm, setLessonForm] = useState<LessonForm>(emptyLessonForm())
  const [cloneForm, setCloneForm] = useState<CloneForm>(emptyCloneForm())
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  const selectedPackage = useMemo(
    () => packages.find((item) => item.id === selectedPackageId) ?? null,
    [packages, selectedPackageId],
  )
  const selectedUnit = useMemo(
    () => selectedPackage?.units.find((item) => item.id === selectedUnitId) ?? null,
    [selectedPackage, selectedUnitId],
  )

  const subjectMap = useMemo(() => Object.fromEntries(subjects.map((subject) => [subject.id, subject.name])), [subjects])
  const schoolYearMap = useMemo(
    () => Object.fromEntries(schoolYears.map((schoolYear) => [schoolYear.id, schoolYear.name])),
    [schoolYears],
  )

  const load = useCallback(
    async (preferredSchoolYearId?: number | null, preferredPackageId?: number | null, preferredUnitId?: number | null) => {
      setLoading(true)
      setError('')
      try {
        const [yearData, subjectData] = await Promise.all([api.listSchoolYears(), api.listSubjects()])
        const nextSchoolYearId =
          preferredSchoolYearId && yearData.some((schoolYear) => schoolYear.id === preferredSchoolYearId)
            ? preferredSchoolYearId
            : yearData.find((schoolYear) => schoolYear.is_active)?.id ?? yearData[0]?.id ?? null
        const packageData = await api.listCurriculumPackages(nextSchoolYearId ?? undefined)
        const nextPackageId =
          preferredPackageId && packageData.some((item) => item.id === preferredPackageId)
            ? preferredPackageId
            : packageData[0]?.id ?? null
        const nextPackage = packageData.find((item) => item.id === nextPackageId) ?? null
        const nextUnitId =
          preferredUnitId && nextPackage?.units.some((item) => item.id === preferredUnitId)
            ? preferredUnitId
            : nextPackage?.units[0]?.id ?? null

        setSchoolYears(yearData)
        setSubjects(subjectData)
        setPackages(packageData)
        setSelectedSchoolYearId(nextSchoolYearId)
        setSelectedPackageId(nextPackageId)
        setSelectedUnitId(nextUnitId)
        setPackageForm((current) =>
          editingPackageId
            ? current
            : emptyPackageForm(nextSchoolYearId ? String(nextSchoolYearId) : '', subjectData[0] ? String(subjectData[0].id) : ''),
        )
        setCloneForm((current) =>
          editingPackageId || editingUnitId || editingLessonId
            ? current
            : emptyCloneForm(nextPackageId ? String(nextPackageId) : '', nextSchoolYearId ? String(nextSchoolYearId) : ''),
        )
      } catch (loadError) {
        setError(loadError instanceof Error ? loadError.message : 'Unable to load curriculum')
      } finally {
        setLoading(false)
      }
    },
    [editingLessonId, editingPackageId, editingUnitId],
  )

  useEffect(() => {
    void load()
  }, [load])

  const resetPackageForm = () => {
    setEditingPackageId(null)
    setPackageForm(emptyPackageForm(selectedSchoolYearId ? String(selectedSchoolYearId) : '', subjects[0] ? String(subjects[0].id) : ''))
  }

  const resetUnitForm = () => {
    setEditingUnitId(null)
    setUnitForm(emptyUnitForm())
  }

  const resetLessonForm = () => {
    setEditingLessonId(null)
    setLessonForm(emptyLessonForm())
  }

  const savePackage = async () => {
    if (!packageForm.school_year_id || !packageForm.subject_id || !packageForm.name.trim()) return
    setSaving(true)
    try {
      const payload = {
        school_year_id: Number(packageForm.school_year_id),
        subject_id: Number(packageForm.subject_id),
        name: packageForm.name.trim(),
        description: packageForm.description.trim() || null,
      }
      const saved = editingPackageId
        ? await api.updateCurriculumPackage(editingPackageId, payload)
        : await api.createCurriculumPackage(payload)
      resetPackageForm()
      await load(payload.school_year_id, saved.id)
    } finally {
      setSaving(false)
    }
  }

  const saveUnit = async () => {
    if (!selectedPackageId || !unitForm.name.trim()) return
    setSaving(true)
    try {
      const payload = {
        package_id: selectedPackageId,
        name: unitForm.name.trim(),
        description: unitForm.description.trim() || null,
        sequence_order: Number(unitForm.sequence_order || 1),
        standards_tags: splitTags(unitForm.standards_tags),
      }
      await (editingUnitId ? api.updateCurriculumUnit(editingUnitId, payload) : api.createCurriculumUnit(payload))
      resetUnitForm()
      await load(selectedSchoolYearId, selectedPackageId, editingUnitId ?? undefined)
    } finally {
      setSaving(false)
    }
  }

  const saveLesson = async () => {
    if (!selectedUnitId || !lessonForm.name.trim()) return
    setSaving(true)
    try {
      const payload = {
        unit_id: selectedUnitId,
        name: lessonForm.name.trim(),
        description: lessonForm.description.trim() || null,
        sequence_order: Number(lessonForm.sequence_order || 1),
        estimated_duration_minutes: lessonForm.estimated_duration_minutes ? Number(lessonForm.estimated_duration_minutes) : null,
        standards_tags: splitTags(lessonForm.standards_tags),
      }
      await (editingLessonId ? api.updateCurriculumLesson(editingLessonId, payload) : api.createCurriculumLesson(payload))
      resetLessonForm()
      await load(selectedSchoolYearId, selectedPackageId, selectedUnitId)
    } finally {
      setSaving(false)
    }
  }

  const clonePackage = async () => {
    if (!cloneForm.source_package_id || !cloneForm.target_school_year_id) return
    setSaving(true)
    try {
      const created = await api.cloneCurriculumPackage(Number(cloneForm.source_package_id), {
        target_school_year_id: Number(cloneForm.target_school_year_id),
        name: cloneForm.name.trim() || undefined,
      })
      setCloneForm(emptyCloneForm(String(created.id), String(created.school_year_id)))
      await load(created.school_year_id, created.id)
    } finally {
      setSaving(false)
    }
  }

  if (loading) return <LoadingState message="Loading curriculum…" />
  if (error) return <ErrorState message={error} onRetry={() => void load(selectedSchoolYearId, selectedPackageId, selectedUnitId)} />

  return (
    <div className="space-y-4">
      <div className="grid gap-4 xl:grid-cols-[1.15fr_0.85fr]">
        <Card>
          <CardHeader>
            <CardTitle>Curriculum packages</CardTitle>
            <CardDescription>Organize school-year packages into units and lessons.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid gap-4 md:grid-cols-2">
              <div className="space-y-2">
                <Label>School year</Label>
                <Select
                  value={selectedSchoolYearId ? String(selectedSchoolYearId) : 'all'}
                  onValueChange={(value) => {
                    const nextYearId = value === 'all' ? null : Number(value)
                    setSelectedSchoolYearId(nextYearId)
                    void load(nextYearId)
                  }}
                >
                  <SelectTrigger>
                    <SelectValue placeholder="Choose school year" />
                  </SelectTrigger>
                  <SelectContent>
                    {schoolYears.map((schoolYear) => (
                      <SelectItem key={schoolYear.id} value={String(schoolYear.id)}>
                        {schoolYear.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="rounded-lg border bg-muted/20 p-3 text-sm">
                <p className="font-medium">{packages.length} package(s)</p>
                <p className="text-muted-foreground">{selectedPackage ? `Selected: ${selectedPackage.name}` : 'Select a package to add units.'}</p>
              </div>
            </div>

            {packages.length ? (
              <div className="space-y-3">
                {packages.map((pkg) => (
                  <details key={pkg.id} open className="rounded-lg border p-3">
                    <summary className="cursor-pointer list-none">
                      <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
                        <div>
                          <div className="flex flex-wrap items-center gap-2">
                            <button
                              type="button"
                              className="text-left text-lg font-semibold"
                              onClick={() => {
                                setSelectedPackageId(pkg.id)
                                setSelectedUnitId(pkg.units[0]?.id ?? null)
                              }}
                            >
                              {pkg.name}
                            </button>
                            <Badge variant="secondary">{schoolYearMap[pkg.school_year_id] || `Year ${pkg.school_year_id}`}</Badge>
                            <Badge variant="secondary">{subjectMap[pkg.subject_id] || `Subject ${pkg.subject_id}`}</Badge>
                          </div>
                          {pkg.description ? <p className="mt-2 text-sm text-muted-foreground">{pkg.description}</p> : null}
                        </div>
                        <div className="flex flex-wrap gap-2">
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={() => {
                              setSelectedPackageId(pkg.id)
                              setPackageForm({
                                school_year_id: String(pkg.school_year_id),
                                subject_id: String(pkg.subject_id),
                                name: pkg.name,
                                description: pkg.description || '',
                              })
                              setEditingPackageId(pkg.id)
                            }}
                          >
                            Edit
                          </Button>
                          <Button size="sm" variant="destructive" onClick={() => void api.deleteCurriculumPackage(pkg.id).then(() => load(selectedSchoolYearId))}>
                            Delete
                          </Button>
                        </div>
                      </div>
                    </summary>
                    <div className="mt-4 space-y-3">
                      {pkg.units.length ? (
                        pkg.units.map((unit) => (
                          <details key={unit.id} open className="rounded-md border bg-muted/10 p-3">
                            <summary className="cursor-pointer list-none">
                              <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
                                <div>
                                  <button
                                    type="button"
                                    className="text-left font-medium"
                                    onClick={() => {
                                      setSelectedPackageId(pkg.id)
                                      setSelectedUnitId(unit.id)
                                    }}
                                  >
                                    {unit.sequence_order}. {unit.name}
                                  </button>
                                  {unit.description ? <p className="mt-1 text-sm text-muted-foreground">{unit.description}</p> : null}
                                  {unit.standards_tags.length ? (
                                    <div className="mt-2 flex flex-wrap gap-2">
                                      {unit.standards_tags.map((tag) => (
                                        <Badge key={tag} variant="outline">
                                          {tag}
                                        </Badge>
                                      ))}
                                    </div>
                                  ) : null}
                                </div>
                                <div className="flex flex-wrap gap-2">
                                  <Button
                                    size="sm"
                                    variant="outline"
                                    onClick={() => {
                                      setSelectedPackageId(pkg.id)
                                      setSelectedUnitId(unit.id)
                                      setUnitForm({
                                        name: unit.name,
                                        description: unit.description || '',
                                        sequence_order: String(unit.sequence_order),
                                        standards_tags: unit.standards_tags.join(', '),
                                      })
                                      setEditingUnitId(unit.id)
                                    }}
                                  >
                                    Edit
                                  </Button>
                                  <Button size="sm" variant="destructive" onClick={() => void api.deleteCurriculumUnit(unit.id).then(() => load(selectedSchoolYearId, pkg.id))}>
                                    Delete
                                  </Button>
                                </div>
                              </div>
                            </summary>
                            <div className="mt-3 space-y-3">
                              {unit.lessons.length ? (
                                unit.lessons.map((lesson) => (
                                  <div key={lesson.id} className="rounded-md border bg-background p-3">
                                    <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
                                      <div>
                                        <button
                                          type="button"
                                          className="text-left font-medium"
                                          onClick={() => {
                                            setSelectedPackageId(pkg.id)
                                            setSelectedUnitId(unit.id)
                                          }}
                                        >
                                          {lesson.sequence_order}. {lesson.name}
                                        </button>
                                        <p className="mt-1 text-sm text-muted-foreground">
                                          {lesson.estimated_duration_minutes ? `${lesson.estimated_duration_minutes} min` : 'Duration not set'}
                                        </p>
                                        {lesson.description ? <p className="mt-1 text-sm text-muted-foreground">{lesson.description}</p> : null}
                                        {lesson.standards_tags.length ? (
                                          <div className="mt-2 flex flex-wrap gap-2">
                                            {lesson.standards_tags.map((tag) => (
                                              <Badge key={tag} variant="outline">
                                                {tag}
                                              </Badge>
                                            ))}
                                          </div>
                                        ) : null}
                                        {lesson.resources.length ? (
                                          <div className="mt-2 flex flex-wrap gap-2">
                                            {lesson.resources.map((resource) => (
                                              <Badge key={resource.id} variant="secondary">
                                                {resource.name}
                                              </Badge>
                                            ))}
                                          </div>
                                        ) : (
                                          <p className="mt-2 text-xs text-muted-foreground">No linked resources yet.</p>
                                        )}
                                      </div>
                                      <div className="flex flex-wrap gap-2">
                                        <Button
                                          size="sm"
                                          variant="outline"
                                          onClick={() => {
                                            setSelectedPackageId(pkg.id)
                                            setSelectedUnitId(unit.id)
                                            setLessonForm({
                                              name: lesson.name,
                                              description: lesson.description || '',
                                              sequence_order: String(lesson.sequence_order),
                                              estimated_duration_minutes: lesson.estimated_duration_minutes
                                                ? String(lesson.estimated_duration_minutes)
                                                : '',
                                              standards_tags: lesson.standards_tags.join(', '),
                                            })
                                            setEditingLessonId(lesson.id)
                                          }}
                                        >
                                          Edit
                                        </Button>
                                        <Button size="sm" variant="destructive" onClick={() => void api.deleteCurriculumLesson(lesson.id).then(() => load(selectedSchoolYearId, pkg.id, unit.id))}>
                                          Delete
                                        </Button>
                                      </div>
                                    </div>
                                  </div>
                                ))
                              ) : (
                                <p className="text-sm text-muted-foreground">No lessons in this unit yet.</p>
                              )}
                            </div>
                          </details>
                        ))
                      ) : (
                        <p className="text-sm text-muted-foreground">No units in this package yet.</p>
                      )}
                    </div>
                  </details>
                ))}
              </div>
            ) : (
              <EmptyState title="No curriculum packages yet" description="Create a package for each subject and school year." />
            )}
          </CardContent>
        </Card>

        <div className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>{editingPackageId ? 'Edit curriculum package' : 'Create curriculum package'}</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="space-y-2">
                <Label>School year</Label>
                <Select value={packageForm.school_year_id} onValueChange={(value) => setPackageForm((current) => ({ ...current, school_year_id: value }))}>
                  <SelectTrigger>
                    <SelectValue placeholder="Choose school year" />
                  </SelectTrigger>
                  <SelectContent>
                    {schoolYears.map((schoolYear) => (
                      <SelectItem key={schoolYear.id} value={String(schoolYear.id)}>
                        {schoolYear.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label>Subject</Label>
                <Select value={packageForm.subject_id} onValueChange={(value) => setPackageForm((current) => ({ ...current, subject_id: value }))}>
                  <SelectTrigger>
                    <SelectValue placeholder="Choose subject" />
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
                <Label>Name</Label>
                <Input value={packageForm.name} onChange={(event) => setPackageForm((current) => ({ ...current, name: event.target.value }))} placeholder="Core Math 2025" />
              </div>
              <div className="space-y-2">
                <Label>Description</Label>
                <Textarea value={packageForm.description} onChange={(event) => setPackageForm((current) => ({ ...current, description: event.target.value }))} placeholder="Describe pacing, goals, and scope." />
              </div>
              <div className="flex gap-2">
                <Button onClick={() => void savePackage()} disabled={saving}>
                  {editingPackageId ? 'Update package' : 'Create package'}
                </Button>
                {editingPackageId ? (
                  <Button variant="outline" onClick={resetPackageForm}>
                    Cancel
                  </Button>
                ) : null}
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>{editingUnitId ? 'Edit unit' : 'Create unit'}</CardTitle>
              <CardDescription>{selectedPackage ? `Adding to ${selectedPackage.name}` : 'Select a package first.'}</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="space-y-2">
                <Label>Name</Label>
                <Input value={unitForm.name} onChange={(event) => setUnitForm((current) => ({ ...current, name: event.target.value }))} placeholder="Unit 1: Number Sense" />
              </div>
              <div className="space-y-2">
                <Label>Description</Label>
                <Textarea value={unitForm.description} onChange={(event) => setUnitForm((current) => ({ ...current, description: event.target.value }))} placeholder="Describe the anchor skills for this unit." />
              </div>
              <div className="grid gap-3 md:grid-cols-2">
                <div className="space-y-2">
                  <Label>Sequence order</Label>
                  <Input type="number" min="1" value={unitForm.sequence_order} onChange={(event) => setUnitForm((current) => ({ ...current, sequence_order: event.target.value }))} />
                </div>
                <div className="space-y-2">
                  <Label>Standards tags</Label>
                  <Input value={unitForm.standards_tags} onChange={(event) => setUnitForm((current) => ({ ...current, standards_tags: event.target.value }))} placeholder="MATH-NS.1, MATH-NS.2" />
                </div>
              </div>
              <div className="flex gap-2">
                <Button onClick={() => void saveUnit()} disabled={saving || !selectedPackageId}>
                  {editingUnitId ? 'Update unit' : 'Create unit'}
                </Button>
                {editingUnitId ? (
                  <Button variant="outline" onClick={resetUnitForm}>
                    Cancel
                  </Button>
                ) : null}
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>{editingLessonId ? 'Edit lesson' : 'Create lesson'}</CardTitle>
              <CardDescription>{selectedUnit ? `Adding to ${selectedUnit.name}` : 'Select a unit first.'}</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="space-y-2">
                <Label>Name</Label>
                <Input value={lessonForm.name} onChange={(event) => setLessonForm((current) => ({ ...current, name: event.target.value }))} placeholder="Lesson 1: Place value warm-up" />
              </div>
              <div className="space-y-2">
                <Label>Description</Label>
                <Textarea value={lessonForm.description} onChange={(event) => setLessonForm((current) => ({ ...current, description: event.target.value }))} placeholder="Describe the activity, checks, and outcomes." />
              </div>
              <div className="grid gap-3 md:grid-cols-3">
                <div className="space-y-2">
                  <Label>Sequence order</Label>
                  <Input type="number" min="1" value={lessonForm.sequence_order} onChange={(event) => setLessonForm((current) => ({ ...current, sequence_order: event.target.value }))} />
                </div>
                <div className="space-y-2">
                  <Label>Duration (minutes)</Label>
                  <Input type="number" min="1" value={lessonForm.estimated_duration_minutes} onChange={(event) => setLessonForm((current) => ({ ...current, estimated_duration_minutes: event.target.value }))} />
                </div>
                <div className="space-y-2">
                  <Label>Standards tags</Label>
                  <Input value={lessonForm.standards_tags} onChange={(event) => setLessonForm((current) => ({ ...current, standards_tags: event.target.value }))} placeholder="MATH-NS.1" />
                </div>
              </div>
              <div className="flex gap-2">
                <Button onClick={() => void saveLesson()} disabled={saving || !selectedUnitId}>
                  {editingLessonId ? 'Update lesson' : 'Create lesson'}
                </Button>
                {editingLessonId ? (
                  <Button variant="outline" onClick={resetLessonForm}>
                    Cancel
                  </Button>
                ) : null}
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Clone package wizard</CardTitle>
              <CardDescription>Carry a package into a new school year without rebuilding units and lessons.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="space-y-2">
                <Label>Source package</Label>
                <Select value={cloneForm.source_package_id} onValueChange={(value) => setCloneForm((current) => ({ ...current, source_package_id: value }))}>
                  <SelectTrigger>
                    <SelectValue placeholder="Choose package" />
                  </SelectTrigger>
                  <SelectContent>
                    {packages.map((pkg) => (
                      <SelectItem key={pkg.id} value={String(pkg.id)}>
                        {pkg.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label>Target school year</Label>
                <Select value={cloneForm.target_school_year_id} onValueChange={(value) => setCloneForm((current) => ({ ...current, target_school_year_id: value }))}>
                  <SelectTrigger>
                    <SelectValue placeholder="Choose school year" />
                  </SelectTrigger>
                  <SelectContent>
                    {schoolYears.map((schoolYear) => (
                      <SelectItem key={schoolYear.id} value={String(schoolYear.id)}>
                        {schoolYear.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label>Optional clone name</Label>
                <Input value={cloneForm.name} onChange={(event) => setCloneForm((current) => ({ ...current, name: event.target.value }))} placeholder="Core Math 2026" />
              </div>
              <Button onClick={() => void clonePackage()} disabled={saving || !cloneForm.source_package_id || !cloneForm.target_school_year_id}>
                Clone package
              </Button>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  )
}
