import { type ChangeEvent, useMemo, useState } from 'react'
import { CheckCircle2, FileJson, Upload } from 'lucide-react'
import { Link } from 'react-router-dom'
import { api } from '@/lib/api'
import type { CurriculumImportDetail, CurriculumImportSchema } from '@/types/api'
import { buildCurriculumImportExample, formatEstimatedHours, parseCurriculumImportJson, type NormalizedCurriculumImport } from '@/lib/curriculumImport'
import { CurriculumImportTree } from '@/components/features/CurriculumImportTree'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardAction, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Textarea } from '@/components/ui/textarea'

type CurriculumImportWizardProps = {
  schema: CurriculumImportSchema | null
  onCancel: () => void
  onImported: () => void
}

const STEPS = [
  'Upload method',
  'Validation & preview',
  'Review & confirm',
  'Success',
] as const

function StatsGrid({ curriculum }: { curriculum: NormalizedCurriculumImport }) {
  return (
    <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
      <Card size="sm">
        <CardHeader>
          <CardDescription>Subjects</CardDescription>
          <CardTitle>{curriculum.subjectCount}</CardTitle>
        </CardHeader>
      </Card>
      <Card size="sm">
        <CardHeader>
          <CardDescription>Units</CardDescription>
          <CardTitle>{curriculum.unitCount}</CardTitle>
        </CardHeader>
      </Card>
      <Card size="sm">
        <CardHeader>
          <CardDescription>Lessons</CardDescription>
          <CardTitle>{curriculum.lessonCount}</CardTitle>
        </CardHeader>
      </Card>
      <Card size="sm">
        <CardHeader>
          <CardDescription>Estimated hours</CardDescription>
          <CardTitle>{formatEstimatedHours(curriculum.estimatedHours)}</CardTitle>
        </CardHeader>
      </Card>
    </div>
  )
}

