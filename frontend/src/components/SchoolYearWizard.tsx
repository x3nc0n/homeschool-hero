import { useCallback, useEffect, useMemo, useState } from 'react'
import { ArrowLeft, ArrowRight, CalendarDays, CheckCircle2, Loader2, Plus, Sparkles, X } from 'lucide-react'
import { EmptyState } from '@/components/common/EmptyState'
import { ErrorState } from '@/components/common/ErrorState'
import { LoadingState } from '@/components/common/LoadingState'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Progress } from '@/components/ui/progress'
import { api } from '@/lib/api'
import { cn } from '@/lib/utils'
import type {
  SchoolYear,
  SchoolYearWizardCreatePayload,
  SchoolYearWizardCustomBreak,
  SchoolYearWizardHolidayPreset,
  SchoolYearWizardTemplate,
  SchoolYearWizardTermStructure,
} from '@/types/api'

type SchoolYearWizardProps = {
  open: boolean
  existingSchoolYears: SchoolYear[]
  onOpenChange: (open: boolean) => void
  onComplete: (schoolYearId: number) => Promise<void> | void
}

type WizardSchoolYearForm = {
  name: string
  start_date: string
  end_date: string
  is_active: boolean
}

type LocalCustomBreak = SchoolYearWizardCustomBreak & {
  id: string
}

type PreviewTerm = {
  name: string
  start_date: string
  end_date: string
}

const DAY_IN_MS = 24 * 60 * 60 * 1000
const stepLabels = ['Choose Template', 'Term Structure', 'Holidays & Breaks', 'Review & Confirm'] as const
const termStructureOptions: Array<{ key: SchoolYearWizardTermStructure; label: string; description: string }> = [
  { key: 'semesters', label: 'Semesters', description: 'Two balanced halves for fall and spring reporting.' },
  { key: 'quarters', label: 'Quarters', description: 'Four progress checkpoints spread across the year.' },
  { key: 'trimesters', label: 'Trimesters', description: 'Three larger terms with fewer transitions.' },
  { key: 'custom', label: 'Custom', description: 'Create the year now and fine-tune terms afterward.' },
]

function parseMonthDay(value: string) {
  const [month, day] = value.split('-').map(Number)
  return { month, day }
}

function createLocalDate(value: string) {
  const [year, month, day] = value.split('-').map(Number)
  return new Date(year, month - 1, day)
}

