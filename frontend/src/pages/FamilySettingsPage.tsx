import { useCallback, useEffect, useMemo, useState } from 'react'
import { Plus, Save, Trash2 } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { api } from '@/lib/api'
import type {
  ComplianceCustomRulePayload,
  ComplianceRule,
  ComplianceRuleType,
  GradeScaleInput,
  GradeScaleRange,
  MaintenanceStatus,
} from '@/types/api'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Textarea } from '@/components/ui/textarea'
import { LoadingState } from '@/components/common/LoadingState'
import { ErrorState } from '@/components/common/ErrorState'
import { LanguageSelector } from '@/components/common/LanguageSelector'
import { useAuth } from '@/context/AuthContext'

const defaultRanges: GradeScaleRange[] = [
  { letter: 'A', min: 90, max: 100, gpa_points: 4 },
  { letter: 'B', min: 80, max: 89.99, gpa_points: 3 },
  { letter: 'C', min: 70, max: 79.99, gpa_points: 2 },
  { letter: 'D', min: 60, max: 69.99, gpa_points: 1 },
  { letter: 'F', min: 0, max: 59.99, gpa_points: 0 },
]

const stateCodes = ['CUSTOM', 'TX', 'CA', 'VA', 'NY', 'FL'] as const
const ruleTypeValues: ComplianceRuleType[] = [
  'attendance_days',
  'attendance_hours',
  'subjects_required',
  'assessment_required',
  'notification_required',
  'portfolio_required',
]

const blankRule: ComplianceCustomRulePayload = {
  rule_type: 'attendance_days',
  rule_name: '',
  description: '',
  threshold_value: '180',
  threshold_unit: 'days',
  subjects_list: null,
  is_active: true,
}

const featureDefinitions = [
  {
    key: 'attendance',
    label: 'Attendance Tracking',
    description: 'Show attendance navigation and allow access to the attendance page.',
  },
  {
    key: 'quizzes',
    label: 'Quizzes',
    description: 'Show quiz management and allow access to quiz routes.',
  },
  {
    key: 'compliance',
    label: 'Compliance Tracking',
    description: 'Show compliance dashboards, rules, and compliance reports routes.',
  },
  {
    key: 'portfolio',
    label: 'Portfolio',
    description: 'Show the portfolio workspace and allow access to portfolio routes.',
  },
  {
    key: 'planner',
    label: 'Schedule Planner',
    description: 'Show the planner in navigation and allow access to planner routes.',
  },
] as const

function normalizeFeatureSettings(enabledFeatures: Record<string, boolean>) {
  return Object.fromEntries(featureDefinitions.map((feature) => [feature.key, enabledFeatures[feature.key] !== false])) as Record<string, boolean>
}

function toLocalDateTime(value?: string | null) {
  if (!value) return ''
  const date = new Date(value)
  const offset = date.getTimezoneOffset()
  const local = new Date(date.getTime() - offset * 60_000)
  return local.toISOString().slice(0, 16)
}

function toIsoDateTime(value: string) {
  return value ? new Date(value).toISOString() : null
}

