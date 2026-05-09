import { useCallback, useEffect, useMemo, useState } from 'react'
import { api } from '@/lib/api'
import type { CurriculumPackageDetail, Resource, ResourceType } from '@/types/api'
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

type ResourceForm = {
  name: string
  description: string
  resource_type: ResourceType
  url: string
  tags: string
  metadata: string
  file: File | null
}

function emptyResourceForm(): ResourceForm {
  return {
    name: '',
    description: '',
    resource_type: 'link',
    url: '',
    tags: '',
    metadata: '{\n  "format": "pdf"\n}',
    file: null,
  }
}

function splitTags(value: string) {
  return value
    .split(',')
    .map((item) => item.trim())
    .filter(Boolean)
}

export function ResourceLibraryPage() {
  const [resources, setResources] = useState<Resource[]>([])
  const [packages, setPackages] = useState<CurriculumPackageDetail[]>([])
  const [search, setSearch] = useState('')
  const [tag, setTag] = useState('')
  const [resourceTypeFilter, setResourceTypeFilter] = useState<ResourceType | 'all'>('all')
  const [selectedLessonId, setSelectedLessonId] = useState<string>('')
  const [editingResourceId, setEditingResourceId] = useState<number | null>(null)
  const [form, setForm] = useState<ResourceForm>(emptyResourceForm())
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  const lessonOptions = useMemo(
    () =>
      packages.flatMap((pkg) =>
        pkg.units.flatMap((unit) =>
          unit.lessons.map((lesson) => ({
            id: lesson.id,
            label: `${pkg.name} → ${unit.name} → ${lesson.name}`,
          })),
        ),
      ),
    [packages],
  )

  const lessonLabelMap = useMemo(
    () => Object.fromEntries(lessonOptions.map((lesson) => [lesson.id, lesson.label])),
    [lessonOptions],
  )

  const load = useCallback(
    async (filters = { search, tag, resource_type: resourceTypeFilter }) => {
      setLoading(true)
      setError('')
      try {
        const [resourceData, packageData] = await Promise.all([api.listResources(filters), api.listCurriculumPackages()])
        setResources(resourceData)
        setPackages(packageData)
        setSelectedLessonId(
          (current) => current || (packageData[0]?.units[0]?.lessons[0] ? String(packageData[0].units[0].lessons[0].id) : ''),
        )
      } catch (loadError) {
        setError(loadError instanceof Error ? loadError.message : 'Unable to load resource library')
      } finally {
        setLoading(false)
      }
    },
    [resourceTypeFilter, search, tag],
  )

  useEffect(() => {
    void load()
  }, [load])

  const resetForm = () => {
    setEditingResourceId(null)
    setForm(emptyResourceForm())
  }

  const saveResource = async () => {
    if (!form.name.trim()) return
    setSaving(true)
    try {
      const metadata = form.metadata.trim() ? (JSON.parse(form.metadata) as Record<string, unknown>) : {}
      if (editingResourceId) {
        await api.updateResource(editingResourceId, {
          name: form.name.trim(),
          description: form.description.trim() || null,
          resource_type: form.resource_type,
          url: form.resource_type === 'link' ? form.url.trim() || null : null,
          tags: splitTags(form.tags),
          metadata,
        })
      } else {
        const formData = new FormData()
        formData.append('name', form.name.trim())
        formData.append('description', form.description.trim())
        formData.append('resource_type', form.resource_type)
        formData.append('tags', JSON.stringify(splitTags(form.tags)))
        formData.append('metadata', JSON.stringify(metadata))
        if (form.resource_type === 'link') {
          formData.append('url', form.url.trim())
        }
        if (form.resource_type === 'file' && form.file) {
          formData.append('file', form.file)
        }
        await api.createResource(formData)
      }
      resetForm()
      await load()
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : 'Unable to save resource')
    } finally {
      setSaving(false)
    }
  }

  if (loading) return <LoadingState message="Loading resource library…" />
  if (error) return <ErrorState message={error} onRetry={() => void load()} />

  return (
    <div className="space-y-4">
      <div className="grid gap-4 xl:grid-cols-[0.85fr_1.15fr]">
        <div className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>{editingResourceId ? 'Edit resource' : 'Add resource'}</CardTitle>
              <CardDescription>Store files, links, and reusable notes with tags and metadata.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="space-y-2">
                <Label>Resource type</Label>
                <Select value={form.resource_type} onValueChange={(value: ResourceType) => setForm((current) => ({ ...current, resource_type: value }))}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="file">File</SelectItem>
                    <SelectItem value="link">Link</SelectItem>
                    <SelectItem value="note">Note</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label>Name</Label>
                <Input value={form.name} onChange={(event) => setForm((current) => ({ ...current, name: event.target.value }))} placeholder="Printable practice" />
              </div>
              <div className="space-y-2">
                <Label>Description / note body</Label>
                <Textarea value={form.description} onChange={(event) => setForm((current) => ({ ...current, description: event.target.value }))} placeholder="How to use this resource, note body, or summary." />
              </div>
              {form.resource_type === 'link' ? (
                <div className="space-y-2">
                  <Label>External URL</Label>
                  <Input value={form.url} onChange={(event) => setForm((current) => ({ ...current, url: event.target.value }))} placeholder="https://example.com/resource" />
                </div>
              ) : null}
              {form.resource_type === 'file' && !editingResourceId ? (
                <div className="space-y-2">
                  <Label>File</Label>
                  <Input type="file" accept="application/pdf,image/*,text/plain" onChange={(event) => setForm((current) => ({ ...current, file: event.target.files?.[0] ?? null }))} />
                </div>
              ) : null}
              {form.resource_type === 'file' && editingResourceId ? (
                <p className="text-xs text-muted-foreground">File replacement is not supported in-place yet. Create a new file resource if the attachment changes.</p>
              ) : null}
              <div className="space-y-2">
                <Label>Tags</Label>
                <Input value={form.tags} onChange={(event) => setForm((current) => ({ ...current, tags: event.target.value }))} placeholder="worksheet, math, warmup" />
              </div>
              <div className="space-y-2">
                <Label>Metadata JSON</Label>
                <Textarea value={form.metadata} onChange={(event) => setForm((current) => ({ ...current, metadata: event.target.value }))} className="min-h-28 font-mono text-xs" />
              </div>
              <div className="flex gap-2">
                <Button onClick={() => void saveResource()} disabled={saving || (form.resource_type === 'file' && !editingResourceId && !form.file)}>
                  {editingResourceId ? 'Update resource' : 'Create resource'}
                </Button>
                {editingResourceId ? (
                  <Button variant="outline" onClick={resetForm}>
                    Cancel
                  </Button>
                ) : null}
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Link resources to lessons</CardTitle>
              <CardDescription>Choose a lesson, then link or unlink resources from the library list.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-2">
              <Label>Lesson</Label>
              <Select value={selectedLessonId || (lessonOptions[0] ? String(lessonOptions[0].id) : '')} onValueChange={setSelectedLessonId}>
                <SelectTrigger>
                  <SelectValue placeholder="Choose lesson" />
                </SelectTrigger>
                <SelectContent>
                  {lessonOptions.map((lesson) => (
                    <SelectItem key={lesson.id} value={String(lesson.id)}>
                      {lesson.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </CardContent>
          </Card>
        </div>

        <Card>
          <CardHeader>
            <CardTitle>Resource library</CardTitle>
            <CardDescription>Search by title, filter by tag or type, and attach materials to lessons.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid gap-3 md:grid-cols-[1fr_180px_180px_auto]">
              <Input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search resources" />
              <Input value={tag} onChange={(event) => setTag(event.target.value)} placeholder="Tag filter" />
              <Select value={resourceTypeFilter} onValueChange={(value: ResourceType | 'all') => setResourceTypeFilter(value)}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All types</SelectItem>
                  <SelectItem value="file">Files</SelectItem>
                  <SelectItem value="link">Links</SelectItem>
                  <SelectItem value="note">Notes</SelectItem>
                </SelectContent>
              </Select>
              <Button onClick={() => void load({ search, tag, resource_type: resourceTypeFilter })}>Apply filters</Button>
            </div>

            {resources.length ? (
              <div className="space-y-3">
                {resources.map((resource) => {
                  const selectedLessonNumber = selectedLessonId ? Number(selectedLessonId) : null
                  const linkedToSelectedLesson = selectedLessonNumber ? resource.lesson_ids.includes(selectedLessonNumber) : false
                  return (
                    <div key={resource.id} className="rounded-lg border p-4">
                      <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
                        <div className="space-y-2">
                          <div className="flex flex-wrap items-center gap-2">
                            <h3 className="font-semibold">{resource.name}</h3>
                            <Badge variant="secondary">{resource.resource_type}</Badge>
                            {resource.tags.map((item) => (
                              <Badge key={item} variant="outline">
                                {item}
                              </Badge>
                            ))}
                          </div>
                          {resource.description ? <p className="text-sm text-muted-foreground">{resource.description}</p> : null}
                          <div className="flex flex-wrap gap-3 text-sm">
                            {resource.url ? (
                              <a className="text-primary underline-offset-4 hover:underline" href={resource.url} target="_blank" rel="noreferrer">
                                Open link
                              </a>
                            ) : null}
                            {resource.file_url ? (
                              <a className="text-primary underline-offset-4 hover:underline" href={resource.file_url} target="_blank" rel="noreferrer">
                                Open file
                              </a>
                            ) : null}
                          </div>
                          {resource.lesson_ids.length ? (
                            <div className="flex flex-wrap gap-2">
                              {resource.lesson_ids.map((lessonId) => (
                                <Badge key={lessonId} variant="secondary">
                                  {lessonLabelMap[lessonId] || `Lesson ${lessonId}`}
                                </Badge>
                              ))}
                            </div>
                          ) : (
                            <p className="text-xs text-muted-foreground">Not linked to any lessons yet.</p>
                          )}
                        </div>
                        <div className="flex flex-wrap gap-2">
                          {selectedLessonNumber ? (
                            linkedToSelectedLesson ? (
                              <Button
                                size="sm"
                                variant="outline"
                                onClick={() => void api.unlinkResourceFromLesson(selectedLessonNumber, resource.id).then(() => load({ search, tag, resource_type: resourceTypeFilter }))}
                              >
                                Unlink from lesson
                              </Button>
                            ) : (
                              <Button
                                size="sm"
                                onClick={() => void api.linkResourceToLesson(selectedLessonNumber, resource.id).then(() => load({ search, tag, resource_type: resourceTypeFilter }))}
                              >
                                Link to lesson
                              </Button>
                            )
                          ) : null}
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={() => {
                              setEditingResourceId(resource.id)
                              setForm({
                                name: resource.name,
                                description: resource.description || '',
                                resource_type: resource.resource_type,
                                url: resource.url || '',
                                tags: resource.tags.join(', '),
                                metadata: JSON.stringify(resource.metadata, null, 2),
                                file: null,
                              })
                            }}
                          >
                            Edit
                          </Button>
                          <Button size="sm" variant="destructive" onClick={() => void api.deleteResource(resource.id).then(() => load({ search, tag, resource_type: resourceTypeFilter }))}>
                            Delete
                          </Button>
                        </div>
                      </div>
                    </div>
                  )
                })}
              </div>
            ) : (
              <EmptyState title="No resources yet" description="Upload a file, add a link, or save a reusable note to start your library." />
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
