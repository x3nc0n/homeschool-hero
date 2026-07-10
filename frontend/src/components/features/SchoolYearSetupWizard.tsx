import { useEffect, useMemo, useRef, useState } from 'react'
import { ArrowRight, CalendarDays, Check, Plus, Sparkles, Trash2 } from 'lucide-react'
import { api } from '@/lib/api'
import { cn } from '@/lib/utils'
import {
  buildGeneratedTerms,
  buildInstructionalDayPreview,
  buildPresetEvents,
  buildSchoolYearName,
  createDefaultCustomTerms,
  expandCustomBreaks,
  getStateHolidayPreset,
  getTemplateDefaults,
  getTemplateOptions,
  type HolidayPresetId,
  type SchoolYearTemplateId,
  type WizardBreakDraft,
  type WizardEventDraft,
  type WizardTermDraft,
  validateCustomBreaks,
  validateCustomTerms,
  validateSchoolYearRange,
} from '@/lib/schoolYearWizard'
import type { SchoolYear, TermType } from '@/types/api'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Progress } from '@/components/ui/progress'
import { Textarea } from '@/components/ui/textarea'

const steps = [
  { id: 'template', title: 'Template' },
  { id: 'structure', title: 'Terms' },
  { id: 'holidays', title: 'Holidays' },
  { id: 'review', title: 'Review' },
] as const

const termOptions: Array<{ id: TermType; title: string; description: string }> = [
  { id: 'semester', title: 'Semesters', description: 'Split the year into two larger terms.' },
  { id: 'quarter', title: 'Quarters', description: 'Use four smaller terms for tighter progress checks.' },
  { id: 'trimester', title: 'Trimesters', description: 'Keep three balanced terms across the year.' },
  { id: 'custom', title: 'Custom', description: 'Name each term yourself and choose the exact dates.' },
]

function parseDate(value: string) {
  const [year, month, day] = value.split('-').map(Number)
  return new Date(year, month - 1, day)
}

function compareDates(left: string, right: string) {
  return parseDate(left).getTime() - parseDate(right).getTime()
}

function formatDateLabel(value: string) {
  return parseDate(value).toLocaleDateString(undefined, {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  })
}

function monthLabel(value: string) {
  return parseDate(value).toLocaleDateString(undefined, {
    month: 'long',
    year: 'numeric',
  })
}

