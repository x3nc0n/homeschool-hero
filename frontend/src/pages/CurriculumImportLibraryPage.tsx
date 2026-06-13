import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { Trash2 } from 'lucide-react'
import { useAuth } from '@/context/AuthContext'
import { api } from '@/lib/api'
import type { CurriculumImportSchema, CurriculumImportSummary } from '@/types/api'
import { formatEstimatedHours } from '@/lib/curriculumImport'
import { EmptyState } from '@/components/common/EmptyState'
import { ErrorState } from '@/components/common/ErrorState'
import { CurriculumSourceBrowser } from '@/components/features/CurriculumSourceBrowser'
import { CurriculumImportWizard } from '@/components/features/CurriculumImportWizard'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardAction, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '@/components/ui/card'
import { LoadingState } from '@/components/common/LoadingState'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'

function getGradeLevels(curriculum: CurriculumImportSummary) {
  return curriculum.grade_levels?.length ? curriculum.grade_levels : curriculum.metadata?.grade_levels ?? []
}

function getEstimatedHours(curriculum: CurriculumImportSummary) {
  return curriculum.estimated_hours ?? curriculum.metadata?.estimated_hours ?? null
}

function formatDate(value: string | null | undefined) {
  if (!value) return '—'
  return new Date(value).toLocaleDateString()
}