function toDateString(date: Date) {
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`
}

function addDays(value: string, days: number) {
  const date = createLocalDate(value)
  date.setDate(date.getDate() + days)
  return toDateString(date)
}

function differenceInDays(startDate: string, endDate: string) {
  return Math.round((createLocalDate(endDate).getTime() - createLocalDate(startDate).getTime()) / DAY_IN_MS)
}

function formatDateLabel(value: string) {
  return createLocalDate(value).toLocaleDateString(undefined, {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  })
}

function formatDateRange(startDate: string, endDate: string) {
  return `${formatDateLabel(startDate)} – ${formatDateLabel(endDate)}`
}

function getSuggestedSchoolYearName(startDate: string, endDate: string) {
  if (!startDate || !endDate) return ''

  const startYear = Number(startDate.slice(0, 4))
  const endYear = Number(endDate.slice(0, 4))
  return startYear === endYear ? `${startYear} School Year` : `${startYear}-${endYear} School Year`
}

function getDefaultAcademicRange(referenceDate = new Date()) {
  const year = referenceDate.getFullYear()
  const month = referenceDate.getMonth() + 1
  const startYear = month >= 5 ? year : year - 1

  return {
    start_date: `${startYear}-08-15`,
    end_date: `${startYear + 1}-05-30`,
  }
}

function resolveTemplateRange(template: SchoolYearWizardTemplate, referenceDate = new Date()) {
  const { month: startMonth, day: startDay } = parseMonthDay(template.suggested_start_date)
  const { month: endMonth, day: endDay } = parseMonthDay(template.suggested_end_date)
  const currentYear = referenceDate.getFullYear()
  const currentMonth = referenceDate.getMonth() + 1
  let startYear = currentYear

  if (currentMonth < 5 && startMonth > currentMonth) {
    startYear -= 1
  }

  const crossesYear = endMonth < startMonth || (endMonth === startMonth && endDay < startDay)
  const endYear = crossesYear ? startYear + 1 : startYear

  return {
    start_date: `${startYear}-${String(startMonth).padStart(2, '0')}-${String(startDay).padStart(2, '0')}`,
    end_date: `${endYear}-${String(endMonth).padStart(2, '0')}-${String(endDay).padStart(2, '0')}`,
  }
}

function getInitialState() {
  const range = getDefaultAcademicRange()
  return {
    form: {
      name: getSuggestedSchoolYearName(range.start_date, range.end_date),
      start_date: range.start_date,
      end_date: range.end_date,
      is_active: true,
    } satisfies WizardSchoolYearForm,
    termStructure: 'semesters' as SchoolYearWizardTermStructure,
  }
}

function getTermNames(termStructure: SchoolYearWizardTermStructure) {
  switch (termStructure) {
    case 'semesters':
      return ['Fall Semester', 'Spring Semester']
    case 'quarters':
      return ['Q1', 'Q2', 'Q3', 'Q4']
    case 'trimesters':
      return ['Trimester 1', 'Trimester 2', 'Trimester 3']
    case 'custom':
      return ['Custom Term']
  }
}

function getTermCount(termStructure: SchoolYearWizardTermStructure) {
  switch (termStructure) {
    case 'semesters':
      return 2
    case 'quarters':
      return 4
    case 'trimesters':
      return 3
    case 'custom':
      return 1
  }
}

function generatePreviewTerms(startDate: string, endDate: string, termStructure: SchoolYearWizardTermStructure) {
  if (!startDate || !endDate || startDate > endDate) {
    return [] as PreviewTerm[]
  }

  const count = getTermCount(termStructure)
  const totalDays = differenceInDays(startDate, endDate) + 1
  const baseDays = Math.floor(totalDays / count)
  const remainder = totalDays % count
  const names = getTermNames(termStructure)
  let currentStart = startDate

  return Array.from({ length: count }, (_, index) => {
    const segmentDays = baseDays + (index < remainder ? 1 : 0)
    const currentEnd = addDays(currentStart, segmentDays - 1)
    const term = {
      name: names[index] ?? `Term ${index + 1}`,
      start_date: currentStart,
      end_date: currentEnd,
    }

    currentStart = addDays(currentEnd, 1)
    return term
  })
}

function isRangeInvalid(startDate: string, endDate: string) {
  return !startDate || !endDate || startDate > endDate
}

function getBasicsError(form: WizardSchoolYearForm, existingSchoolYears: SchoolYear[]) {
  const trimmedName = form.name.trim()
  if (!trimmedName) return 'School year name is required.'
  if (!form.start_date || !form.end_date) return 'Choose both a start and end date.'
  if (isRangeInvalid(form.start_date, form.end_date)) return 'Start date must be before end date.'

  if (existingSchoolYears.some((schoolYear) => schoolYear.name.trim().toLowerCase() === trimmedName.toLowerCase())) {
    return 'A school year with this name already exists.'
  }

  return ''
}

function getCustomBreaksError(form: WizardSchoolYearForm, customBreaks: LocalCustomBreak[]) {
  for (const customBreak of customBreaks) {
    if (!customBreak.name.trim()) return 'Each custom break needs a name.'
    if (!customBreak.start_date || !customBreak.end_date) return 'Each custom break needs a start and end date.'
    if (customBreak.start_date > customBreak.end_date) return `${customBreak.name || 'Custom break'} has an invalid date range.`
    if (customBreak.start_date < form.start_date || customBreak.end_date > form.end_date) {
      return `Custom breaks must stay within ${formatDateRange(form.start_date, form.end_date)}.`
    }
  }

  return ''
}

function getHolidayTimingLabel(preset: SchoolYearWizardHolidayPreset) {
  if (preset.date_range) {
    return formatDateRange(preset.date_range.start_date, preset.date_range.end_date)
  }

  if (preset.date) {
    return formatDateLabel(preset.date)
  }

  if (preset.events.length === 1) {
    return formatDateLabel(preset.events[0].date)
  }

  if (preset.events.length > 1) {
    const preview = preset.events.slice(0, 3).map((event) => formatDateLabel(event.date))
    const remaining = preset.events.length - preview.length
    return remaining > 0 ? `${preview.join(', ')} + ${remaining} more` : preview.join(', ')
  }

  return 'Dates generated from the selected school year'
}

function getHolidayDayCount(preset: SchoolYearWizardHolidayPreset) {
  if (preset.date_range) {
    return differenceInDays(preset.date_range.start_date, preset.date_range.end_date) + 1
  }

  if (preset.events.length) {
    return preset.events.length
  }

  return preset.date ? 1 : 0
}

function getHolidayTypeMeta(type: SchoolYearWizardHolidayPreset['type']) {
  switch (type) {
    case 'federal':
      return {
        title: 'Federal holidays',
        description: 'National holidays calculated for the selected school year.',
      }
    case 'religious':
      return {
        title: 'Religious holidays',
        description: 'Computed observances like Easter-based holidays.',
      }
    case 'school_break':
      return {
        title: 'School breaks',
        description: 'Common multi-day breaks you can add with one click.',
      }
  }
}

function createCustomBreak() {
  return {
    id: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
    name: '',
    start_date: '',
    end_date: '',
  }
}

function HolidayPresetSection({
  presets,
  selectedHolidayKeys,
  onToggle,
}: {
  presets: SchoolYearWizardHolidayPreset[]
  selectedHolidayKeys: string[]
  onToggle: (key: string) => void
}) {
  if (!presets.length) {
    return null
  }

  const meta = getHolidayTypeMeta(presets[0].type)

  return (
    <Card>
      <CardHeader>
        <CardTitle>{meta.title}</CardTitle>
        <CardDescription>{meta.description}</CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        {presets.map((preset) => {
          const checked = selectedHolidayKeys.includes(preset.key)
          const dayCount = getHolidayDayCount(preset)

          return (
            <label
              key={preset.key}
              className={cn(
                'flex cursor-pointer items-start gap-3 rounded-xl border p-4 transition-colors hover:bg-muted/40',
                checked && 'border-primary bg-primary/5',
              )}
            >
              <input
                type="checkbox"
                className="mt-1 h-4 w-4"
                checked={checked}
                onChange={() => onToggle(preset.key)}
              />
              <div className="min-w-0 flex-1 space-y-1">
                <div className="flex flex-wrap items-center gap-2">
                  <p className="font-medium">{preset.name}</p>
                  <Badge variant="secondary">{dayCount} day{dayCount === 1 ? '' : 's'}</Badge>
                </div>
                <p className="text-sm text-muted-foreground">{getHolidayTimingLabel(preset)}</p>
              </div>
            </label>
          )
        })}
      </CardContent>
    </Card>
  )
}

export function SchoolYearWizard({ open, existingSchoolYears, onOpenChange, onComplete }: SchoolYearWizardProps) {
  const initialState = useMemo(() => getInitialState(), [])
  const [step, setStep] = useState(0)
  const [schoolYearForm, setSchoolYearForm] = useState<WizardSchoolYearForm>(initialState.form)
  const [nameManuallyEdited, setNameManuallyEdited] = useState(false)
  const [selectedTemplateKey, setSelectedTemplateKey] = useState('')
  const [termStructure, setTermStructure] = useState<SchoolYearWizardTermStructure>(initialState.termStructure)
  const [templates, setTemplates] = useState<SchoolYearWizardTemplate[]>([])
  const [templatesLoading, setTemplatesLoading] = useState(false)
  const [templatesError, setTemplatesError] = useState('')
  const [holidayPresets, setHolidayPresets] = useState<SchoolYearWizardHolidayPreset[]>([])
  const [holidaysLoading, setHolidaysLoading] = useState(false)
  const [holidaysError, setHolidaysError] = useState('')
  const [selectedHolidayKeys, setSelectedHolidayKeys] = useState<string[]>([])
  const [holidayDefaultsApplied, setHolidayDefaultsApplied] = useState(false)
  const [customBreaks, setCustomBreaks] = useState<LocalCustomBreak[]>([])
  const [stepError, setStepError] = useState('')
  const [submissionError, setSubmissionError] = useState('')
  const [submissionStage, setSubmissionStage] = useState('')
  const [submitting, setSubmitting] = useState(false)

  const resetWizard = useCallback(() => {
    const nextState = getInitialState()
    setStep(0)
    setSchoolYearForm(nextState.form)
    setNameManuallyEdited(false)
    setSelectedTemplateKey('')
    setTermStructure(nextState.termStructure)
    setTemplatesError('')
    setHolidayPresets([])
    setHolidaysError('')
    setSelectedHolidayKeys([])
    setHolidayDefaultsApplied(false)
    setCustomBreaks([])
    setStepError('')
    setSubmissionError('')
    setSubmissionStage('')
    setSubmitting(false)
  }, [])

  useEffect(() => {
    if (open) {
      resetWizard()
    }
  }, [open, resetWizard])

  useEffect(() => {
    if (!open) return

    const previousOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'

    return () => {
      document.body.style.overflow = previousOverflow
    }
  }, [open])

  useEffect(() => {
    if (!open || submitting) return

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        onOpenChange(false)
      }
    }

    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [onOpenChange, open, submitting])

  const loadTemplates = useCallback(async () => {
    setTemplatesLoading(true)
    setTemplatesError('')

    try {
      const response = await api.listSchoolYearWizardTemplates()
      setTemplates(response)
    } catch (error) {
      setTemplatesError(error instanceof Error ? error.message : 'Unable to load school year templates.')
    } finally {
      setTemplatesLoading(false)
    }
  }, [])

  useEffect(() => {
    if (!open) return
    void loadTemplates()
  }, [loadTemplates, open])

  const holidayYear = useMemo(() => {
    if (!schoolYearForm.start_date) return new Date().getFullYear()
    return Number(schoolYearForm.start_date.slice(0, 4))
  }, [schoolYearForm.start_date])

  const loadHolidayPresets = useCallback(async () => {
    setHolidaysLoading(true)
    setHolidaysError('')

    try {
      const response = await api.listSchoolYearWizardHolidays(holidayYear)
      setHolidayPresets(response)
      setSelectedHolidayKeys((current) => {
        if (!holidayDefaultsApplied) {
          return response.filter((preset) => preset.key === 'us_federal').map((preset) => preset.key)
        }

        return current.filter((key) => response.some((preset) => preset.key === key))
      })
      if (!holidayDefaultsApplied) {
        setHolidayDefaultsApplied(true)
      }
    } catch (error) {
      setHolidayPresets([])
      setHolidaysError(error instanceof Error ? error.message : 'Unable to load holiday presets.')
    } finally {
      setHolidaysLoading(false)
    }
  }, [holidayDefaultsApplied, holidayYear])

  useEffect(() => {
    if (!open) return
    void loadHolidayPresets()
  }, [loadHolidayPresets, open])

  const computedTerms = useMemo(
    () => generatePreviewTerms(schoolYearForm.start_date, schoolYearForm.end_date, termStructure),
    [schoolYearForm.end_date, schoolYearForm.start_date, termStructure],
  )

  const suggestedName = useMemo(
    () => getSuggestedSchoolYearName(schoolYearForm.start_date, schoolYearForm.end_date),
    [schoolYearForm.end_date, schoolYearForm.start_date],
  )

  const holidayGroups = useMemo(() => {
    return {
      federal: holidayPresets.filter((preset) => preset.type === 'federal'),
      religious: holidayPresets.filter((preset) => preset.type === 'religious'),
      school_break: holidayPresets.filter((preset) => preset.type === 'school_break'),
    }
  }, [holidayPresets])

  const selectedHolidayPresets = useMemo(
    () => holidayPresets.filter((preset) => selectedHolidayKeys.includes(preset.key)),
    [holidayPresets, selectedHolidayKeys],
  )

  const selectedHolidayDayCount = useMemo(
    () => selectedHolidayPresets.reduce((total, preset) => total + getHolidayDayCount(preset), 0),
    [selectedHolidayPresets],
  )

  const syncSchoolYearDates = useCallback(
    (updates: Partial<Pick<WizardSchoolYearForm, 'start_date' | 'end_date'>>, options?: { keepTemplate?: boolean }) => {
      setSchoolYearForm((current) => {
        const nextForm = { ...current, ...updates }
        if (!nameManuallyEdited) {
          nextForm.name = getSuggestedSchoolYearName(nextForm.start_date, nextForm.end_date)
        }
        return nextForm
      })

      if (!options?.keepTemplate) {
        setSelectedTemplateKey('')
      }
    },
    [nameManuallyEdited],
  )

  const handleTemplateSelect = (template: SchoolYearWizardTemplate) => {
    const range = resolveTemplateRange(template)
    setSelectedTemplateKey(template.key)
    setTermStructure(template.default_term_structure)
    setStepError('')
    syncSchoolYearDates(range, { keepTemplate: true })
  }

  const handleHolidayToggle = (key: string) => {
    setSelectedHolidayKeys((current) => (current.includes(key) ? current.filter((item) => item !== key) : [...current, key]))
  }

  const updateCustomBreak = (breakId: string, field: keyof SchoolYearWizardCustomBreak, value: string) => {
    setCustomBreaks((current) => current.map((item) => (item.id === breakId ? { ...item, [field]: value } : item)))
  }

  const handleClose = () => {
    if (!submitting) {
      onOpenChange(false)
    }
  }

  const getStepValidationError = (stepIndex: number) => {
    if (stepIndex === 0) {
      return getBasicsError(schoolYearForm, existingSchoolYears)
    }

    if (stepIndex === 2) {
      return getCustomBreaksError(schoolYearForm, customBreaks)
    }

    return ''
  }

  const handleNext = () => {
    const error = getStepValidationError(step)
    if (error) {
      setStepError(error)
      return
    }

    setStepError('')
    setSubmissionError('')
    setStep((current) => Math.min(current + 1, stepLabels.length - 1))
  }

  const handleBack = () => {
    setStepError('')
    setSubmissionError('')
    setStep((current) => Math.max(current - 1, 0))
  }

  const handleCreate = async () => {
    const basicsError = getBasicsError(schoolYearForm, existingSchoolYears)
    if (basicsError) {
      setStep(0)
      setStepError(basicsError)
      return
    }

    const customBreaksError = getCustomBreaksError(schoolYearForm, customBreaks)
    if (customBreaksError) {
      setStep(2)
      setStepError(customBreaksError)
      return
    }

    setStepError('')
    setSubmissionError('')
    setSubmitting(true)

    try {
      setSubmissionStage('Creating school year…')
      const payload: SchoolYearWizardCreatePayload = {
        name: schoolYearForm.name.trim(),
        start_date: schoolYearForm.start_date,
        end_date: schoolYearForm.end_date,
        term_structure: termStructure,
        holidays: selectedHolidayKeys,
        custom_breaks: customBreaks.map(({ id: _id, ...customBreak }) => ({
          name: customBreak.name.trim(),
          start_date: customBreak.start_date,
          end_date: customBreak.end_date,
        })),
        is_active: schoolYearForm.is_active,
      }

      const schoolYear = await api.createSchoolYearFromWizard(payload)
      setSubmissionStage('Refreshing calendar…')
      await onComplete(schoolYear.id)
      onOpenChange(false)
    } catch (error) {
      setSubmissionError(error instanceof Error ? error.message : 'Unable to create the school year setup.')
    } finally {
      setSubmitting(false)
      setSubmissionStage('')
    }
  }

  if (!open) {
    return null
  }

  return (
    <div className="fixed inset-0 z-50 p-4">
      <button type="button" aria-label="Close school year setup wizard" className="absolute inset-0 bg-black/50" onClick={handleClose} />
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="school-year-wizard-title"
        className="relative mx-auto flex h-full max-h-[calc(100vh-2rem)] w-full max-w-6xl items-center justify-center"
      >
        <Card className="flex max-h-full w-full flex-col overflow-hidden">
          <CardHeader className="border-b pb-5">
            <div className="flex items-start justify-between gap-3">
              <div className="space-y-2">
                <div className="flex flex-wrap items-center gap-2">
                  <Badge variant="secondary">Calendar setup</Badge>
                  <Badge variant="outline">Step {step + 1} of {stepLabels.length}</Badge>
                </div>
                <CardTitle id="school-year-wizard-title" className="flex items-center gap-2">
                  <Sparkles className="h-4 w-4 text-primary" />
                  School Year Setup Wizard
                </CardTitle>
                <CardDescription>
                  Choose a template, preview the term layout, add holidays, and create the whole school year in one pass.
                </CardDescription>
              </div>
              <Button type="button" variant="ghost" size="icon" aria-label="Close wizard" onClick={handleClose} disabled={submitting}>
                <X className="h-4 w-4" />
              </Button>
            </div>
            <div className="space-y-3 pt-2">
              <Progress value={((step + 1) / stepLabels.length) * 100} />
              <div className="grid gap-3 md:grid-cols-4">
                {stepLabels.map((label, index) => (
                  <div
                    key={label}
                    className={cn(
                      'rounded-xl border p-3 text-sm',
                      index === step ? 'border-primary bg-primary/5' : index < step ? 'border-emerald-500/30 bg-emerald-500/5' : 'bg-muted/30',
                    )}
                  >
                    <div className="flex items-center gap-2">
                      <span
                        className={cn(
                          'flex h-7 w-7 items-center justify-center rounded-full border text-xs font-semibold',
                          index < step
                            ? 'border-emerald-600 text-emerald-600'
                            : index === step
                              ? 'border-primary text-primary'
                              : 'border-muted-foreground/30 text-muted-foreground',
                        )}
                      >
                        {index < step ? <CheckCircle2 className="h-4 w-4" /> : index + 1}
                      </span>
                      <p className="font-medium">{label}</p>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </CardHeader>

          <CardContent className="flex-1 space-y-6 overflow-y-auto p-4 md:p-6">
            {step === 0 ? (
              <div className="space-y-6">
                <div className="space-y-3">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div>
                      <h3 className="font-semibold">Start with a school-year template</h3>
                      <p className="text-sm text-muted-foreground">Templates prefill dates and suggest the best term structure for common homeschool schedules.</p>
                    </div>
                    <Badge variant="outline">Smart default: upcoming August start</Badge>
                  </div>

                  {templatesLoading ? <LoadingState message="Loading school year templates…" /> : null}
                  {!templatesLoading && templatesError ? <ErrorState message={templatesError} onRetry={() => void loadTemplates()} /> : null}
                  {!templatesLoading && !templatesError ? (
                    templates.length ? (
                      <div className="grid gap-3 md:grid-cols-2">
                        {templates.map((template) => {
                          const templateRange = resolveTemplateRange(template)
                          const isSelected = selectedTemplateKey === template.key

                          return (
                            <button
                              key={template.key}
                              type="button"
                              className={cn(
                                'rounded-xl border p-4 text-left transition-colors hover:bg-muted/40',
                                isSelected && 'border-primary bg-primary/5',
                              )}
                              onClick={() => handleTemplateSelect(template)}
                            >
                              <div className="flex flex-wrap items-start justify-between gap-2">
                                <div>
                                  <p className="font-medium">{template.name}</p>
                                  <p className="mt-1 text-sm text-muted-foreground">{template.description}</p>
                                </div>
                                <Badge variant="secondary">{template.default_term_structure}</Badge>
                              </div>
                              <p className="mt-4 text-sm text-muted-foreground">{formatDateRange(templateRange.start_date, templateRange.end_date)}</p>
                            </button>
                          )
                        })}
                      </div>
                    ) : (
                      <EmptyState title="No templates available" description="You can still enter custom dates and build the school year manually." />
                    )
                  ) : null}
                </div>

                <Card>
                  <CardHeader>
                    <CardTitle>School year details</CardTitle>
                    <CardDescription>Pick custom dates any time — the wizard updates the suggested name and term preview automatically.</CardDescription>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    <div className="grid gap-4 md:grid-cols-2">
                      <div className="space-y-2 md:col-span-2">
                        <Label htmlFor="wizard-school-year-name">School year name</Label>
                        <Input
                          id="wizard-school-year-name"
                          value={schoolYearForm.name}
                          onChange={(event) => {
                            setNameManuallyEdited(true)
                            setSchoolYearForm((current) => ({ ...current, name: event.target.value }))
                          }}
                          placeholder="2026-2027 School Year"
                        />
                        {suggestedName ? <p className="text-xs text-muted-foreground">Suggested from dates: {suggestedName}</p> : null}
                      </div>
                      <div className="space-y-2">
                        <Label htmlFor="wizard-school-year-start">Start date</Label>
                        <Input
                          id="wizard-school-year-start"
                          type="date"
                          value={schoolYearForm.start_date}
                          onChange={(event) => syncSchoolYearDates({ start_date: event.target.value })}
                        />
                      </div>
                      <div className="space-y-2">
                        <Label htmlFor="wizard-school-year-end">End date</Label>
                        <Input
                          id="wizard-school-year-end"
                          type="date"
                          value={schoolYearForm.end_date}
                          onChange={(event) => syncSchoolYearDates({ end_date: event.target.value })}
                        />
                      </div>
                    </div>

                    <label className="flex items-center gap-2 rounded-lg border p-3 text-sm">
                      <input
                        type="checkbox"
                        className="h-4 w-4"
                        checked={schoolYearForm.is_active}
                        onChange={(event) => setSchoolYearForm((current) => ({ ...current, is_active: event.target.checked }))}
                      />
                      Make this the active school year
                    </label>
                  </CardContent>
                </Card>
              </div>
            ) : null}

            {step === 1 ? (
              <div className="space-y-6">
                <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
                  {termStructureOptions.map((option) => (
                    <button
                      key={option.key}
                      type="button"
                      className={cn(
                        'rounded-xl border p-4 text-left transition-colors hover:bg-muted/40',
                        termStructure === option.key && 'border-primary bg-primary/5',
                      )}
                      onClick={() => {
                        setTermStructure(option.key)
                        setStepError('')
                      }}
                    >
                      <p className="font-medium">{option.label}</p>
                      <p className="mt-2 text-sm text-muted-foreground">{option.description}</p>
                    </button>
                  ))}
                </div>

                <Card>
                  <CardHeader>
                    <CardTitle>Year split preview</CardTitle>
                    <CardDescription>
                      These dates are auto-calculated from the full school-year range and will be created by the backend wizard.
                    </CardDescription>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    <div className="flex overflow-hidden rounded-full border bg-muted/30">
                      {computedTerms.map((term, index) => (
                        <div
                          key={`${term.name}-${term.start_date}`}
                          className={cn(
                            'min-h-3 flex-1 border-r border-background/70',
                            index % 2 === 0 ? 'bg-primary/25' : 'bg-primary/15',
                            index === computedTerms.length - 1 && 'border-r-0',
                          )}
                        />
                      ))}
                    </div>
                    <div className="flex flex-wrap gap-3">
                      {computedTerms.map((term) => (
                        <div key={`${term.name}-${term.start_date}`} className="min-w-[13rem] flex-1 rounded-xl border p-4">
                          <p className="font-medium">{term.name}</p>
                          <p className="mt-1 text-sm text-muted-foreground">{formatDateRange(term.start_date, term.end_date)}</p>
                        </div>
                      ))}
                    </div>
                    {termStructure === 'custom' ? (
                      <p className="text-sm text-muted-foreground">Custom uses a single full-year term so you can adjust detailed term boundaries after creation.</p>
                    ) : null}
                  </CardContent>
                </Card>
              </div>
            ) : null}

            {step === 2 ? (
              <div className="space-y-6">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div>
                    <h3 className="font-semibold">Preset holidays for {holidayYear}</h3>
                    <p className="text-sm text-muted-foreground">Holiday dates come from the backend preset library and stay in sync with the create API.</p>
                  </div>
                  <Badge variant="outline">{selectedHolidayDayCount} preset day{selectedHolidayDayCount === 1 ? '' : 's'} selected</Badge>
                </div>

                {holidaysLoading ? <LoadingState message="Loading holiday presets…" /> : null}
                {!holidaysLoading && holidaysError ? <ErrorState message={holidaysError} onRetry={() => void loadHolidayPresets()} /> : null}
                {!holidaysLoading && !holidaysError ? (
                  <div className="space-y-4">
                    <HolidayPresetSection presets={holidayGroups.federal} selectedHolidayKeys={selectedHolidayKeys} onToggle={handleHolidayToggle} />
                    <HolidayPresetSection presets={holidayGroups.religious} selectedHolidayKeys={selectedHolidayKeys} onToggle={handleHolidayToggle} />
                    <HolidayPresetSection presets={holidayGroups.school_break} selectedHolidayKeys={selectedHolidayKeys} onToggle={handleHolidayToggle} />
                  </div>
                ) : null}

                <Card>
                  <CardHeader>
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div>
                        <CardTitle>Custom breaks</CardTitle>
                        <CardDescription>Add family-specific breaks like trips, co-op weeks, or local holidays.</CardDescription>
                      </div>
                      <Button type="button" variant="outline" size="sm" onClick={() => setCustomBreaks((current) => [...current, createCustomBreak()])}>
                        <Plus className="mr-2 h-4 w-4" />
                        Add break
                      </Button>
                    </div>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    {customBreaks.length ? (
                      customBreaks.map((customBreak, index) => (
                        <div key={customBreak.id} className="rounded-xl border p-4">
                          <div className="grid gap-3 lg:grid-cols-[minmax(0,1.2fr)_repeat(2,minmax(0,1fr))_auto] lg:items-end">
                            <div className="space-y-2">
                              <Label htmlFor={`custom-break-name-${customBreak.id}`}>Break name</Label>
                              <Input
                                id={`custom-break-name-${customBreak.id}`}
                                value={customBreak.name}
                                onChange={(event) => updateCustomBreak(customBreak.id, 'name', event.target.value)}
                                placeholder={index === 0 ? 'Fall Break' : 'Custom Break'}
                              />
                            </div>
                            <div className="space-y-2">
                              <Label htmlFor={`custom-break-start-${customBreak.id}`}>Start date</Label>
                              <Input
                                id={`custom-break-start-${customBreak.id}`}
                                type="date"
                                value={customBreak.start_date}
                                min={schoolYearForm.start_date}
                                max={schoolYearForm.end_date}
                                onChange={(event) => updateCustomBreak(customBreak.id, 'start_date', event.target.value)}
                              />
                            </div>
                            <div className="space-y-2">
                              <Label htmlFor={`custom-break-end-${customBreak.id}`}>End date</Label>
                              <Input
                                id={`custom-break-end-${customBreak.id}`}
                                type="date"
                                value={customBreak.end_date}
                                min={schoolYearForm.start_date}
                                max={schoolYearForm.end_date}
                                onChange={(event) => updateCustomBreak(customBreak.id, 'end_date', event.target.value)}
                              />
                            </div>
                            <Button
                              type="button"
                              variant="ghost"
                              className="justify-start lg:justify-center"
                              onClick={() => setCustomBreaks((current) => current.filter((item) => item.id !== customBreak.id))}
                            >
                              Remove
                            </Button>
                          </div>
                        </div>
                      ))
                    ) : (
                      <EmptyState title="No custom breaks yet" description="Optional: add any family-specific breaks before you create the school year." />
                    )}
                  </CardContent>
                </Card>
              </div>
            ) : null}

            {step === 3 ? (
              <div className="space-y-4">
                <div className="grid gap-4 lg:grid-cols-[0.95fr_1.05fr]">
                  <Card>
                    <CardHeader>
                      <CardTitle>School year summary</CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-3 text-sm">
                      <div>
                        <p className="font-medium">{schoolYearForm.name.trim() || suggestedName}</p>
                        <p className="text-muted-foreground">{formatDateRange(schoolYearForm.start_date, schoolYearForm.end_date)}</p>
                      </div>
                      <div className="flex flex-wrap gap-2">
                        <Badge variant={schoolYearForm.is_active ? 'default' : 'secondary'}>
                          {schoolYearForm.is_active ? 'Will be active' : 'Saved as inactive'}
                        </Badge>
                        <Badge variant="outline">{termStructure}</Badge>
                        <Badge variant="outline">{computedTerms.length} term{computedTerms.length === 1 ? '' : 's'}</Badge>
                        <Badge variant="outline">{selectedHolidayDayCount} preset day{selectedHolidayDayCount === 1 ? '' : 's'}</Badge>
                        <Badge variant="outline">{customBreaks.length} custom break{customBreaks.length === 1 ? '' : 's'}</Badge>
                      </div>
                    </CardContent>
                  </Card>

                  <Card>
                    <CardHeader>
                      <CardTitle>Term preview</CardTitle>
                      <CardDescription>These term dates mirror the backend wizard calculation.</CardDescription>
                    </CardHeader>
                    <CardContent className="space-y-3 text-sm">
                      {computedTerms.map((term) => (
                        <div key={`${term.name}-${term.start_date}`} className="rounded-lg border p-3">
                          <p className="font-medium">{term.name}</p>
                          <p className="text-muted-foreground">{formatDateRange(term.start_date, term.end_date)}</p>
                        </div>
                      ))}
                    </CardContent>
                  </Card>
                </div>

                <Card>
                  <CardHeader>
                    <CardTitle>Selected holidays & breaks</CardTitle>
                    <CardDescription>Review the preset holidays and any custom breaks before creating the year.</CardDescription>
                  </CardHeader>
                  <CardContent className="space-y-3 text-sm">
                    {selectedHolidayPresets.length ? (
                      selectedHolidayPresets.map((preset) => (
                        <div key={preset.key} className="rounded-lg border p-3">
                          <div className="flex flex-wrap items-center gap-2">
                            <CalendarDays className="h-4 w-4 text-muted-foreground" />
                            <p className="font-medium">{preset.name}</p>
                            <Badge variant="secondary">{getHolidayDayCount(preset)} day{getHolidayDayCount(preset) === 1 ? '' : 's'}</Badge>
                          </div>
                          <p className="mt-1 text-muted-foreground">{getHolidayTimingLabel(preset)}</p>
                        </div>
                      ))
                    ) : (
                      <p className="text-muted-foreground">No preset holidays selected.</p>
                    )}

                    {customBreaks.length ? (
                      <div className="space-y-3 pt-2">
                        {customBreaks.map((customBreak) => (
                          <div key={customBreak.id} className="rounded-lg border p-3">
                            <p className="font-medium">{customBreak.name}</p>
                            <p className="text-muted-foreground">{formatDateRange(customBreak.start_date, customBreak.end_date)}</p>
                          </div>
                        ))}
                      </div>
                    ) : null}
                  </CardContent>
                </Card>
              </div>
            ) : null}

            {stepError ? <p role="alert" className="text-sm text-destructive">{stepError}</p> : null}
            {submissionError ? <p role="alert" className="text-sm text-destructive">{submissionError}</p> : null}
            {submissionStage ? (
              <div role="status" aria-live="polite" className="flex items-center gap-2 rounded-lg border border-primary/30 bg-primary/5 p-3 text-sm text-primary">
                <Loader2 className="h-4 w-4 animate-spin" />
                <span>{submissionStage}</span>
              </div>
            ) : null}
          </CardContent>

          <CardFooter className="justify-between gap-3 border-t px-4 py-4 md:px-6">
            <div>
              {step === 0 ? (
                <Button type="button" variant="outline" onClick={handleClose} disabled={submitting}>
                  Cancel
                </Button>
              ) : (
                <Button type="button" variant="outline" onClick={handleBack} disabled={submitting}>
                  <ArrowLeft className="mr-2 h-4 w-4" />
                  Back
                </Button>
              )}
            </div>
            <div>
              {step < stepLabels.length - 1 ? (
                <Button type="button" onClick={handleNext} disabled={submitting || (step === 2 && holidaysLoading)}>
                  Next
                  <ArrowRight className="ml-2 h-4 w-4" />
                </Button>
              ) : (
                <Button type="button" onClick={() => void handleCreate()} disabled={submitting}>
                  {submitting ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
                  Create School Year
                </Button>
              )}
            </div>
          </CardFooter>
        </Card>
      </div>
    </div>
  )
}