function formatDate(date: Date) {
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`
}

function clampDate(date: string, startDate: string, endDate: string) {
  if (compareDates(date, startDate) < 0) return startDate
  if (compareDates(date, endDate) > 0) return endDate
  return date
}

function createBreakId(counter: number) {
  return `custom-break-${counter}`
}

function createTermId(counter: number) {
  return `custom-term-${counter}`
}

function buildSuggestedBreak(kind: 'fall' | 'spring', startDate: string, endDate: string, id: string): WizardBreakDraft {
  const startYear = parseDate(startDate).getFullYear()
  const endYear = parseDate(endDate).getFullYear()
  const suggestion =
    kind === 'fall'
      ? {
          name: 'Fall Break',
          start: `${startYear}-10-13`,
          end: `${startYear}-10-17`,
          notes: 'A short autumn break.',
        }
      : {
          name: 'Spring Break',
          start: `${endYear}-03-16`,
          end: `${endYear}-03-20`,
          notes: 'A one-week spring break.',
        }

  const clampedStart = clampDate(suggestion.start, startDate, endDate)
  const clampedEnd = clampDate(suggestion.end, clampedStart, endDate)
  return {
    id,
    name: suggestion.name,
    start_date: clampedStart,
    end_date: clampedEnd,
    notes: suggestion.notes,
  }
}

function mergeEvents(events: WizardEventDraft[]) {
  const deduped = new Map<string, WizardEventDraft>()
  for (const event of events) {
    const key = `${event.date}:${event.name}`
    if (!deduped.has(key)) {
      deduped.set(key, event)
    }
  }
  return Array.from(deduped.values()).sort((left, right) => {
    const dateComparison = compareDates(left.date, right.date)
    return dateComparison !== 0 ? dateComparison : left.name.localeCompare(right.name)
  })
}

export function SchoolYearSetupWizard({
  existingYears,
  stateCode,
  onCreated,
}: {
  existingYears: SchoolYear[]
  stateCode?: string
  onCreated: (schoolYearId: number) => Promise<void>
}) {
  const initialDefaults = useMemo(() => getTemplateDefaults('traditional'), [])
  const [stepIndex, setStepIndex] = useState(0)
  const [templateId, setTemplateId] = useState<SchoolYearTemplateId>('traditional')
  const [schoolYearName, setSchoolYearName] = useState(initialDefaults.name)
  const [nameTouched, setNameTouched] = useState(false)
  const [startDate, setStartDate] = useState(initialDefaults.start_date)
  const [endDate, setEndDate] = useState(initialDefaults.end_date)
  const [isActive, setIsActive] = useState(existingYears.length === 0)
  const [termType, setTermType] = useState<TermType>('semester')
  const [customTerms, setCustomTerms] = useState<WizardTermDraft[]>(createDefaultCustomTerms(initialDefaults.start_date, initialDefaults.end_date))
  const [selectedPresets, setSelectedPresets] = useState<Record<HolidayPresetId, boolean>>({
    federal: true,
    religious: true,
    state: Boolean(getStateHolidayPreset(stateCode)),
  })
  const [customBreaks, setCustomBreaks] = useState<WizardBreakDraft[]>([])
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')
  const [isSaving, setIsSaving] = useState(false)
  const termCounter = useRef(2)
  const breakCounter = useRef(1)
  const endDateAutoSet = useRef(false)
  const statePreset = useMemo(() => getStateHolidayPreset(stateCode), [stateCode])

  useEffect(() => {
    if (!statePreset) return
    setSelectedPresets((current) => (current.state ? current : { ...current, state: true }))
  }, [statePreset])

  useEffect(() => {
    if (termType !== 'custom') return
    setCustomTerms((current) => {
      if (current.length) return current
      return createDefaultCustomTerms(startDate, endDate)
    })
  }, [endDate, startDate, termType])

  const generatedTerms = useMemo(() => buildGeneratedTerms(startDate, endDate, termType, customTerms), [customTerms, endDate, startDate, termType])
  const presetEvents = useMemo(
    () =>
      buildPresetEvents({
        startDate,
        endDate,
        includeFederal: selectedPresets.federal,
        includeReligious: selectedPresets.religious,
        includeState: selectedPresets.state,
        stateCode,
      }),
    [endDate, selectedPresets.federal, selectedPresets.religious, selectedPresets.state, startDate, stateCode],
  )
  const customBreakEvents = useMemo(() => expandCustomBreaks(customBreaks), [customBreaks])
  const reviewEvents = useMemo(() => mergeEvents([...presetEvents, ...customBreakEvents]), [customBreakEvents, presetEvents])
  const instructionalPreview = useMemo(() => buildInstructionalDayPreview(startDate, endDate, reviewEvents), [endDate, reviewEvents, startDate])
  const eventsByMonth = useMemo(
    () =>
      reviewEvents.reduce<Record<string, WizardEventDraft[]>>((accumulator, event) => {
        const key = event.date.slice(0, 7)
        accumulator[key] = [...(accumulator[key] || []), event]
        return accumulator
      }, {}),
    [reviewEvents],
  )

  const schoolYearRangeError = validateSchoolYearRange(startDate, endDate)
  const customTermError = termType === 'custom' ? validateCustomTerms(startDate, endDate, customTerms) : ''
  const customBreakError = validateCustomBreaks(startDate, endDate, customBreaks)
  const completion = ((stepIndex + 1) / steps.length) * 100

  const resetWizard = (nextIsActive = existingYears.length === 0) => {
    const defaults = getTemplateDefaults('traditional')
    setStepIndex(0)
    setTemplateId('traditional')
    setSchoolYearName(defaults.name)
    setNameTouched(false)
    setStartDate(defaults.start_date)
    setEndDate(defaults.end_date)
    setIsActive(nextIsActive)
    setTermType('semester')
    setCustomTerms(createDefaultCustomTerms(defaults.start_date, defaults.end_date))
    setCustomBreaks([])
    setSelectedPresets({
      federal: true,
      religious: true,
      state: Boolean(getStateHolidayPreset(stateCode)),
    })
    endDateAutoSet.current = false
    setError('')
    setSuccess('')
  }

  const applyTemplate = (nextTemplateId: SchoolYearTemplateId) => {
    const defaults = getTemplateDefaults(nextTemplateId)
    setTemplateId(nextTemplateId)
    setStartDate(defaults.start_date)
    setEndDate(defaults.end_date)
    setSchoolYearName(defaults.name)
    setNameTouched(false)
    setCustomTerms(createDefaultCustomTerms(defaults.start_date, defaults.end_date))
    endDateAutoSet.current = false
    setError('')
    setSuccess('')
  }

  const updateDate = (field: 'start' | 'end', value: string) => {
    const nextStart = field === 'start' ? value : startDate
    let nextEnd = field === 'end' ? value : endDate

    if (field === 'start' && value) {
      if (!nextEnd || endDateAutoSet.current) {
        const d = parseDate(value)
        d.setDate(d.getDate() + 1)
        nextEnd = formatDate(d)
        endDateAutoSet.current = true
      }
    } else if (field === 'end') {
      endDateAutoSet.current = false
    }

    if (!nameTouched && nextStart && nextEnd && compareDates(nextStart, nextEnd) <= 0) {
      setSchoolYearName(buildSchoolYearName(nextStart, nextEnd))
    }
    if (field === 'start') {
      setStartDate(value)
    }
    setEndDate(nextEnd)
    setError('')
    setSuccess('')
  }

  const addCustomTerm = () => {
    setCustomTerms((current) => [
      ...current,
      {
        id: createTermId(termCounter.current),
        name: `Term ${current.length + 1}`,
        start_date: startDate,
        end_date: endDate,
      },
    ])
    termCounter.current += 1
  }

  const addCustomBreak = (kind?: 'fall' | 'spring') => {
    const id = createBreakId(breakCounter.current)
    breakCounter.current += 1
    setCustomBreaks((current) => [
      ...current,
      kind
        ? buildSuggestedBreak(kind, startDate, endDate, id)
        : { id, name: '', start_date: '', end_date: '', notes: '' },
    ])
  }

  const validateCurrentStep = () => {
    if (stepIndex === 0) {
      return schoolYearRangeError || (!schoolYearName.trim() ? 'Give the school year a name.' : '')
    }
    if (stepIndex === 1) {
      return customTermError
    }
    if (stepIndex === 2) {
      return customBreakError
    }
    return ''
  }

  const handleNext = () => {
    const stepError = validateCurrentStep()
    if (stepError) {
      setError(stepError)
      return
    }
    setError('')
    setSuccess('')
    setStepIndex((current) => Math.min(current + 1, steps.length - 1))
  }

  const handleSave = async () => {
    const stepError = validateCurrentStep()
    if (stepError) {
      setError(stepError)
      return
    }

    setIsSaving(true)
    setError('')
    setSuccess('')
    let createdSchoolYear: SchoolYear | null = null

    try {
      createdSchoolYear = await api.createSchoolYear({
        name: schoolYearName.trim(),
        start_date: startDate,
        end_date: endDate,
        is_active: isActive,
      })

      for (const term of generatedTerms) {
        await api.createTerm({
          school_year_id: createdSchoolYear.id,
          name: term.name,
          start_date: term.start_date,
          end_date: term.end_date,
          term_type: term.term_type,
        })
      }

      for (const event of reviewEvents) {
        await api.createCalendarEvent({
          school_year_id: createdSchoolYear.id,
          date: event.date,
          event_type: event.event_type,
          name: event.name,
          is_instructional_day: event.is_instructional_day,
          notes: event.notes || null,
        })
      }

      await onCreated(createdSchoolYear.id)
      resetWizard(false)
      setSuccess('Your school year is ready. You can fine-tune terms or holiday dates below any time.')
    } catch (saveError) {
      if (createdSchoolYear) {
        await onCreated(createdSchoolYear.id)
        setError('The school year was created, but a few terms or holidays still need attention. Finish any touch-ups below.')
      } else {
        setError(saveError instanceof Error ? saveError.message : 'Unable to create the school year wizard draft.')
      }
    } finally {
      setIsSaving(false)
    }
  }

  return (
    <Card>
      <CardHeader>
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <CardTitle className="flex items-center gap-2">
              <Sparkles className="h-4 w-4 text-primary" />
              School year setup wizard
            </CardTitle>
            <CardDescription>
              Walk through the year once, then use the calendar tools below to tweak anything later.
            </CardDescription>
          </div>
          <Badge variant="outline">Step {stepIndex + 1} of {steps.length}</Badge>
        </div>
      </CardHeader>
      <CardContent className="space-y-5">
        <Progress value={completion} />

        <div className="flex flex-wrap gap-2">
          {steps.map((step, index) => (
            <Button
              key={step.id}
              type="button"
              size="sm"
              variant={index === stepIndex ? 'default' : index < stepIndex ? 'outline' : 'ghost'}
              onClick={() => {
                if (index > stepIndex) return
                setError('')
                setStepIndex(index)
              }}
              disabled={index > stepIndex}
            >
              {index < stepIndex ? <Check className="mr-2 h-3.5 w-3.5" /> : null}
              {step.title}
            </Button>
          ))}
        </div>

        {success ? <div className="rounded-lg border border-emerald-300 bg-emerald-50 px-4 py-3 text-sm text-emerald-900">{success}</div> : null}
        {error ? <div className="rounded-lg border border-destructive/30 bg-destructive/5 px-4 py-3 text-sm text-destructive">{error}</div> : null}

        {stepIndex === 0 ? (
          <div className="space-y-4">
            <div>
              <h3 className="text-sm font-semibold">Start with a familiar template</h3>
              <p className="text-sm text-muted-foreground">Choose the pattern closest to your family rhythm. You can still adjust the dates.</p>
            </div>
            <div className="grid gap-3 md:grid-cols-2">
              {getTemplateOptions().map((option) => (
                <button
                  key={option.id}
                  type="button"
                  className={cn(
                    'rounded-xl border p-4 text-left transition-colors',
                    templateId === option.id ? 'border-primary bg-primary/5' : 'hover:border-primary/40 hover:bg-muted/30',
                  )}
                  onClick={() => applyTemplate(option.id)}
                >
                  <p className="font-semibold">{option.label}</p>
                  <p className="mt-1 text-sm text-muted-foreground">{option.description}</p>
                </button>
              ))}
            </div>

            <div className="grid gap-4 md:grid-cols-2">
              <div className="space-y-2 md:col-span-2">
                <Label htmlFor="school-year-name">School year name</Label>
                <Input
                  id="school-year-name"
                  value={schoolYearName}
                  onChange={(event) => {
                    setSchoolYearName(event.target.value)
                    setNameTouched(true)
                    setError('')
                    setSuccess('')
                  }}
                  placeholder="2026-2027"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="school-year-start">Start date</Label>
                <Input id="school-year-start" type="date" value={startDate} onChange={(event) => updateDate('start', event.target.value)} />
              </div>
              <div className="space-y-2">
                <Label htmlFor="school-year-end">End date</Label>
                <Input id="school-year-end" type="date" value={endDate} min={startDate || undefined} onChange={(event) => updateDate('end', event.target.value)} />
              </div>
            </div>

            <label className="flex items-center gap-2 text-sm">
              <input type="checkbox" checked={isActive} onChange={(event) => setIsActive(event.target.checked)} />
              Make this the active school year
            </label>

            <div className="rounded-lg border bg-muted/20 p-4 text-sm text-muted-foreground">
              {existingYears.length
                ? `You already have ${existingYears.length} school year${existingYears.length === 1 ? '' : 's'}. The wizard will add a new one without replacing older calendars.`
                : 'This will create your first school year and turn on the calendar tools for the family.'}
            </div>
          </div>
        ) : null}

        {stepIndex === 1 ? (
          <div className="space-y-4">
            <div>
              <h3 className="text-sm font-semibold">Choose how you want to divide the year</h3>
              <p className="text-sm text-muted-foreground">Semesters, quarters, trimesters, or a fully custom layout all work.</p>
            </div>

            <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
              {termOptions.map((option) => (
                <button
                  key={option.id}
                  type="button"
                  className={cn(
                    'rounded-xl border p-4 text-left transition-colors',
                    termType === option.id ? 'border-primary bg-primary/5' : 'hover:border-primary/40 hover:bg-muted/30',
                  )}
                  onClick={() => {
                    setTermType(option.id)
                    setError('')
                  }}
                >
                  <p className="font-semibold">{option.title}</p>
                  <p className="mt-1 text-sm text-muted-foreground">{option.description}</p>
                </button>
              ))}
            </div>

            {termType === 'custom' ? (
              <div className="space-y-3 rounded-xl border p-4">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div>
                    <p className="font-semibold">Custom term dates</p>
                    <p className="text-sm text-muted-foreground">Add as many terms as you need. Keep each term inside the school year.</p>
                  </div>
                  <Button type="button" size="sm" variant="outline" onClick={addCustomTerm}>
                    <Plus className="mr-2 h-3.5 w-3.5" />
                    Add term
                  </Button>
                </div>

                {customTerms.map((term, index) => (
                  <div key={term.id} className="grid gap-3 rounded-lg border bg-muted/20 p-3 md:grid-cols-[1.2fr_1fr_1fr_auto]">
                    <div className="space-y-2">
                      <Label htmlFor={`term-name-${term.id}`}>Term name</Label>
                      <Input
                        id={`term-name-${term.id}`}
                        value={term.name}
                        onChange={(event) =>
                          setCustomTerms((current) =>
                            current.map((entry) => (entry.id === term.id ? { ...entry, name: event.target.value } : entry)),
                          )
                        }
                      />
                    </div>
                    <div className="space-y-2">
                      <Label htmlFor={`term-start-${term.id}`}>Start date</Label>
                      <Input
                        id={`term-start-${term.id}`}
                        type="date"
                        value={term.start_date}
                        onChange={(event) =>
                          setCustomTerms((current) =>
                            current.map((entry) => (entry.id === term.id ? { ...entry, start_date: event.target.value } : entry)),
                          )
                        }
                      />
                    </div>
                    <div className="space-y-2">
                      <Label htmlFor={`term-end-${term.id}`}>End date</Label>
                      <Input
                        id={`term-end-${term.id}`}
                        type="date"
                        value={term.end_date}
                        onChange={(event) =>
                          setCustomTerms((current) =>
                            current.map((entry) => (entry.id === term.id ? { ...entry, end_date: event.target.value } : entry)),
                          )
                        }
                      />
                    </div>
                    <div className="flex items-end justify-end">
                      <Button
                        type="button"
                        size="icon-sm"
                        variant="ghost"
                        onClick={() => setCustomTerms((current) => current.filter((entry) => entry.id !== term.id || current.length === 1))}
                        disabled={index === 0 && customTerms.length === 1}
                        aria-label={`Remove ${term.name || `term ${index + 1}`}`}
                      >
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    </div>
                  </div>
                ))}
              </div>
            ) : null}

            <div className="rounded-xl border p-4">
              <div className="flex items-center gap-2">
                <CalendarDays className="h-4 w-4 text-primary" />
                <p className="font-semibold">Term preview</p>
              </div>
              <div className="mt-3 space-y-2">
                {generatedTerms.map((term) => (
                  <div key={term.id} className="flex flex-wrap items-center justify-between gap-2 rounded-lg border bg-muted/20 px-3 py-2 text-sm">
                    <div>
                      <p className="font-medium">{term.name}</p>
                      <p className="text-muted-foreground">{formatDateLabel(term.start_date)} – {formatDateLabel(term.end_date)}</p>
                    </div>
                    <Badge variant="outline">{term.term_type}</Badge>
                  </div>
                ))}
              </div>
            </div>
          </div>
        ) : null}

        {stepIndex === 2 ? (
          <div className="space-y-4">
            <div>
              <h3 className="text-sm font-semibold">Add holidays and breaks</h3>
              <p className="text-sm text-muted-foreground">Turn common closures on once, then add any custom breaks your family needs.</p>
            </div>

            <div className="grid gap-3 lg:grid-cols-3">
              {([
                {
                  id: 'federal',
                  title: 'US federal holidays',
                  description: 'New Year’s Day, Labor Day, Thanksgiving, and the rest of the federal calendar.',
                },
                {
                  id: 'religious',
                  title: 'Common religious holidays',
                  description: 'Christmas break plus Easter-related closures.',
                },
                {
                  id: 'state',
                  title: statePreset ? `${statePreset.label} (${statePreset.stateCode})` : 'State-specific holidays',
                  description: statePreset
                    ? statePreset.description
                    : stateCode
                      ? `No curated preset is ready for ${stateCode} yet. You can still add that break below.`
                      : 'Pick your family state in Family Settings to unlock a suggested preset here.',
                },
              ] as const).map((preset) => {
                const enabled = selectedPresets[preset.id]
                const isDisabled = preset.id === 'state' && !statePreset
                return (
                  <button
                    key={preset.id}
                    type="button"
                    className={cn(
                      'rounded-xl border p-4 text-left transition-colors',
                      enabled ? 'border-primary bg-primary/5' : 'hover:border-primary/40 hover:bg-muted/30',
                      isDisabled ? 'cursor-not-allowed opacity-60' : '',
                    )}
                    onClick={() => {
                      if (isDisabled) return
                      setSelectedPresets((current) => ({ ...current, [preset.id]: !current[preset.id] }))
                      setError('')
                    }}
                    disabled={isDisabled}
                  >
                    <div className="flex items-center justify-between gap-2">
                      <p className="font-semibold">{preset.title}</p>
                      <Badge variant={enabled ? 'secondary' : 'outline'}>{enabled ? 'On' : 'Off'}</Badge>
                    </div>
                    <p className="mt-1 text-sm text-muted-foreground">{preset.description}</p>
                  </button>
                )
              })}
            </div>

            <div className="rounded-xl border p-4">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div>
                  <p className="font-semibold">Custom breaks</p>
                  <p className="text-sm text-muted-foreground">Add a spring break, fall break, co-op pause, or any family-specific closure.</p>
                </div>
                <div className="flex flex-wrap gap-2">
                  <Button type="button" size="sm" variant="outline" onClick={() => addCustomBreak('fall')}>
                    Add fall break
                  </Button>
                  <Button type="button" size="sm" variant="outline" onClick={() => addCustomBreak('spring')}>
                    Add spring break
                  </Button>
                  <Button type="button" size="sm" onClick={() => addCustomBreak()}>
                    <Plus className="mr-2 h-3.5 w-3.5" />
                    Add custom break
                  </Button>
                </div>
              </div>

              {customBreaks.length ? (
                <div className="mt-4 space-y-3">
                  {customBreaks.map((customBreak, index) => (
                    <div key={customBreak.id} className="rounded-lg border bg-muted/20 p-3">
                      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-[1.2fr_1fr_1fr_auto]">
                        <div className="space-y-2">
                          <Label htmlFor={`break-name-${customBreak.id}`}>Break name</Label>
                          <Input
                            id={`break-name-${customBreak.id}`}
                            value={customBreak.name}
                            placeholder={`Break ${index + 1}`}
                            onChange={(event) =>
                              setCustomBreaks((current) =>
                                current.map((entry) => (entry.id === customBreak.id ? { ...entry, name: event.target.value } : entry)),
                              )
                            }
                          />
                        </div>
                        <div className="space-y-2">
                          <Label htmlFor={`break-start-${customBreak.id}`}>Start date</Label>
                          <Input
                            id={`break-start-${customBreak.id}`}
                            type="date"
                            value={customBreak.start_date}
                            onChange={(event) =>
                              setCustomBreaks((current) =>
                                current.map((entry) => (entry.id === customBreak.id ? { ...entry, start_date: event.target.value } : entry)),
                              )
                            }
                          />
                        </div>
                        <div className="space-y-2">
                          <Label htmlFor={`break-end-${customBreak.id}`}>End date</Label>
                          <Input
                            id={`break-end-${customBreak.id}`}
                            type="date"
                            value={customBreak.end_date}
                            onChange={(event) =>
                              setCustomBreaks((current) =>
                                current.map((entry) => (entry.id === customBreak.id ? { ...entry, end_date: event.target.value } : entry)),
                              )
                            }
                          />
                        </div>
                        <div className="flex items-end justify-end">
                          <Button
                            type="button"
                            size="icon-sm"
                            variant="ghost"
                            onClick={() => setCustomBreaks((current) => current.filter((entry) => entry.id !== customBreak.id))}
                            aria-label={`Remove ${customBreak.name || `break ${index + 1}`}`}
                          >
                            <Trash2 className="h-4 w-4" />
                          </Button>
                        </div>
                      </div>
                      <div className="mt-3 space-y-2">
                        <Label htmlFor={`break-notes-${customBreak.id}`}>Notes</Label>
                        <Textarea
                          id={`break-notes-${customBreak.id}`}
                          value={customBreak.notes}
                          placeholder="Optional note for this break"
                          onChange={(event) =>
                            setCustomBreaks((current) =>
                              current.map((entry) => (entry.id === customBreak.id ? { ...entry, notes: event.target.value } : entry)),
                            )
                          }
                        />
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="mt-4 text-sm text-muted-foreground">No custom breaks yet. Presets will still load if you keep them turned on.</p>
              )}
            </div>

            <div className="grid gap-3 md:grid-cols-3">
              <Card size="sm">
                <CardHeader>
                  <CardDescription>Preset holidays</CardDescription>
                  <CardTitle>{presetEvents.length}</CardTitle>
                </CardHeader>
              </Card>
              <Card size="sm">
                <CardHeader>
                  <CardDescription>Custom break dates</CardDescription>
                  <CardTitle>{customBreakEvents.length}</CardTitle>
                </CardHeader>
              </Card>
              <Card size="sm">
                <CardHeader>
                  <CardDescription>Total non-instructional dates</CardDescription>
                  <CardTitle>{reviewEvents.length}</CardTitle>
                </CardHeader>
              </Card>
            </div>
          </div>
        ) : null}

        {stepIndex === 3 ? (
          <div className="space-y-4">
            <div>
              <h3 className="text-sm font-semibold">Review your calendar before saving</h3>
              <p className="text-sm text-muted-foreground">You’ll still be able to edit every term, grading period, and closure after the school year is created.</p>
            </div>

            <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
              <Card size="sm">
                <CardHeader>
                  <CardDescription>School year</CardDescription>
                  <CardTitle>{schoolYearName.trim() || 'Untitled'}</CardTitle>
                </CardHeader>
              </Card>
              <Card size="sm">
                <CardHeader>
                  <CardDescription>Instructional days</CardDescription>
                  <CardTitle>{instructionalPreview.instructionalDays}</CardTitle>
                </CardHeader>
              </Card>
              <Card size="sm">
                <CardHeader>
                  <CardDescription>Terms</CardDescription>
                  <CardTitle>{generatedTerms.length}</CardTitle>
                </CardHeader>
              </Card>
              <Card size="sm">
                <CardHeader>
                  <CardDescription>Holidays & breaks</CardDescription>
                  <CardTitle>{reviewEvents.length}</CardTitle>
                </CardHeader>
              </Card>
            </div>

            <div className="grid gap-4 xl:grid-cols-[0.9fr_1.1fr]">
              <div className="space-y-4">
                <div className="rounded-xl border p-4">
                  <p className="font-semibold">Dates</p>
                  <p className="mt-2 text-sm text-muted-foreground">{formatDateLabel(startDate)} – {formatDateLabel(endDate)}</p>
                  <div className="mt-3 flex flex-wrap gap-2">
                    <Badge variant={isActive ? 'secondary' : 'outline'}>{isActive ? 'Active school year' : 'Saved as inactive'}</Badge>
                    <Badge variant="outline">{templateId.replace('_', ' ')}</Badge>
                    <Badge variant="outline">{termType}</Badge>
                  </div>
                </div>

                <div className="rounded-xl border p-4">
                  <p className="font-semibold">Term plan</p>
                  <div className="mt-3 space-y-2">
                    {generatedTerms.map((term) => (
                      <div key={term.id} className="rounded-lg border bg-muted/20 px-3 py-2 text-sm">
                        <p className="font-medium">{term.name}</p>
                        <p className="text-muted-foreground">{formatDateLabel(term.start_date)} – {formatDateLabel(term.end_date)}</p>
                      </div>
                    ))}
                  </div>
                </div>

                <div className="rounded-xl border p-4 text-sm text-muted-foreground">
                  Weekday baseline {instructionalPreview.weekdayDays} • Closures {instructionalPreview.nonInstructionalOverrides} • Weekend instructional days {instructionalPreview.instructionalOverrides}
                </div>
              </div>

              <div className="rounded-xl border p-4">
                <div className="flex items-center justify-between gap-2">
                  <p className="font-semibold">Calendar preview</p>
                  <Badge variant="outline">{reviewEvents.length} dates</Badge>
                </div>
                {reviewEvents.length ? (
                  <div className="mt-4 space-y-4">
                    {Object.entries(eventsByMonth).map(([monthKey, events]) => (
                      <div key={monthKey}>
                        <p className="text-sm font-medium">{monthLabel(`${monthKey}-01`)}</p>
                        <div className="mt-2 space-y-2">
                          {events.map((event) => (
                            <div key={`${event.date}-${event.name}`} className="flex flex-wrap items-start justify-between gap-2 rounded-lg border bg-muted/20 px-3 py-2 text-sm">
                              <div>
                                <p className="font-medium">{event.name}</p>
                                <p className="text-muted-foreground">{formatDateLabel(event.date)}{event.notes ? ` · ${event.notes}` : ''}</p>
                              </div>
                              <Badge variant="outline">{event.source}</Badge>
                            </div>
                          ))}
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="mt-4 text-sm text-muted-foreground">No holiday dates are queued yet. You can still save the year and add closures later.</p>
                )}
              </div>
            </div>
          </div>
        ) : null}

        <div className="flex flex-wrap items-center justify-between gap-2 border-t pt-4">
          <Button type="button" variant="ghost" onClick={() => resetWizard()} disabled={isSaving}>
            Reset wizard
          </Button>
          <div className="flex flex-wrap gap-2">
            <Button type="button" variant="outline" onClick={() => setStepIndex((current) => Math.max(current - 1, 0))} disabled={stepIndex === 0 || isSaving}>
              Back
            </Button>
            {stepIndex < steps.length - 1 ? (
              <Button type="button" onClick={handleNext} disabled={isSaving}>
                Next
                <ArrowRight className="ml-2 h-4 w-4" />
              </Button>
            ) : (
              <Button type="button" onClick={() => void handleSave()} disabled={isSaving}>
                {isSaving ? 'Creating school year…' : 'Create school year'}
              </Button>
            )}
          </div>
        </div>
      </CardContent>
    </Card>
  )
}
