import { type ChangeEvent, type DragEvent, useEffect, useMemo, useRef, useState } from 'react'
import { CheckCircle2, FileJson, FileText, Sparkles, Upload, WandSparkles } from 'lucide-react'
import { Link } from 'react-router-dom'
import { useAuth } from '@/context/AuthContext'
import { useCapabilities } from '@/context/CapabilitiesContext'
import { ApiError, api } from '@/lib/api'
import { CurriculumSessionRunner, duplicatesAcknowledged } from '@/lib/curriculumImportSession'
import type { CurriculumAiImportSession, CurriculumDuplicateMatch, CurriculumImportDetail, CurriculumImportSchema } from '@/types/api'
import {
  buildCurriculumImportExample,
  formatEstimatedHours,
  normalizeCurriculumImport,
  parseCurriculumImportJson,
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
  const { onlineCurriculumEnabled } = useCapabilities()
  const [step, setStep] = useState<(typeof STEPS)[number]>(STEPS[0])
  const [importMode, setImportMode] = useState<'manual' | 'ai'>('manual')
  const [method, setMethod] = useState<'paste' | 'file' | 'url'>('paste')
  const [jsonText, setJsonText] = useState('')
  const [fileName, setFileName] = useState('')
  const [error, setError] = useState('')
  const [saving, setSaving] = useState(false)
  const [activating, setActivating] = useState(false)
  const [parsed, setParsed] = useState<NormalizedCurriculumImport | null>(null)
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
  const aiFileInputRef = useRef<HTMLInputElement | null>(null)
  const [session, setSession] = useState<CurriculumAiImportSession | null>(null)
  const [matches, setMatches] = useState<CurriculumDuplicateMatch[]>([])
  const [acknowledgedIds, setAcknowledgedIds] = useState<number[]>([])
  const [validatedText, setValidatedText] = useState<string | null>(null)
  const [checkingDuplicates, setCheckingDuplicates] = useState(false)
  const [duplicateError, setDuplicateError] = useState('')
  const [preflightAttempt, setPreflightAttempt] = useState(0)
  const [runner] = useState(() => new CurriculumSessionRunner(api.deleteCurriculumAiImportSession))
  const active = useRef(true)
  const attempt = useRef(0)
  const editorText = useRef(editablePayloadText)
  useEffect(() => { editorText.current = editablePayloadText }, [editablePayloadText])

  useEffect(() => {
    active.current = true
    const invalidate = () => { attempt.current++ }
    return () => {
      active.current = false
      invalidate()
      void runner.cancel().catch(() => { /* The server expiry also releases abandoned sessions. */ })
    }
  }, [runner])

  useEffect(() => {
    if ((step !== STEPS[1] && step !== STEPS[2]) || !editablePayloadText) return
    let current = true
    setValidatedText(null)
    setAcknowledgedIds([])
    setMatches([])
    setCheckingDuplicates(true)
    setDuplicateError('')
    const timer = window.setTimeout(async () => {
      try {
        const result = parseCurriculumImportJson(editablePayloadText)
        const response = await api.checkCurriculumImportDuplicates(result.raw)
        if (!current || editorText.current !== editablePayloadText) return
        setMatches(response.matches)
        setValidatedText(editablePayloadText)
      } catch (checkError) {
        if (current && editorText.current === editablePayloadText) {
          setDuplicateError(checkError instanceof Error ? checkError.message : 'Unable to check for duplicates. Retry before importing.')
        }
      } finally {
        if (current) setCheckingDuplicates(false)
      }
    }, 350)
    return () => { current = false; window.clearTimeout(timer) }
  }, [editablePayloadText, step, preflightAttempt])

  useEffect(() => {
    if (!session || session.status !== 'ready') return
    const timer = window.setTimeout(() => {
      setSession((current) => current ? { ...current, status: 'expired' } : null)
      setError('This AI draft session expired. Copy your edits before starting a new analysis.')
    }, Math.min(2147483647, Math.max(0, Date.parse(session.expires_at) - Date.now())))
    return () => window.clearTimeout(timer)
  }, [session])

  const closeWizard = async () => {
    if (saving || activating) return
    attempt.current++
    setAnalyzing(false)
    try {
      await runner.cancel()
      if (active.current) onCancel()
    } catch {
      if (active.current) setError('Unable to cancel the server session. Try Close again; it will also expire automatically.')
    }
  }

  const requiredFields = useMemo(() => {
    const required = schema?.required
    if (Array.isArray(required)) {
      return required.filter((value): value is string => typeof value === 'string')
    }
    return ['name', 'grade_levels', 'subjects']
  }, [schema])

  const aiFeatureEnabled = isFeatureEnabled('curriculum_ai_import')
  const aiAvailable = aiFeatureEnabled
  const aiAvailabilityMessage = 'AI import is coming soon for this family.'

  useEffect(() => {
    if (!onlineCurriculumEnabled) {
      setAiInputMethod('file')
    }
  }, [onlineCurriculumEnabled])

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
    attempt.current++
    void runner.cancel().catch(() => { if (active.current) setError('Unable to cancel the previous analysis. It will expire automatically.') })
    setAnalyzing(false)
    setSession(null)
    resetError()
    setStep(STEPS[0])
    setParsed(null)
    setEditablePayloadText('')
    setValidatedText(null)
    setAcknowledgedIds([])
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
      setAiWarnings([])
      setEditablePayloadText(JSON.stringify(result.raw, null, 2))
      setAiSourceLabel('')
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
    const text = await file.text()
    if (!active.current) return
    setJsonText(text)
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
      if (importMode === 'manual') setJsonText(editablePayloadText)
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
    const requestAttempt = ++attempt.current
    setSession(null)

    try {
      const create = () =>
        aiInputMethod === 'file'
          ? (() => {
              if (!aiFile) {
                throw new Error('Choose a PDF, DOCX, or TXT file to continue.')
              }
              const payload = new FormData()
              payload.append('file', aiFile)
              return api.createCurriculumAiImportSession(payload)
            })()
          : (() => {
              const trimmedUrl = aiUrl.trim()
              if (!trimmedUrl) {
                throw new Error('Paste a curriculum URL to continue.')
              }
              return api.createCurriculumAiImportSession({ url: trimmedUrl })
            })()

      const response = await runner.run(create, api.getCurriculumAiImportSession, (next) => {
        if (active.current && attempt.current === requestAttempt) setSession(next)
      })
      if (!response || !active.current || attempt.current !== requestAttempt) return
      if (response.status === 'expired') throw new Error('This analysis session expired. Start a new analysis to retry.')
      if (response.status === 'failed') throw new Error('Analysis failed. Check that the document contains readable text and try a new analysis. If it fails again, ask an administrator to check the AI provider.')
      if (response.status !== 'ready' || !response.draft) throw new Error('No editable draft was returned. Start a new analysis.')
      const normalized = normalizeCurriculumImport(response.draft)
      const nextPayload = response.draft as Record<string, unknown>

      setAnalysisProgress(100)
      setParsed(normalized)
      setEditablePayloadText(JSON.stringify(nextPayload, null, 2))
      setAiWarnings(response.warnings)
      setAiSourceLabel(response.source_name || (aiInputMethod === 'file' ? aiFile?.name || '' : aiUrl.trim()))
      setStep(STEPS[1])
    } catch (analysisError) {
      if (!active.current || attempt.current !== requestAttempt) return
      if (analysisError instanceof ApiError) {
        setError(analysisError.status === 503
          ? 'AI curriculum import is unavailable. Ask an administrator to check the AI provider, or use Standard JSON.'
          : analysisError.status === 404 || analysisError.status === 410
            ? 'This analysis session is no longer available. Start a new analysis.'
            : 'Analysis could not finish. Check the file or URL and start a new analysis. If this continues, ask an administrator to check the AI provider.')
      } else {
        setError(analysisError instanceof TypeError
          ? 'The connection was interrupted. Start a new analysis when the server is available.'
          : analysisError instanceof Error ? analysisError.message : 'Unable to analyze this curriculum document right now.')
      }
    } finally {
      if (active.current && attempt.current === requestAttempt) setAnalyzing(false)
    }
  }

  const handleContinueFromPreview = () => {
    if (!syncDraftEdits()) {
      return
    }
    setStep(STEPS[2])
  }

  const handleImport = async () => {
    if (validatedText !== editablePayloadText || checkingDuplicates || !duplicatesAcknowledged(matches, acknowledgedIds)) return
    if (importMode === 'ai' && (!session || session.status !== 'ready' || Date.parse(session.expires_at) <= Date.now())) return
    const payload = syncDraftEdits()

    if (!payload) return

    setSaving(true)
    resetError()
    try {
      const created =
        importMode === 'ai'
          ? await api.confirmCurriculumAiImportSession(session!.id, { draft: payload, client_revision: session!.revision, acknowledged_duplicate_ids: acknowledgedIds })
          : await api.confirmCurriculumImport({ draft: payload, acknowledged_duplicate_ids: acknowledgedIds })
      if (importMode === 'ai') runner.confirmed()
      if (!active.current) return
      setCreatedCurriculum(created)
      setStep(STEPS[3])
      onImported()
    } catch (saveError) {
      if (!active.current) return
      if (saveError instanceof ApiError && saveError.status === 409) {
        setStep(STEPS[2])
        setAcknowledgedIds([])
        if (saveError.code === 'curriculum_import_duplicate_conflict') {
          setMatches(saveError.matches)
          setValidatedText(editablePayloadText)
          setError('The duplicate matches changed. Review and acknowledge the current matches before importing separately.')
          return
        }
        setValidatedText(null)
        setError(`${saveError.message} Rename or edit the draft and check again; duplicate acknowledgement cannot override this conflict.`)
        return
      }
      setError(saveError instanceof Error ? saveError.message : 'Unable to import curriculum right now.')
    } finally {
      if (active.current) setSaving(false)
    }
  }

  const handleActivateNow = async () => {
    if (!createdCurriculum) return
    setActivating(true)
    resetError()
    try {
      const activation = await api.activateImportedCurriculum(createdCurriculum.id)
      if (!active.current) return
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
      if (!active.current) return
      setError(activationError instanceof Error ? activationError.message : 'Unable to activate curriculum right now.')
    } finally {
      if (active.current) setActivating(false)
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
          <Button size="sm" variant="outline" disabled={saving || activating} onClick={loadExample}>
            <FileJson className="h-4 w-4" />
            Load example
          </Button>
          <Button size="sm" variant="ghost" disabled={saving || activating} onClick={() => void closeWizard()}>
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
              <Tabs value={importMode} onValueChange={(value) => { if (!analyzing) setImportMode(value as 'manual' | 'ai') }}>
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
                          {onlineCurriculumEnabled ? <TabsTrigger value="url">Paste URL</TabsTrigger> : null}
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
                              <input
                                ref={aiFileInputRef}
                                id="curriculum-ai-upload"
                                type="file"
                                className="sr-only"
                                accept=".pdf,.docx,.txt,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document,text/plain"
                                onChange={(event) => handleAiFileChange(event.target.files?.[0])}
                              />
                              <Button
                                type="button"
                                variant="secondary"
                                onClick={() => aiFileInputRef.current?.click()}
                              >
                                <Upload className="h-4 w-4" />
                                Choose file
                              </Button>
                            </div>
                          </div>

                          {aiFile ? (
                            <div className="rounded-lg border bg-muted/20 p-3 text-sm">
                              <p className="font-medium">Selected: {aiFile.name}</p>
                              <p className="text-muted-foreground">{(aiFile.size / 1024).toFixed(1)} KB</p>
                            </div>
                          ) : null}
                        </TabsContent>
                        {onlineCurriculumEnabled ? (
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
                        ) : (
                          <div className="rounded-lg border border-dashed p-4 text-sm text-muted-foreground">
                            Online curriculum downloads are disabled. Upload a local document to create an AI-assisted draft.
                          </div>
                        )}
                      </Tabs>

                      {analyzing ? (
                        <Card size="sm">
                          <CardHeader>
                            <CardTitle className="flex items-center gap-2">
                              <Sparkles className="h-4 w-4 text-primary" />
                              Analyzing curriculum structure…
                            </CardTitle>
                            <CardDescription role="status">Processing in the background. Large documents may take several minutes. You can cancel without importing anything.</CardDescription>
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
                      <p role="status" className="mt-1 text-muted-foreground">{session ? `Session: ${session.status}` : aiAvailable ? 'Ready to analyze curriculum documents.' : aiAvailabilityMessage}</p>
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
            {(
              <div className="grid gap-4 xl:grid-cols-[340px_minmax(0,1fr)]">
                <Card size="sm">
                  <CardHeader>
                    <CardTitle>Edit the curriculum draft</CardTitle>
                    <CardDescription>{aiSourceLabel ? `Draft source: ${aiSourceLabel}` : 'Adjust the draft JSON, including metadata.edition, then refresh the preview.'}</CardDescription>
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
                      aria-label="Curriculum draft JSON"
                      onChange={(event) => { editorText.current = event.target.value; setValidatedText(null); setAcknowledgedIds([]); setMatches([]); setEditablePayloadText(event.target.value) }}
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
                  {parsed.metadata.edition ? <Badge variant="outline">Edition: {parsed.metadata.edition}</Badge> : null}
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
              <Button variant="ghost" onClick={() => void closeWizard()}>
                Done
              </Button>
            </div>
          </div>
        ) : null}

        {(step === STEPS[1] || step === STEPS[2]) ? (
          <Card size="sm">
            <CardHeader><CardTitle>Duplicate curriculum check</CardTitle></CardHeader>
            <CardContent className="space-y-3 text-sm">
              {checkingDuplicates ? <p role="status">Checking the current draft…</p> : null}
              {duplicateError ? <p role="alert">{duplicateError}</p> : null}
              {!checkingDuplicates && validatedText !== editablePayloadText ? <Button variant="outline" onClick={() => setPreflightAttempt((value) => value + 1)}>Check again</Button> : null}
              {validatedText === editablePayloadText && !matches.length ? <p>No matching curriculum content found.</p> : null}
              {matches.map((match) => (
                <div key={match.id} className="space-y-2 rounded-lg border p-3">
                  <Link className="font-medium underline" target="_blank" rel="noreferrer" to={`/curriculum/${match.id}`}>{match.name}</Link>
                  <p>Grades: {match.grade_levels.join(', ') || 'Not specified'} · Edition: {match.edition || 'Not specified'}</p>
                  <p>{match.reason}</p>
                  <p>Subjects: {match.matched_subjects.join(', ') || 'None'}; Units: {match.matched_units.join(', ') || 'None'}; Lessons: {match.matched_lessons.join(', ') || 'None'}</p>
                  <label className="flex items-start gap-2">
                    <input type="checkbox" disabled={saving || validatedText !== editablePayloadText} checked={acknowledgedIds.includes(match.id)}
                      onChange={(event) => setAcknowledgedIds((ids) => event.target.checked ? [...ids, match.id] : ids.filter((id) => id !== match.id))} />
                    Import as a separate curriculum despite this match. Nothing will be merged or removed.
                  </label>
                </div>
              ))}
              {importMode === 'ai' && session?.status === 'expired' ? <p role="alert">Session expired. Copy your edits before starting a new analysis.</p> : null}
            </CardContent>
          </Card>
        ) : null}
        <div className="flex flex-wrap justify-between gap-2 border-t pt-4">
          <Button variant="ghost" disabled={saving || activating} onClick={() => void closeWizard()}>
            Cancel
          </Button>

          <div className="flex gap-2">
            {step === STEPS[1] ? (
              <>
                <Button variant="outline" onClick={() => { if (importMode === 'manual') setJsonText(editablePayloadText); setStep(STEPS[0]) }}>
                  Back
                </Button>
                <Button onClick={handleContinueFromPreview}>Continue</Button>
              </>
            ) : null}
            {step === STEPS[2] ? (
              <>
                <Button variant="outline" disabled={saving} onClick={() => setStep(STEPS[1])}>
                  Back
                </Button>
                <Button disabled={saving || checkingDuplicates || validatedText !== editablePayloadText || !duplicatesAcknowledged(matches, acknowledgedIds) || (importMode === 'ai' && session?.status !== 'ready')} onClick={() => void handleImport()}>
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
                    {session?.status === 'failed' || session?.status === 'expired' ? 'Start a new analysis' : 'Analyze curriculum'}
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