export function CurriculumImportWizard({ schema, onCancel, onImported }: CurriculumImportWizardProps) {
  const [step, setStep] = useState<(typeof STEPS)[number]>(STEPS[0])
  const [method, setMethod] = useState<'paste' | 'file' | 'url'>('paste')
  const [jsonText, setJsonText] = useState('')
  const [fileName, setFileName] = useState('')
  const [error, setError] = useState('')
  const [saving, setSaving] = useState(false)
  const [activating, setActivating] = useState(false)
  const [parsed, setParsed] = useState<NormalizedCurriculumImport | null>(null)
  const [rawPayload, setRawPayload] = useState<Record<string, unknown> | null>(null)
  const [createdCurriculum, setCreatedCurriculum] = useState<CurriculumImportDetail | null>(null)

  const requiredFields = useMemo(() => {
    const required = schema?.required
    if (Array.isArray(required)) {
      return required.filter((value): value is string => typeof value === 'string')
    }
    return ['name', 'grade_levels', 'subjects']
  }, [schema])

  const resetError = () => setError('')

  const loadExample = () => {
    resetError()
    setMethod('paste')
    setFileName('')
    setJsonText(JSON.stringify(buildCurriculumImportExample(), null, 2))
  }

  const validateAndPreview = () => {
    try {
      resetError()
      const result = parseCurriculumImportJson(jsonText)
      setParsed(result.normalized)
      setRawPayload(result.raw)
      setStep(STEPS[1])
    } catch (validationError) {
      setError(validationError instanceof Error ? validationError.message : 'Unable to validate curriculum JSON.')
    }
  }

  const handleFileSelected = async (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]
    if (!file) return
    setMethod('file')
    setFileName(file.name)
    setJsonText(await file.text())
    resetError()
  }

  const handleImport = async () => {
    if (!rawPayload) return

    setSaving(true)
    resetError()
    try {
      const created = await api.importCurriculum(rawPayload)
      setCreatedCurriculum(created)
      setStep(STEPS[3])
      onImported()
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : 'Unable to import curriculum right now.')
    } finally {
      setSaving(false)
    }
  }

  const handleActivateNow = async () => {
    if (!createdCurriculum) return
    setActivating(true)
    resetError()
    try {
      const activation = await api.activateImportedCurriculum(createdCurriculum.id)
      setCreatedCurriculum((current) =>
        current
          ? {
              ...current,
              is_activated: true,
              last_activated_at: activation.activated_at,
            }
          : current,
      )
      onImported()
    } catch (activationError) {
      setError(activationError instanceof Error ? activationError.message : 'Unable to activate curriculum right now.')
    } finally {
      setActivating(false)
    }
  }

  return (
    <Card>
      <CardHeader>
        <div>
          <CardTitle>Import curriculum</CardTitle>
          <CardDescription>Bring in a structured curriculum JSON file, preview the tree, then import it into the library.</CardDescription>
        </div>
        <CardAction className="flex gap-2">
          <Button size="sm" variant="outline" onClick={loadExample}>
            <FileJson className="h-4 w-4" />
            Load example
          </Button>
          <Button size="sm" variant="ghost" onClick={onCancel}>
            Close
          </Button>
        </CardAction>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="flex flex-wrap gap-2">
          {STEPS.map((label, index) => (
            <Badge key={label} variant={label === step ? 'secondary' : 'outline'}>
              {index + 1}. {label}
            </Badge>
          ))}
        </div>

        {error ? (
          <div role="alert" className="rounded-lg border border-destructive/30 bg-destructive/5 px-4 py-3 text-sm text-destructive">
            {error}
          </div>
        ) : null}

        {step === STEPS[0] ? (
          <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_280px]">
            <div className="space-y-4">
              <Tabs value={method} onValueChange={(value) => setMethod(value as 'paste' | 'file' | 'url')}>
                <TabsList>
                  <TabsTrigger value="paste">Paste JSON</TabsTrigger>
                  <TabsTrigger value="file">Upload file</TabsTrigger>
                  <TabsTrigger value="url" disabled>
                    URL (soon)
                  </TabsTrigger>
                </TabsList>
                <TabsContent value="paste" className="space-y-2">
                  <Label htmlFor="curriculum-import-json">Curriculum JSON</Label>
                  <Textarea
                    id="curriculum-import-json"
                    className="min-h-[360px] font-mono text-xs"
                    placeholder='{"name":"Biology Foundations","grade_levels":["8"],"subjects":[...]}'
                    value={jsonText}
                    onChange={(event) => setJsonText(event.target.value)}
                  />
                </TabsContent>
                <TabsContent value="file" className="space-y-3">
                  <div className="space-y-2">
                    <Label htmlFor="curriculum-import-file">Upload .json file</Label>
                    <Input id="curriculum-import-file" accept=".json,application/json" type="file" onChange={(event) => void handleFileSelected(event)} />
                  </div>
                  <div className="rounded-lg border border-dashed p-4 text-sm text-muted-foreground">
                    {fileName ? `Loaded ${fileName}. Continue to validate and preview it.` : 'Choose a JSON file and we will preview it before importing.'}
                  </div>
                  <Textarea className="min-h-[260px] font-mono text-xs" readOnly value={jsonText} />
                </TabsContent>
                <TabsContent value="url">
                  <div className="rounded-lg border border-dashed p-4 text-sm text-muted-foreground">
                    URL imports are planned for a later phase.
                  </div>
                </TabsContent>
              </Tabs>
            </div>

            <Card size="sm">
              <CardHeader>
                <CardTitle>Standard format</CardTitle>
                <CardDescription>These are the required top-level fields we expect in the import contract today.</CardDescription>
              </CardHeader>
              <CardContent className="space-y-3 text-sm">
                <div className="flex flex-wrap gap-2">
                  {requiredFields.map((field) => (
                    <Badge key={field} variant="outline">
                      {field}
                    </Badge>
                  ))}
                </div>
                <p className="text-muted-foreground">Each subject contains units, and each unit contains lessons with optional objectives, resources, and time estimates.</p>
              </CardContent>
            </Card>
          </div>
        ) : null}

        {step === STEPS[1] && parsed ? (
          <div className="space-y-4">
            <StatsGrid curriculum={parsed} />
            <Card size="sm">
              <CardHeader>
                <CardTitle>{parsed.name}</CardTitle>
                <CardDescription>Preview the curriculum tree before you confirm the import.</CardDescription>
              </CardHeader>
              <CardContent>
                <CurriculumImportTree curriculum={parsed} />
              </CardContent>
            </Card>
          </div>
        ) : null}

        {step === STEPS[2] && parsed ? (
          <div className="space-y-4">
            <StatsGrid curriculum={parsed} />
            <Card size="sm">
              <CardHeader>
                <CardTitle>Review and confirm</CardTitle>
                <CardDescription>We will import the curriculum exactly as previewed here.</CardDescription>
              </CardHeader>
              <CardContent className="space-y-3 text-sm">
                {parsed.description ? <p className="text-muted-foreground">{parsed.description}</p> : null}
                <div className="flex flex-wrap gap-2">
                  {parsed.metadata.gradeLevels.map((gradeLevel) => (
                    <Badge key={gradeLevel} variant="outline">
                      Grade {gradeLevel}
                    </Badge>
                  ))}
                  {parsed.metadata.standardsAlignment.map((standard) => (
                    <Badge key={standard} variant="outline">
                      {standard}
                    </Badge>
                  ))}
                </div>
              </CardContent>
            </Card>
          </div>
        ) : null}

        {step === STEPS[3] && createdCurriculum ? (
          <div className="space-y-4">
            <div className="rounded-lg border border-emerald-500/30 bg-emerald-500/10 p-4">
              <div className="flex items-start gap-3">
                <CheckCircle2 className="mt-0.5 h-5 w-5 text-emerald-600" />
                <div className="space-y-1">
                  <p className="font-medium text-emerald-900 dark:text-emerald-100">{createdCurriculum.name} was imported successfully.</p>
                  <p className="text-sm text-emerald-800 dark:text-emerald-200">You can activate it now or review it in the curriculum detail view first.</p>
                </div>
              </div>
            </div>

            <div className="flex flex-wrap gap-2">
              <Button disabled={createdCurriculum.is_activated || activating} onClick={() => void handleActivateNow()}>
                <Upload className="h-4 w-4" />
                {createdCurriculum.is_activated ? 'Activated' : activating ? 'Activating…' : 'Activate now'}
              </Button>
              <Button asChild variant="outline">
                <Link to={`/curriculum/${createdCurriculum.id}`}>View details</Link>
              </Button>
              <Button variant="ghost" onClick={onCancel}>
                Done
              </Button>
            </div>
          </div>
        ) : null}

        <div className="flex flex-wrap justify-between gap-2 border-t pt-4">
          <Button variant="ghost" onClick={onCancel}>
            Cancel
          </Button>

          <div className="flex gap-2">
            {step === STEPS[1] ? (
              <>
                <Button variant="outline" onClick={() => setStep(STEPS[0])}>
                  Back
                </Button>
                <Button onClick={() => setStep(STEPS[2])}>Continue</Button>
              </>
            ) : null}
            {step === STEPS[2] ? (
              <>
                <Button variant="outline" onClick={() => setStep(STEPS[1])}>
                  Back
                </Button>
                <Button disabled={saving} onClick={() => void handleImport()}>
                  {saving ? 'Importing…' : 'Import curriculum'}
                </Button>
              </>
            ) : null}
            {step === STEPS[0] ? <Button onClick={validateAndPreview}>Validate & preview</Button> : null}
          </div>
        </div>
      </CardContent>
    </Card>
  )
}