export function FamilySettingsPage() {
  const { t } = useTranslation(['common', 'settings'])
  const { enabledFeatures, refreshSession } = useAuth()
  const [scales, setScales] = useState<GradeScaleInput[]>([])
  const [featureSettings, setFeatureSettings] = useState<Record<string, boolean>>(() => normalizeFeatureSettings(enabledFeatures))
  const [stateCode, setStateCode] = useState('CUSTOM')
  const [customRules, setCustomRules] = useState<ComplianceRule[]>([])
  const [ruleForm, setRuleForm] = useState<ComplianceCustomRulePayload>(blankRule)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [savingFeatures, setSavingFeatures] = useState(false)
  const [savingState, setSavingState] = useState(false)
  const [savingRule, setSavingRule] = useState(false)
  const [maintenance, setMaintenance] = useState<MaintenanceStatus | null>(null)
  const [maintenanceMessage, setMaintenanceMessage] = useState('')
  const [maintenanceSaving, setMaintenanceSaving] = useState(false)
  const [scheduleSaving, setScheduleSaving] = useState(false)
  const [scheduleStart, setScheduleStart] = useState('')
  const [scheduleEnd, setScheduleEnd] = useState('')
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')

  const totalDefaults = useMemo(() => scales.filter((scale) => scale.is_default).length, [scales])
  const stateOptions = useMemo(
    () => stateCodes.map((value) => ({ value, label: t(`settings:family.states.${value}`) })),
    [t],
  )
  const ruleTypes = useMemo(
    () =>
      ruleTypeValues.map((value) => ({
        value,
        label: t(`settings:family.ruleTypes.${value}.label`),
        unit: t(`settings:family.ruleTypes.${value}.unit`),
      })),
    [t],
  )
  const selectedRuleType = useMemo(
    () => ruleTypes.find((option) => option.value === ruleForm.rule_type) ?? ruleTypes[0],
    [ruleForm.rule_type, ruleTypes],
  )

  useEffect(() => {
    setFeatureSettings(normalizeFeatureSettings(enabledFeatures))
  }, [enabledFeatures])

  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const [gradeScales, familyState, rulesResponse, maintenanceStatus] = await Promise.all([
        api.listGradeScales(),
        api.getFamilyComplianceState(),
        api.getComplianceRules(),
        api.getMaintenanceStatus(),
      ])
      setScales(gradeScales.map((scale) => ({ id: scale.id, name: scale.name, is_default: scale.is_default, ranges: scale.ranges })))
      setStateCode(familyState.state_code)
      setCustomRules(rulesResponse.rules.filter((rule) => rule.is_custom))
      setMaintenance(maintenanceStatus)
      setMaintenanceMessage(maintenanceStatus.message)
      setScheduleStart(toLocalDateTime(maintenanceStatus.start_at))
      setScheduleEnd(toLocalDateTime(maintenanceStatus.end_at))
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : t('settings:family.errors.load'))
    } finally {
      setLoading(false)
    }
  }, [t])

  useEffect(() => {
    void load()
  }, [load])

  const saveGradeScales = async () => {
    setSaving(true)
    setError('')
    setMessage('')
    try {
      const saved = await api.upsertGradeScales(scales)
      setScales(saved.map((scale) => ({ id: scale.id, name: scale.name, is_default: scale.is_default, ranges: scale.ranges })))
      setMessage(t('settings:family.messages.gradeScalesSaved'))
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : t('settings:family.errors.saveGradeScales'))
    } finally {
      setSaving(false)
    }
  }

  const saveState = async () => {
    setSavingState(true)
    setError('')
    setMessage('')
    try {
      const updated = await api.updateFamilyComplianceState(stateCode)
      const rulesResponse = await api.getComplianceRules(updated.state_code)
      setStateCode(updated.state_code)
      setCustomRules(rulesResponse.rules.filter((rule) => rule.is_custom))
      setMessage(t('settings:family.messages.stateSaved'))
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : t('settings:family.errors.saveState'))
    } finally {
      setSavingState(false)
    }
  }

  const saveFeatures = async (nextFeatures: Record<string, boolean>) => {
    setSavingFeatures(true)
    setError('')
    setMessage('')
    try {
      const updated = await api.updateFamilyFeatures(nextFeatures)
      setFeatureSettings(normalizeFeatureSettings(updated.enabled_features))
      await refreshSession()
      setMessage('Feature visibility updated.')
    } catch (saveError) {
      setFeatureSettings(normalizeFeatureSettings(enabledFeatures))
      setError(saveError instanceof Error ? saveError.message : 'Unable to save feature settings')
    } finally {
      setSavingFeatures(false)
    }
  }

  const saveCustomRule = async () => {
    setSavingRule(true)
    setError('')
    setMessage('')
    try {
      await api.createCustomComplianceRule({
        ...ruleForm,
        state_code: stateCode,
        subjects_list: ruleForm.rule_type === 'subjects_required' ? ruleForm.subjects_list ?? [] : null,
      })
      const rulesResponse = await api.getComplianceRules(stateCode)
      setCustomRules(rulesResponse.rules.filter((rule) => rule.is_custom))
      setRuleForm(blankRule)
      setMessage(t('settings:family.messages.customRuleSaved'))
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : t('settings:family.errors.saveCustomRule'))
    } finally {
      setSavingRule(false)
    }
  }

  const saveMaintenanceMode = async (enabled: boolean) => {
    setMaintenanceSaving(true)
    setError('')
    setMessage('')
    try {
      const updated = await api.toggleMaintenance({ enabled, message: maintenanceMessage })
      setMaintenance(updated)
      setMaintenanceMessage(updated.message)
      setMessage(t(enabled ? 'settings:family.messages.maintenanceEnabled' : 'settings:family.messages.maintenanceDisabled'))
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : t('settings:family.errors.saveMaintenance'))
    } finally {
      setMaintenanceSaving(false)
    }
  }

  const saveMaintenanceSchedule = async () => {
    setScheduleSaving(true)
    setError('')
    setMessage('')
    try {
      const updated = await api.scheduleMaintenance({
        start_at: toIsoDateTime(scheduleStart),
        end_at: toIsoDateTime(scheduleEnd),
        message: maintenanceMessage,
      })
      setMaintenance(updated)
      setMaintenanceMessage(updated.message)
      setScheduleStart(toLocalDateTime(updated.start_at))
      setScheduleEnd(toLocalDateTime(updated.end_at))
      setMessage(t(updated.start_at && updated.end_at ? 'settings:family.messages.maintenanceScheduled' : 'settings:family.messages.maintenanceCleared'))
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : t('settings:family.errors.saveSchedule'))
    } finally {
      setScheduleSaving(false)
    }
  }

  if (loading) return <LoadingState message={t('settings:family.loading')} />
  if (error && !scales.length && !customRules.length) return <ErrorState message={error} onRetry={() => void load()} />

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <CardTitle>{t('settings:language.title')}</CardTitle>
          <CardDescription>{t('settings:language.description')}</CardDescription>
        </CardHeader>
        <CardContent className="max-w-xs">
          <LanguageSelector />
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Features</CardTitle>
          <CardDescription>Choose which optional areas stay visible in navigation and available by route.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {featureDefinitions.map((feature) => {
            const inputId = `family-feature-${feature.key}`
            return (
              <div key={feature.key} className="flex items-start justify-between gap-4 rounded-lg border p-4">
                <div className="space-y-1">
                  <Label htmlFor={inputId} className="font-medium">
                    {feature.label}
                  </Label>
                  <p className="text-sm text-muted-foreground">{feature.description}</p>
                </div>
                <input
                  id={inputId}
                  type="checkbox"
                  className="mt-1 h-4 w-4"
                  checked={featureSettings[feature.key]}
                  disabled={savingFeatures}
                  onChange={(event) => {
                    const nextFeatures = { ...featureSettings, [feature.key]: event.target.checked }
                    setFeatureSettings(nextFeatures)
                    void saveFeatures(nextFeatures)
                  }}
                />
              </div>
            )
          })}
        </CardContent>
      </Card>

      <div className="grid gap-4 xl:grid-cols-[1fr_1.1fr]">
        <Card>
          <CardHeader>
            <CardTitle>{t('settings:family.maintenance.title')}</CardTitle>
            <CardDescription>{t('settings:family.maintenance.description')}</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex flex-wrap items-center gap-2">
              <Badge variant={maintenance?.active ? 'destructive' : 'secondary'}>
                {maintenance?.active ? t('settings:family.maintenance.active', { source: maintenance.source }) : t('settings:family.maintenance.inactive')}
              </Badge>
              {maintenance?.env_enabled ? <Badge variant="outline">{t('settings:family.maintenance.forcedByEnv')}</Badge> : null}
              {maintenance?.scheduled ? <Badge variant="outline">{t('settings:family.maintenance.windowSaved')}</Badge> : null}
            </div>
            <div className="space-y-2">
              <Label>{t('settings:family.maintenance.message')}</Label>
              <Textarea value={maintenanceMessage} onChange={(event) => setMaintenanceMessage(event.target.value)} />
            </div>
            <div className="flex flex-wrap gap-2">
              <Button onClick={() => void saveMaintenanceMode(true)} disabled={maintenanceSaving}>
                {t('settings:family.maintenance.enable')}
              </Button>
              <Button variant="outline" onClick={() => void saveMaintenanceMode(false)} disabled={maintenanceSaving}>
                {t('settings:family.maintenance.disable')}
              </Button>
            </div>
            <div className="grid gap-4 border-t pt-4 md:grid-cols-2">
              <div className="space-y-2">
                <Label>{t('settings:family.maintenance.windowStart')}</Label>
                <Input type="datetime-local" value={scheduleStart} onChange={(event) => setScheduleStart(event.target.value)} />
              </div>
              <div className="space-y-2">
                <Label>{t('settings:family.maintenance.windowEnd')}</Label>
                <Input type="datetime-local" value={scheduleEnd} onChange={(event) => setScheduleEnd(event.target.value)} />
              </div>
            </div>
            <div className="flex flex-wrap gap-2">
              <Button variant="outline" onClick={() => void saveMaintenanceSchedule()} disabled={scheduleSaving}>
                {t('settings:family.maintenance.saveWindow')}
              </Button>
              <Button
                variant="ghost"
                onClick={() => {
                  setScheduleStart('')
                  setScheduleEnd('')
                  void api
                    .scheduleMaintenance({ start_at: null, end_at: null, message: maintenanceMessage })
                    .then((updated) => {
                      setMaintenance(updated)
                      setMessage(t('settings:family.messages.maintenanceCleared'))
                    })
                    .catch((saveError) => setError(saveError instanceof Error ? saveError.message : t('settings:family.errors.clearSchedule')))
                }}
                disabled={scheduleSaving}
              >
                {t('settings:family.maintenance.clearWindow')}
              </Button>
            </div>
            <p className="text-xs text-muted-foreground">
              {t('settings:family.maintenance.bypassRoles', { roles: maintenance?.bypass_roles?.join(', ') || 'parent, co-parent' })}
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>{t('settings:family.compliance.title')}</CardTitle>
            <CardDescription>{t('settings:family.compliance.description')}</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <Label>{t('settings:family.compliance.state')}</Label>
              <Select value={stateCode} onValueChange={setStateCode}>
                <SelectTrigger className="w-full md:w-72">
                  <SelectValue placeholder={t('settings:family.compliance.chooseState')} />
                </SelectTrigger>
                <SelectContent>
                  {stateOptions.map((option) => (
                    <SelectItem key={option.value} value={option.value}>
                      {option.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <Button onClick={() => void saveState()} disabled={savingState}>
              {t('settings:family.compliance.saveState')}
            </Button>

            <div className="space-y-2 border-t pt-4">
              <Label>{t('settings:family.compliance.customRuleType')}</Label>
              <Select
                value={ruleForm.rule_type}
                onValueChange={(value) =>
                  setRuleForm((current) => ({
                    ...current,
                    rule_type: value as ComplianceRuleType,
                    threshold_unit: ruleTypes.find((option) => option.value === value)?.unit ?? current.threshold_unit,
                  }))
                }
              >
                <SelectTrigger className="w-full">
                  <SelectValue placeholder={t('settings:family.compliance.chooseRuleType')} />
                </SelectTrigger>
                <SelectContent>
                  {ruleTypes.map((option) => (
                    <SelectItem key={option.value} value={option.value}>
                      {option.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-2">
              <Label>{t('settings:family.compliance.ruleName')}</Label>
              <Input
                value={ruleForm.rule_name}
                onChange={(event) => setRuleForm((current) => ({ ...current, rule_name: event.target.value }))}
              />
            </div>
            <div className="space-y-2">
              <Label>{t('settings:family.compliance.descriptionLabel')}</Label>
              <Textarea
                value={ruleForm.description}
                onChange={(event) => setRuleForm((current) => ({ ...current, description: event.target.value }))}
              />
            </div>

            <div className="grid gap-4 md:grid-cols-2">
              <div className="space-y-2">
                <Label>{t('settings:family.compliance.requiredValue')}</Label>
                <Input
                  type="number"
                  min="0"
                  step="0.01"
                  value={ruleForm.threshold_value}
                  onChange={(event) => setRuleForm((current) => ({ ...current, threshold_value: event.target.value }))}
                />
              </div>
              <div className="space-y-2">
                <Label>{t('settings:family.compliance.unit')}</Label>
                <Input
                  value={ruleForm.threshold_unit}
                  onChange={(event) => setRuleForm((current) => ({ ...current, threshold_unit: event.target.value }))}
                />
              </div>
            </div>

            {ruleForm.rule_type === 'subjects_required' ? (
              <div className="space-y-2">
                <Label>{t('settings:family.compliance.subjects')}</Label>
                <Input
                  value={(ruleForm.subjects_list ?? []).join(', ')}
                  onChange={(event) =>
                    setRuleForm((current) => ({
                      ...current,
                      subjects_list: event.target.value
                        .split(',')
                        .map((item) => item.trim())
                        .filter(Boolean),
                    }))
                  }
                />
              </div>
            ) : null}

            <Button onClick={() => void saveCustomRule()} disabled={savingRule}>
              {t('settings:family.compliance.saveRule')}
            </Button>
            <p className="text-xs text-muted-foreground">
              {t('settings:family.compliance.helper', { label: selectedRuleType.label, unit: selectedRuleType.unit })}
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>{t('settings:family.compliance.customRulesTitle')}</CardTitle>
            <CardDescription>{t('settings:family.compliance.customRulesDescription')}</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            {customRules.length ? (
              customRules.map((rule) => (
                <div key={rule.id} className="rounded-lg border p-3">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div>
                      <p className="font-medium">{rule.rule_name}</p>
                      <p className="text-sm text-muted-foreground">{rule.description}</p>
                    </div>
                    <Badge variant="outline">{rule.rule_type.replaceAll('_', ' ')}</Badge>
                  </div>
                  <p className="mt-2 text-xs text-muted-foreground">
                    {t('settings:family.compliance.required', { value: rule.threshold_value, unit: rule.threshold_unit })}
                    {rule.subjects_list?.length ? ` · ${rule.subjects_list.join(', ')}` : ''}
                  </p>
                </div>
              ))
            ) : (
              <p className="text-sm text-muted-foreground">{t('settings:family.compliance.emptyRules')}</p>
            )}
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>{t('settings:family.gradeScales.title')}</CardTitle>
          <CardDescription>{t('settings:family.gradeScales.description')}</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-4">
            {scales.map((scale, scaleIndex) => (
              <div key={scale.id ?? `scale-${scaleIndex}`} className="space-y-4 rounded-lg border p-4">
                <div className="flex flex-wrap items-center gap-3">
                  <div className="min-w-[220px] flex-1 space-y-2">
                    <Label>{t('settings:family.gradeScales.scaleName')}</Label>
                    <Input
                      value={scale.name}
                      onChange={(event) =>
                        setScales((current) =>
                          current.map((item, itemIndex) => (itemIndex === scaleIndex ? { ...item, name: event.target.value } : item)),
                        )
                      }
                    />
                  </div>
                  <label className="flex items-center gap-2 text-sm">
                    <input
                      type="radio"
                      checked={scale.is_default}
                      onChange={() =>
                        setScales((current) =>
                          current.map((item, itemIndex) => ({ ...item, is_default: itemIndex === scaleIndex })),
                        )
                      }
                    />
                    {t('settings:family.gradeScales.defaultScale')}
                  </label>
                  <Button variant="ghost" size="sm" onClick={() => setScales((current) => current.filter((_, itemIndex) => itemIndex !== scaleIndex))}>
                    <Trash2 className="mr-2 h-3.5 w-3.5" />
                    {t('settings:family.gradeScales.remove')}
                  </Button>
                </div>

                <div className="grid gap-3 md:grid-cols-5">
                  {scale.ranges.map((range, rangeIndex) => (
                    <div key={`${scale.id ?? scaleIndex}-${rangeIndex}`} className="space-y-2 rounded-md border p-3">
                      <Label>{t('settings:family.gradeScales.letter')}</Label>
                      <Input
                        value={range.letter}
                        onChange={(event) =>
                          setScales((current) =>
                            current.map((item, itemIndex) =>
                              itemIndex === scaleIndex
                                ? {
                                    ...item,
                                    ranges: item.ranges.map((entry, entryIndex) =>
                                      entryIndex === rangeIndex ? { ...entry, letter: event.target.value.toUpperCase() } : entry,
                                    ),
                                  }
                                : item,
                            ),
                          )
                        }
                      />
                      <Label>{t('settings:family.gradeScales.min')}</Label>
                      <Input
                        type="number"
                        value={range.min}
                        onChange={(event) =>
                          setScales((current) =>
                            current.map((item, itemIndex) =>
                              itemIndex === scaleIndex
                                ? {
                                    ...item,
                                    ranges: item.ranges.map((entry, entryIndex) =>
                                      entryIndex === rangeIndex ? { ...entry, min: Number(event.target.value) } : entry,
                                    ),
                                  }
                                : item,
                            ),
                          )
                        }
                      />
                      <Label>{t('settings:family.gradeScales.max')}</Label>
                      <Input
                        type="number"
                        value={range.max}
                        onChange={(event) =>
                          setScales((current) =>
                            current.map((item, itemIndex) =>
                              itemIndex === scaleIndex
                                ? {
                                    ...item,
                                    ranges: item.ranges.map((entry, entryIndex) =>
                                      entryIndex === rangeIndex ? { ...entry, max: Number(event.target.value) } : entry,
                                    ),
                                  }
                                : item,
                            ),
                          )
                        }
                      />
                      <Label>{t('settings:family.gradeScales.gpa')}</Label>
                      <Input
                        type="number"
                        step="0.1"
                        value={range.gpa_points}
                        onChange={(event) =>
                          setScales((current) =>
                            current.map((item, itemIndex) =>
                              itemIndex === scaleIndex
                                ? {
                                    ...item,
                                    ranges: item.ranges.map((entry, entryIndex) =>
                                      entryIndex === rangeIndex ? { ...entry, gpa_points: Number(event.target.value) } : entry,
                                    ),
                                  }
                                : item,
                            ),
                          )
                        }
                      />
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>

          <div className="flex flex-wrap gap-2">
            <Button
              variant="outline"
              onClick={() =>
                setScales((current) => [
                  ...current,
                  { name: t('settings:family.gradeScales.scaleNameDefault', { count: current.length + 1 }), is_default: current.length === 0, ranges: defaultRanges },
                ])
              }
            >
              <Plus className="mr-2 h-4 w-4" />
              {t('settings:family.gradeScales.addScale')}
            </Button>
            <Button onClick={() => void saveGradeScales()} disabled={saving || totalDefaults !== 1}>
              <Save className="mr-2 h-4 w-4" />
              {t('settings:family.gradeScales.saveSettings')}
            </Button>
          </div>

          <p className="text-xs text-muted-foreground">{t('settings:family.messages.defaultCount', { count: totalDefaults })}</p>
          {message ? <p className="text-sm text-muted-foreground">{message}</p> : null}
          {error ? <p className="text-sm text-destructive">{error}</p> : null}
        </CardContent>
      </Card>
    </div>
  )
}
