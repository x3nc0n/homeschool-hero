import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { Trash2 } from 'lucide-react'
import { useAuth } from '@/context/AuthContext'
import { api } from '@/lib/api'
import type { CurriculumImportDetail } from '@/types/api'
import { formatEstimatedHours, normalizeCurriculumImport } from '@/lib/curriculumImport'
import { EmptyState } from '@/components/common/EmptyState'
import { ErrorState } from '@/components/common/ErrorState'
import { CurriculumImportTree } from '@/components/features/CurriculumImportTree'
import { LoadingState } from '@/components/common/LoadingState'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardAction, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '@/components/ui/card'

function formatDate(value: string | null | undefined) {
  if (!value) return '—'
  return new Date(value).toLocaleDateString()
}

export function CurriculumImportDetailPage() {
  const { curriculumId } = useParams()
  const navigate = useNavigate()
  const { canManageCurriculum } = useAuth()
  const parsedCurriculumId = Number(curriculumId)
  const [curriculum, setCurriculum] = useState<CurriculumImportDetail | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [activating, setActivating] = useState(false)
  const [deleting, setDeleting] = useState(false)
  const [confirmDelete, setConfirmDelete] = useState(false)

  const load = useCallback(async () => {
    if (!Number.isFinite(parsedCurriculumId)) return
    setLoading(true)
    setError('')
    try {
      setCurriculum(await api.getImportedCurriculum(parsedCurriculumId))
    } catch (loadError) {
      setCurriculum(null)
      setError(loadError instanceof Error ? loadError.message : 'Unable to load curriculum details.')
    } finally {
      setLoading(false)
    }
  }, [parsedCurriculumId])

  useEffect(() => {
    void load()
  }, [load])

  const normalized = useMemo(() => (curriculum ? normalizeCurriculumImport(curriculum) : null), [curriculum])

  if (!Number.isFinite(parsedCurriculumId)) {
    return <ErrorState message="Invalid curriculum selected." />
  }

  if (loading) {
    return <LoadingState message="Loading curriculum detail…" />
  }

  if (error && !curriculum) {
    return <ErrorState message={error} onRetry={() => void load()} />
  }

  if (!curriculum || !normalized) {
    return <EmptyState title="Curriculum not found" description="The imported curriculum may have been deleted or is no longer available." />
  }

  const handleActivate = async () => {
    setActivating(true)
    setError('')
    try {
      const activation = await api.activateImportedCurriculum(curriculum.id)
      setCurriculum((current) =>
        current
          ? {
              ...current,
              is_activated: true,
              last_activated_at: activation.activated_at,
            }
          : current,
      )
    } catch (activationError) {
      setError(activationError instanceof Error ? activationError.message : 'Unable to activate curriculum.')
    } finally {
      setActivating(false)
    }
  }

  const handleDelete = async () => {
    setDeleting(true)
    setError('')
    try {
      await api.deleteImportedCurriculum(curriculum.id)
      navigate('/curriculum')
    } catch (deleteError) {
      setError(deleteError instanceof Error ? deleteError.message : 'Unable to delete curriculum.')
    } finally {
      setDeleting(false)
    }
  }

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <div>
            <CardTitle>{curriculum.name}</CardTitle>
            <CardDescription>{curriculum.description || 'Imported curriculum detail view.'}</CardDescription>
          </div>
          <CardAction className="flex flex-wrap gap-2">
            <Button asChild size="sm" variant="outline">
              <Link to="/curriculum">Back to library</Link>
            </Button>
            {canManageCurriculum && !curriculum.is_activated ? (
              <Button size="sm" disabled={activating} onClick={() => void handleActivate()}>
                {activating ? 'Activating…' : 'Activate'}
              </Button>
            ) : null}
            {canManageCurriculum ? (
              <Button size="icon" variant="ghost" onClick={() => setConfirmDelete((current) => !current)}>
                <Trash2 className="h-4 w-4" />
                <span className="sr-only">Delete curriculum</span>
              </Button>
            ) : null}
          </CardAction>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="flex flex-wrap gap-2">
            <Badge variant={curriculum.is_activated ? 'secondary' : 'outline'}>{curriculum.is_activated ? 'Activated' : 'Imported'}</Badge>
            {normalized.metadata.gradeLevels.map((gradeLevel) => (
              <Badge key={gradeLevel} variant="outline">
                Grade {gradeLevel}
              </Badge>
            ))}
            {normalized.metadata.standardsAlignment.map((standard) => (
              <Badge key={standard} variant="outline">
                {standard}
              </Badge>
            ))}
          </div>
          <p className="text-sm text-muted-foreground">
            Imported {formatDate(curriculum.created_at)} · Last activated {formatDate(curriculum.last_activated_at)}
          </p>
          {normalized.metadata.prerequisites.length ? (
            <div className="space-y-2 text-sm">
              <p className="font-medium">Prerequisites</p>
              <div className="flex flex-wrap gap-2">
                {normalized.metadata.prerequisites.map((item) => (
                  <Badge key={item} variant="outline">
                    {item}
                  </Badge>
                ))}
              </div>
            </div>
          ) : null}
        </CardContent>
        {confirmDelete ? (
          <CardFooter className="justify-between gap-3">
            <p className="text-sm text-muted-foreground">Delete this imported curriculum and remove it from the library?</p>
            <div className="flex gap-2">
              <Button size="sm" variant="outline" onClick={() => setConfirmDelete(false)}>
                Cancel
              </Button>
              <Button size="sm" variant="destructive" disabled={deleting} onClick={() => void handleDelete()}>
                {deleting ? 'Deleting…' : 'Confirm delete'}
              </Button>
            </div>
          </CardFooter>
        ) : null}
      </Card>

      {error ? <ErrorState message={error} onRetry={() => void load()} /> : null}

      <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_300px]">
        <Card>
          <CardHeader>
            <CardTitle>Curriculum tree</CardTitle>
            <CardDescription>Browse the full imported subject, unit, and lesson structure.</CardDescription>
          </CardHeader>
          <CardContent>
            <CurriculumImportTree curriculum={normalized} />
          </CardContent>
        </Card>

        <div className="space-y-4">
          <Card size="sm">
            <CardHeader>
              <CardDescription>Subjects</CardDescription>
              <CardTitle>{normalized.subjectCount}</CardTitle>
            </CardHeader>
          </Card>
          <Card size="sm">
            <CardHeader>
              <CardDescription>Units / lessons</CardDescription>
              <CardTitle>
                {normalized.unitCount} / {normalized.lessonCount}
              </CardTitle>
            </CardHeader>
          </Card>
          <Card size="sm">
            <CardHeader>
              <CardDescription>Estimated hours</CardDescription>
              <CardTitle>{formatEstimatedHours(normalized.estimatedHours)}</CardTitle>
            </CardHeader>
          </Card>
          <Card size="sm">
            <CardHeader>
              <CardTitle>Source</CardTitle>
              <CardDescription>{normalized.source || 'manual'}</CardDescription>
            </CardHeader>
            <CardContent className="text-sm text-muted-foreground">Schema version {normalized.schemaVersion}</CardContent>
          </Card>
        </div>
      </div>
    </div>
  )
}