export function CurriculumImportLibraryPage() {
  const { canManageCurriculum } = useAuth()
  const [curricula, setCurricula] = useState<CurriculumImportSummary[]>([])
  const [schema, setSchema] = useState<CurriculumImportSchema | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [wizardOpen, setWizardOpen] = useState(false)
  const [activatingId, setActivatingId] = useState<number | null>(null)
  const [deletingId, setDeletingId] = useState<number | null>(null)
  const [confirmDeleteId, setConfirmDeleteId] = useState<number | null>(null)
  const [activeTab, setActiveTab] = useState<'library' | 'sources'>('library')

  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const [curriculaResult, schemaResult] = await Promise.allSettled([api.listImportedCurricula(), api.getCurriculumImportSchema()])
      if (curriculaResult.status === 'fulfilled') {
        setCurricula(curriculaResult.value)
      } else {
        throw curriculaResult.reason
      }
      if (schemaResult.status === 'fulfilled') {
        setSchema(schemaResult.value)
      } else {
        setSchema(null)
      }
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : 'Unable to load imported curricula.')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void load()
  }, [load])

  const totals = useMemo(
    () =>
      curricula.reduce(
        (summary, curriculum) => {
          summary.subjects += curriculum.subject_count
          summary.units += curriculum.unit_count
          summary.lessons += curriculum.lesson_count
          summary.activated += curriculum.is_activated ? 1 : 0
          return summary
        },
        { subjects: 0, units: 0, lessons: 0, activated: 0 },
      ),
    [curricula],
  )

  const requiredFields = useMemo(() => {
    const required = schema?.required
    if (Array.isArray(required)) {
      return required.filter((value): value is string => typeof value === 'string')
    }
    return ['name', 'grade_levels', 'subjects']
  }, [schema])

  const handleActivate = async (curriculumId: number) => {
    setActivatingId(curriculumId)
    setError('')
    try {
      await api.activateImportedCurriculum(curriculumId)
      await load()
    } catch (activationError) {
      setError(activationError instanceof Error ? activationError.message : 'Unable to activate curriculum.')
    } finally {
      setActivatingId(null)
    }
  }

  const handleDelete = async (curriculumId: number) => {
    setDeletingId(curriculumId)
    setError('')
    try {
      await api.deleteImportedCurriculum(curriculumId)
      setConfirmDeleteId(null)
      await load()
    } catch (deleteError) {
      setError(deleteError instanceof Error ? deleteError.message : 'Unable to delete curriculum.')
    } finally {
      setDeletingId(null)
    }
  }

  if (loading) {
    return <LoadingState message="Loading curriculum library…" />
  }

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <div>
            <CardTitle>Curriculum library</CardTitle>
            <CardDescription>Import standardized JSON, browse external sources, or use AI-assisted document parsing before activating curricula for your school year.</CardDescription>
          </div>
          {canManageCurriculum ? (
            <CardAction>
              <Button size="sm" onClick={() => setWizardOpen((current) => !current)}>
                {wizardOpen ? 'Close import' : 'Import curriculum'}
              </Button>
            </CardAction>
          ) : null}
        </CardHeader>
        <CardContent className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
          <Card size="sm">
            <CardHeader>
              <CardDescription>Library items</CardDescription>
              <CardTitle>{curricula.length}</CardTitle>
            </CardHeader>
          </Card>
          <Card size="sm">
            <CardHeader>
              <CardDescription>Activated</CardDescription>
              <CardTitle>{totals.activated}</CardTitle>
            </CardHeader>
          </Card>
          <Card size="sm">
            <CardHeader>
              <CardDescription>Subjects / units</CardDescription>
              <CardTitle>
                {totals.subjects} / {totals.units}
              </CardTitle>
            </CardHeader>
          </Card>
          <Card size="sm">
            <CardHeader>
              <CardDescription>Lessons</CardDescription>
              <CardTitle>{totals.lessons}</CardTitle>
            </CardHeader>
          </Card>
        </CardContent>
      </Card>

      {error ? <ErrorState message={error} onRetry={() => void load()} /> : null}

      {wizardOpen && canManageCurriculum ? <CurriculumImportWizard schema={schema} onCancel={() => setWizardOpen(false)} onImported={() => void load()} /> : null}

      <Tabs value={activeTab} onValueChange={(value) => setActiveTab(value as 'library' | 'sources')} className="space-y-4">
        <TabsList>
          <TabsTrigger value="library">My Library</TabsTrigger>
          <TabsTrigger value="sources">Browse Sources</TabsTrigger>
        </TabsList>

        <TabsContent value="library" className="space-y-4">
          <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_280px]">
            <div className="space-y-4">
              {curricula.length ? (
                curricula.map((curriculum) => {
                  const gradeLevels = getGradeLevels(curriculum)
                  const estimatedHours = getEstimatedHours(curriculum)
                  const isDeleting = deletingId === curriculum.id
                  const isActivating = activatingId === curriculum.id
                  const confirmingDelete = confirmDeleteId === curriculum.id

                  return (
                    <Card key={curriculum.id}>
                      <CardHeader>
                        <div>
                          <CardTitle>{curriculum.name}</CardTitle>
                          <CardDescription>{curriculum.description || 'Imported curriculum ready for preview and activation.'}</CardDescription>
                        </div>
                        <CardAction className="flex gap-2">
                          <Button asChild size="sm" variant="outline">
                            <Link to={`/curriculum/${curriculum.id}`}>View details</Link>
                          </Button>
                          {canManageCurriculum && !curriculum.is_activated ? (
                            <Button size="sm" disabled={isActivating} onClick={() => void handleActivate(curriculum.id)}>
                              {isActivating ? 'Activating…' : 'Activate'}
                            </Button>
                          ) : null}
                          {canManageCurriculum ? (
                            <Button size="icon" variant="ghost" onClick={() => setConfirmDeleteId(confirmingDelete ? null : curriculum.id)}>
                              <Trash2 className="h-4 w-4" />
                              <span className="sr-only">Delete curriculum</span>
                            </Button>
                          ) : null}
                        </CardAction>
                      </CardHeader>
                      <CardContent className="space-y-3">
                        <div className="flex flex-wrap gap-2">
                          <Badge variant={curriculum.is_activated ? 'secondary' : 'outline'}>{curriculum.is_activated ? 'Activated' : 'Imported'}</Badge>
                          {gradeLevels.map((gradeLevel) => (
                            <Badge key={gradeLevel} variant="outline">
                              Grade {gradeLevel}
                            </Badge>
                          ))}
                        </div>
                        <div className="grid gap-3 text-sm text-muted-foreground md:grid-cols-4">
                          <div>
                            <p className="font-medium text-foreground">Subjects</p>
                            <p>{curriculum.subject_count}</p>
                          </div>
                          <div>
                            <p className="font-medium text-foreground">Units</p>
                            <p>{curriculum.unit_count}</p>
                          </div>
                          <div>
                            <p className="font-medium text-foreground">Lessons</p>
                            <p>{curriculum.lesson_count}</p>
                          </div>
                          <div>
                            <p className="font-medium text-foreground">Estimated hours</p>
                            <p>{formatEstimatedHours(estimatedHours)}</p>
                          </div>
                        </div>
                        <p className="text-xs text-muted-foreground">
                          Imported {formatDate(curriculum.created_at)}{curriculum.last_activated_at ? ` · Last activated ${formatDate(curriculum.last_activated_at)}` : ''}
                        </p>
                      </CardContent>
                      {confirmingDelete ? (
                        <CardFooter className="justify-between gap-3">
                          <p className="text-sm text-muted-foreground">Delete this curriculum from the library? This cannot be undone.</p>
                          <div className="flex gap-2">
                            <Button size="sm" variant="outline" onClick={() => setConfirmDeleteId(null)}>
                              Cancel
                            </Button>
                            <Button size="sm" variant="destructive" disabled={isDeleting} onClick={() => void handleDelete(curriculum.id)}>
                              {isDeleting ? 'Deleting…' : 'Confirm delete'}
                            </Button>
                          </div>
                        </CardFooter>
                      ) : null}
                    </Card>
                  )
                })
              ) : (
                <EmptyState title="No imported curricula yet" description="Import a curriculum JSON file to create your first reusable library item." />
              )}
            </div>

            <Card size="sm">
              <CardHeader>
                <CardTitle>Schema snapshot</CardTitle>
                <CardDescription>Quick reference for the current curriculum import contract.</CardDescription>
              </CardHeader>
              <CardContent className="space-y-3 text-sm">
                <div className="flex flex-wrap gap-2">
                  {requiredFields.map((field) => (
                    <Badge key={field} variant="outline">
                      {field}
                    </Badge>
                  ))}
                </div>
                <p className="text-muted-foreground">The preview tree expects subjects → units → lessons, with optional objectives, resources, prerequisites, and time estimates on lessons.</p>
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        <TabsContent value="sources" className="space-y-4">
          <CurriculumSourceBrowser onImported={() => void load()} onOpenLibrary={() => setActiveTab('library')} />
        </TabsContent>
      </Tabs>
    </div>
  )
}
