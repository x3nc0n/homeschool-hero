import { type ChangeEvent, type DragEvent, useEffect, useMemo, useState } from 'react'
import { CheckCircle2, FileJson, FileText, Sparkles, Upload, WandSparkles } from 'lucide-react'
import { Link } from 'react-router-dom'
import { useAuth } from '@/context/AuthContext'
import { useCapabilities } from '@/context/CapabilitiesContext'
import { api } from '@/lib/api'
import type { CurriculumAiImportDraftResponse, CurriculumImportDetail, CurriculumImportDocument, CurriculumImportSchema } from '@/types/api'
import {
  buildCurriculumImportExample,
  formatEstimatedHours,
  normalizeCurriculumImport,
  parseCurriculumImportJson,
  toCurriculumImportPayload,
  type NormalizedCurriculumImport,
} from '@/lib/curriculumImport'
import { CurriculumImportTree } from '@/components/features/CurriculumImportTree'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardAction, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Progress } from '@/components/ui/progress'
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

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === 'object' && !Array.isArray(value)
}

function getAiDraftResult(response: CurriculumAiImportDraftResponse | CurriculumImportDocument | Record<string, unknown>) {
  if (isRecord(response) && isRecord(response.draft)) {
    return {
      draft: response.draft,
      warnings: Array.isArray(response.warnings) ? response.warnings.filter((warning): warning is string => typeof warning === 'string') : [],
      sourceLabel: typeof response.source_label === 'string' ? response.source_label : '',
    }
  }

  return {
    draft: isRecord(response) ? response : (toCurriculumImportPayload(normalizeCurriculumImport(buildCurriculumImportExample())) as unknown as Record<string, unknown>),
    warnings: [],
    sourceLabel: '',
  }
}

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

function AnalysisSkeleton() {
  return (
    <div className="space-y-3 rounded-lg border border-dashed p-4">
      <div className="h-4 w-2/5 animate-pulse rounded bg-muted" />
      <div className="h-3 w-full animate-pulse rounded bg-muted" />
      <div className="h-3 w-4/5 animate-pulse rounded bg-muted" />
      <div className="grid gap-3 md:grid-cols-2">
        <div className="h-20 animate-pulse rounded-lg bg-muted" />
        <div className="h-20 animate-pulse rounded-lg bg-muted" />
      </div>
    </div>
  )
}

export function CurriculumImportWizard({ schema, onCancel, onImported }: CurriculumImportWizardProps) {
  const { isFeatureEnabled } = useAuth()
  const { capabilities } = useCapabilities()
  const [step, setStep] = useState<(typeof STEPS)[number]>(STEPS[0])
  const [importMode, setImportMode] = useState<'manual' | 'ai'>('manual')
  const [method, setMethod] = useState<'paste' | 'file' | 'url'>('paste')
  const [jsonText, setJsonText] = useState('')
  const [fileName, setFileName] = useState('')
  const [error, setError] = useState('')
  const [saving, setSaving] = useState(false)
  const [activating, setActivating] = useState(false)
  const [parsed, setParsed] = useState<NormalizedCurriculumImport | null>(null)
  const [rawPayload, setRawPayload] = useState<Record<string, unknown> | null>(null)
  const [createdCurriculum, setCreatedCurriculum] = useState<CurriculumImportDetail | null>(null)
  const [aiInputMethod, setAiInputMethod] = useState<'file' | 'url'>('file')
  const [aiFile, setAiFile] = useState<File | null>(null)
  const [aiUrl, setAiUrl] = useState('')
  const [aiSourceLabel, setAiSourceLabel] = useState('')
  const [aiWarnings, setAiWarnings] = useState<string[]>([])
  const [editablePayloadText, setEditablePayloadText] = useState('')
  const [analyzing, setAnalyzing] = useState(false)
  const [analysisProgress, setAnalysisProgress] = useState(0)
  const [isDragging, setIsDragging] = useState(false)

  const requiredFields = useMemo(() => {
    const required = schema?.required
    if (Array.isArray(required)) {
      return required.filter((value): value is string => typeof value === 'string')
    }
    return ['name', 'grade_levels', 'subjects']
  }, [schema])

  const aiFeatureEnabled = isFeatureEnabled('curriculum_ai_import')
  const aiConfigured = import.meta.env.DEV || (capabilities.ai_grading.enabled && capabilities.ocr.enabled)
  const aiAvailable = aiFeatureEnabled && aiConfigured
  const aiAvailabilityMessage = !aiFeatureEnabled
    ? 'AI import is coming soon for this family.'
    : 'AI import is not configured right now. Standard JSON import is still available.'

  useEffect(() => {
    if (!analyzing) {
      setAnalysisProgress(0)
      return
    }

    setAnalysisProgress(12)
    const interval = window.setInterval(() => {
      setAnalysisProgress((current) => {
        if (current >= 88) return current
        return Math.min(88, current + Math.max(6, Math.round((88 - current) / 3)))
      })
    }, 500)

    return () => window.clearInterval(interval)
  }, [analyzing])

  const resetError = () => setError('')

  const loadExample = () => {
    resetError()
    setImportMode('manual')
    setMethod('paste')
    setFileName('')
    setJsonText(JSON.stringify(buildCurriculumImportExample(), null, 2))
  }

  const handleManualPreview = () => {
    try {
      resetError()
      const result = parseCurriculumImportJson(jsonText)
      setParsed(result.normalized)
      setRawPayload(result.raw)
      setAiWarnings([])
      setEditablePayloadText('')
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

  const handleAiFileChange = (file: File | undefined) => {
    if (!file) return
    setAiFile(file)
    setAiSourceLabel(file.name)
    setAiInputMethod('file')
    resetError()
  }

  const syncDraftEdits = () => {
    try {
      resetError()
      const result = parseCurriculumImportJson(editablePayloadText)
      setParsed(result.normalized)
      setRawPayload(result.raw)
      setEditablePayloadText(JSON.stringify(result.raw, null, 2))
      return result.raw
    } catch (draftError) {
      setError(draftError instanceof Error ? draftError.message : 'Unable to apply the AI draft edits.')
      return null
    }
  }

  const handleAnalyzeAiImport = async () => {
    if (!aiAvailable) {
      setError(aiAvailabilityMessage)
      return
    }

    resetError()
    setAiWarnings([])
    setImportMode('ai')
    setAnalyzing(true)

    try {
      const response =
        aiInputMethod === 'file'
          ? await (() => {
              if (!aiFile) {
                throw new Error('Choose a PDF, DOCX, or TXT file to continue.')
              }
              const payload = new FormData()
              payload.append('file', aiFile)
              return api.createCurriculumAiImportDraft(payload)
            })()
          : await (() => {
              const trimmedUrl = aiUrl.trim()
              if (!trimmedUrl) {
                throw new Error('Paste a curriculum URL to continue.')
              }
              return api.createCurriculumAiImportDraft({ url: trimmedUrl })
            })()

      const draftResult = getAiDraftResult(response)
      const normalized = normalizeCurriculumImport(draftResult.draft)
      const nextPayload = isRecord(draftResult.draft)
        ? draftResult.draft
        : (toCurriculumImportPayload(normalized) as unknown as Record<string, unknown>)

      setAnalysisProgress(100)
      setParsed(normalized)
      setRawPayload(nextPayload)
      setEditablePayloadText(JSON.stringify(nextPayload, null, 2))
      setAiWarnings(draftResult.warnings)
      setAiSourceLabel(draftResult.sourceLabel || (aiInputMethod === 'file' ? aiFile?.name || '' : aiUrl.trim()))
      setStep(STEPS[1])
    } catch (analysisError) {
      setError(analysisError instanceof Error ? analysisError.message : 'Unable to analyze this curriculum document right now.')
    } finally {
      setAnalyzing(false)
    }
  }

  const handleContinueFromPreview = () => {
    if (importMode === 'ai' && !syncDraftEdits()) {
      return
    }
    setStep(STEPS[2])
  }

  const handleImport = async () => {
    const payload =
      importMode === 'ai'
        ? (() => {
            const syncedPayload = syncDraftEdits()
            return syncedPayload
          })()
        : rawPayload

    if (!payload) return

    setSaving(true)
    resetError()
    try {
      const created =
        importMode === 'ai'
          ? await api.confirmCurriculumAiImport({ draft: payload, source_url: aiInputMethod === 'url' ? aiUrl.trim() || null : null })
          : await api.importCurriculum(payload)
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
          <CardDescription>Bring in standard JSON, or upload a document and let AI draft the curriculum structure before you import it.</CardDescription>
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
          <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_300px]">
            <div className="space-y-4">
              <Tabs value={importMode} onValueChange={(value) => setImportMode(value as 'manual' | 'ai')}>
                <TabsList>
                  <TabsTrigger value="manual">Standard JSON</TabsTrigger>
                  <TabsTrigger value="ai" disabled={!aiAvailable}>
                    {aiFeatureEnabled ? 'Upload Document (AI-powered)' : 'Upload Document (coming soon)'}
                  </TabsTrigger>
                </TabsList>

                <TabsContent value="manual" className="space-y-4">
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
                </TabsContent>

                <TabsContent value="ai" className="space-y-4">
                  {aiAvailable ? (
                    <>
                      <Tabs value={aiInputMethod} onValueChange={(value) => setAiInputMethod(value as 'file' | 'url')}>
                        <TabsList>
                          <TabsTrigger value="file">Upload file</TabsTrigger>
                          <TabsTrigger value="url">Paste URL</TabsTrigger>
                        </TabsList>
                        <TabsContent value="file" className="space-y-3">
                          <div
                            className={`rounded-lg border-2 border-dashed p-6 text-center transition ${
                              isDragging ? 'border-primary bg-primary/10' : 'border-muted-foreground/30'
                            }`}
                            onDragOver={(event: DragEvent<HTMLDivElement>) => {
                              event.preventDefault()
                              setIsDragging(true)
                            }}
                            onDragLeave={() => setIsDragging(false)}
                            onDrop={(event: DragEvent<HTMLDivElement>) => {
                              event.preventDefault()
                              setIsDragging(false)
                              handleAiFileChange(event.dataTransfer.files?.[0])
                            }}
                          >
                            <FileText className="mx-auto mb-2 h-7 w-7 text-muted-foreground" />
                            <p className="text-sm font-medium">Drop a PDF, DOCX, or TXT file here</p>
                            <p className="mt-1 text-xs text-muted-foreground">We will analyze the structure, build a draft tree, and let you review it before saving.</p>
                            <div className="mt-3 flex justify-center">
                              <Label htmlFor="curriculum-ai-upload" className="cursor-pointer">
                                <Input
                                  id="curriculum-ai-upload"
                                  type="file"
                                  className="hidden"
                                  accept=".pdf,.docx,.txt,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document,text/plain"
                                  onChange={(event) => handleAiFileChange(event.target.files?.[0])}
                                />
                                <Button type="button" variant="secondary">
                                  <Upload className="h-4 w-4" />
                                  Choose file
                                </Button>
                              </Label>
                            </div>
                          </div>

                          {aiFile ? (
                            <div className="rounded-lg border bg-muted/20 p-3 text-sm">
                              <p className="font-medium">Selected: {aiFile.name}</p>
                              <p className="text-muted-foreground">{(aiFile.size / 1024).toFixed(1)} KB</p>
                            </div>
                          ) : null}
                        </TabsContent>
                        <TabsContent value="url" className="space-y-3">
                          <div className="space-y-2">
                            <Label htmlFor="curriculum-ai-url">Curriculum page or shared document URL</Label>
                            <Input
                              id="curriculum-ai-url"
                              type="url"
                              value={aiUrl}
                              onChange={(event) => setAiUrl(event.target.value)}
                              placeholder="https://example.com/curriculum-outline"
                            />
                          </div>
                          <div className="rounded-lg border border-dashed p-4 text-sm text-muted-foreground">
                            Paste a public curriculum page, syllabus, or outline. AI will draft the structure and let you edit it before import.
                          </div>
                        </TabsContent>
                      </Tabs>

                      {analyzing ? (
                        <Card size="sm">
                          <CardHeader>
                            <CardTitle className="flex items-center gap-2">
                              <Sparkles className="h-4 w-4 text-primary" />
                              Analyzing curriculum structure…
                            </CardTitle>
                            <CardDescription>Uploading, extracting headings, and building an editable draft.</CardDescription>
                          </CardHeader>
                          <CardContent className="space-y-4">
                            <Progress value={analysisProgress} />
                            <AnalysisSkeleton />
                          </CardContent>
                        </Card>
                      ) : null}
                    </>
                  ) : (
                    <div className="rounded-lg border border-dashed p-6 text-sm text-muted-foreground">{aiAvailabilityMessage}</div>
                  )}
                </TabsContent>
              </Tabs>
            </div>

            <Card size="sm">
              <CardHeader>
                <CardTitle>{importMode === 'manual' ? 'Standard format' : 'AI import guidance'}</CardTitle>
                <CardDescription>
                  {importMode === 'manual'
                    ? 'These are the required top-level fields we expect in the import contract today.'
                    : 'AI import accepts document files or URLs, then returns a draft you can refine before saving.'}
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-3 text-sm">
                {importMode === 'manual' ? (
                  <>
                    <div className="flex flex-wrap gap-2">
                      {requiredFields.map((field) => (
                        <Badge key={field} variant="outline">
                          {field}
                        </Badge>
                      ))}
                    </div>
                    <p className="text-muted-foreground">Each subject contains units, and each unit contains lessons with optional objectives, resources, and time estimates.</p>
                  </>
                ) : (
                  <>
                    <div className="rounded-lg border bg-muted/20 p-3">
                      <p className="font-medium">AI import status</p>
                      <p className="mt-1 text-muted-foreground">{aiAvailable ? 'Ready to analyze curriculum documents.' : aiAvailabilityMessage}</p>
                    </div>
                    <p className="text-muted-foreground">Use the draft editor in the next step to rename sections, adjust grade levels, and correct anything AI inferred incorrectly.</p>
                    <div className="flex flex-wrap gap-2">
                      <Badge variant="outline">PDF</Badge>
                      <Badge variant="outline">DOCX</Badge>
                      <Badge variant="outline">TXT</Badge>
                      <Badge variant="outline">URL</Badge>
                    </div>
                  </>
                )}
              </CardContent>
            </Card>
          </div>
        ) : null}

        {step === STEPS[1] && parsed ? (
          <div className="space-y-4">
            <StatsGrid curriculum={parsed} />
            {importMode === 'ai' ? (
              <div className="grid gap-4 xl:grid-cols-[340px_minmax(0,1fr)]">
                <Card size="sm">
                  <CardHeader>
                    <CardTitle>Refine the AI draft</CardTitle>
                    <CardDescription>{aiSourceLabel ? `Draft source: ${aiSourceLabel}` : 'Adjust the draft JSON, then refresh the preview.'}</CardDescription>
                  </CardHeader>
                  <CardContent className="space-y-3">
                    {aiWarnings.length ? (
                      <div className="rounded-lg border border-amber-400/40 bg-amber-500/10 p-3 text-sm text-amber-900 dark:text-amber-100">
                        <p className="font-medium">Review recommended</p>
                        <ul className="mt-2 list-disc space-y-1 pl-5">
                          {aiWarnings.map((warning) => (
                            <li key={warning}>{warning}</li>
                          ))}
                        </ul>
                      </div>
                    ) : null}
                    <Textarea
                      className="min-h-[420px] font-mono text-xs"
                      value={editablePayloadText}
                      onChange={(event) => setEditablePayloadText(event.target.value)}
                    />
                    <Button type="button" variant="outline" onClick={syncDraftEdits}>
                      Refresh preview
                    </Button>
                  </CardContent>
                </Card>
                <Card size="sm">
                  <CardHeader>
                    <CardTitle>{parsed.name}</CardTitle>
                    <CardDescription>Preview the AI-generated curriculum tree before confirming the import.</CardDescription>
                  </CardHeader>
                  <CardContent>
                    <CurriculumImportTree curriculum={parsed} />
                  </CardContent>
                </Card>
              </div>
            ) : (
              <Card size="sm">
                <CardHeader>
                  <CardTitle>{parsed.name}</CardTitle>
                  <CardDescription>Preview the curriculum tree before you confirm the import.</CardDescription>
                </CardHeader>
                <CardContent>
                  <CurriculumImportTree curriculum={parsed} />
                </CardContent>
              </Card>
            )}
          </div>
        ) : null}

        {step === STEPS[2] && parsed ? (
          <div className="space-y-4">
            <StatsGrid curriculum={parsed} />
            <Card size="sm">
              <CardHeader>
                <CardTitle>{importMode === 'ai' ? 'Review the AI draft' : 'Review and confirm'}</CardTitle>
                <CardDescription>
                  {importMode === 'ai'
                    ? 'We will save the edited AI draft exactly as shown here.'
                    : 'We will import the curriculum exactly as previewed here.'}
                </CardDescription>
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
                  {importMode === 'ai' && aiSourceLabel ? <Badge variant="secondary">Source: {aiSourceLabel}</Badge> : null}
                </div>
                {importMode === 'ai' ? <CurriculumImportTree curriculum={parsed} expandAll={false} /> : null}
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
                <Button onClick={handleContinueFromPreview}>Continue</Button>
              </>
            ) : null}
            {step === STEPS[2] ? (
              <>
                <Button variant="outline" onClick={() => setStep(STEPS[1])}>
                  Back
                </Button>
                <Button disabled={saving} onClick={() => void handleImport()}>
                  {saving ? 'Importing…' : importMode === 'ai' ? 'Looks good — Import' : 'Import curriculum'}
                </Button>
              </>
            ) : null}
            {step === STEPS[0] ? (
              <Button disabled={analyzing || (importMode === 'ai' && !aiAvailable)} onClick={() => void (importMode === 'manual' ? handleManualPreview() : handleAnalyzeAiImport())}>
                {importMode === 'manual' ? (
                  'Validate & preview'
                ) : analyzing ? (
                  'Analyzing…'
                ) : (
                  <>
                    <WandSparkles className="h-4 w-4" />
                    Analyze curriculum
                  </>
                )}
              </Button>
            ) : null}
          </div>
        </div>
      </CardContent>
    </Card>
  )
}
