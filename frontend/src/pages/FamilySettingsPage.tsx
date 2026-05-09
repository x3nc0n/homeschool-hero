import { useEffect, useMemo, useState } from 'react'
import { Plus, Save, Trash2 } from 'lucide-react'
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

const defaultRanges: GradeScaleRange[] = [
  { letter: 'A', min: 90, max: 100, gpa_points: 4 },
  { letter: 'B', min: 80, max: 89.99, gpa_points: 3 },
  { letter: 'C', min: 70, max: 79.99, gpa_points: 2 },
  { letter: 'D', min: 60, max: 69.99, gpa_points: 1 },
  { letter: 'F', min: 0, max: 59.99, gpa_points: 0 },
]

const stateOptions = [
  { value: 'CUSTOM', label: 'Custom / generic' },
  { value: 'TX', label: 'Texas' },
  { value: 'CA', label: 'California' },
  { value: 'VA', label: 'Virginia' },
  { value: 'NY', label: 'New York' },
  { value: 'FL', label: 'Florida' },
]

const ruleTypes: Array<{ value: ComplianceRuleType; label: string; unit: string }> = [
  { value: 'attendance_days', label: 'Attendance days', unit: 'days' },
  { value: 'attendance_hours', label: 'Attendance hours', unit: 'hours' },
  { value: 'subjects_required', label: 'Required subjects', unit: 'count' },
  { value: 'assessment_required', label: 'Assessment evidence', unit: 'count' },
  { value: 'notification_required', label: 'Notifications / reports', unit: 'count' },
  { value: 'portfolio_required', label: 'Portfolio evidence', unit: 'count' },
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
  const [scales, setScales] = useState<GradeScaleInput[]>([])
  const [stateCode, setStateCode] = useState('CUSTOM')
  const [customRules, setCustomRules] = useState<ComplianceRule[]>([])
  const [ruleForm, setRuleForm] = useState<ComplianceCustomRulePayload>(blankRule)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
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
  const selectedRuleType = useMemo(
    () => ruleTypes.find((option) => option.value === ruleForm.rule_type) ?? ruleTypes[0],
    [ruleForm.rule_type],
  )

  const load = async () => {
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
      setError(loadError instanceof Error ? loadError.message : 'Unable to load family settings')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void load()
  }, [])

  const saveGradeScales = async () => {
    setSaving(true)
    setError('')
    setMessage('')
    try {
      const saved = await api.upsertGradeScales(scales)
      setScales(saved.map((scale) => ({ id: scale.id, name: scale.name, is_default: scale.is_default, ranges: scale.ranges })))
      setMessage('Grade scales updated.')
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : 'Unable to save grade scales')
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
      setMessage('Family state updated.')
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : 'Unable to save family state')
    } finally {
      setSavingState(false)
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
      setMessage('Custom rule saved.')
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : 'Unable to save custom rule')
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
      setMessage(enabled ? 'Maintenance mode enabled.' : 'Maintenance mode disabled.')
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : 'Unable to update maintenance mode')
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
      setMessage(updated.start_at && updated.end_at ? 'Maintenance window scheduled.' : 'Maintenance schedule cleared.')
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : 'Unable to save maintenance schedule')
    } finally {
      setScheduleSaving(false)
    }
  }

  if (loading) return <LoadingState message="Loading family settings…" />
  if (error && !scales.length && !customRules.length) return <ErrorState message={error} onRetry={() => void load()} />

  return (
    <div className="space-y-4">
      <div className="grid gap-4 xl:grid-cols-[1fr_1.1fr]">
        <Card>
          <CardHeader>
            <CardTitle>Maintenance mode</CardTitle>
            <CardDescription>Pause access for non-admin users while parents and co-parents keep operator access.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex flex-wrap items-center gap-2">
              <Badge variant={maintenance?.active ? 'destructive' : 'secondary'}>
                {maintenance?.active ? `Active via ${maintenance.source}` : 'Inactive'}
              </Badge>
              {maintenance?.env_enabled ? <Badge variant="outline">Forced by env</Badge> : null}
              {maintenance?.scheduled ? <Badge variant="outline">Window saved</Badge> : null}
            </div>
            <div className="space-y-2">
              <Label>Maintenance message</Label>
              <Textarea value={maintenanceMessage} onChange={(event) => setMaintenanceMessage(event.target.value)} />
            </div>
            <div className="flex flex-wrap gap-2">
              <Button onClick={() => void saveMaintenanceMode(true)} disabled={maintenanceSaving}>
                Enable maintenance
              </Button>
              <Button variant="outline" onClick={() => void saveMaintenanceMode(false)} disabled={maintenanceSaving}>
                Disable maintenance
              </Button>
            </div>
            <div className="grid gap-4 border-t pt-4 md:grid-cols-2">
              <div className="space-y-2">
                <Label>Window start</Label>
                <Input type="datetime-local" value={scheduleStart} onChange={(event) => setScheduleStart(event.target.value)} />
              </div>
              <div className="space-y-2">
                <Label>Window end</Label>
                <Input type="datetime-local" value={scheduleEnd} onChange={(event) => setScheduleEnd(event.target.value)} />
              </div>
            </div>
            <div className="flex flex-wrap gap-2">
              <Button variant="outline" onClick={() => void saveMaintenanceSchedule()} disabled={scheduleSaving}>
                Save maintenance window
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
                      setMessage('Maintenance schedule cleared.')
                    })
                    .catch((saveError) => setError(saveError instanceof Error ? saveError.message : 'Unable to clear maintenance schedule'))
                }}
                disabled={scheduleSaving}
              >
                Clear window
              </Button>
            </div>
            <p className="text-xs text-muted-foreground">
              Bypass roles: {maintenance?.bypass_roles?.join(', ') || 'parent, co-parent'}
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Compliance settings</CardTitle>
            <CardDescription>Select your state and add custom rules for unusual homeschool requirements.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <Label>State</Label>
              <Select value={stateCode} onValueChange={setStateCode}>
                <SelectTrigger className="w-full md:w-72">
                  <SelectValue placeholder="Choose state" />
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
              Save family state
            </Button>

            <div className="space-y-2 border-t pt-4">
              <Label>Custom rule type</Label>
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
                  <SelectValue placeholder="Choose custom rule type" />
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
              <Label>Rule name</Label>
              <Input
                value={ruleForm.rule_name}
                onChange={(event) => setRuleForm((current) => ({ ...current, rule_name: event.target.value }))}
              />
            </div>
            <div className="space-y-2">
              <Label>Description</Label>
              <Textarea
                value={ruleForm.description}
                onChange={(event) => setRuleForm((current) => ({ ...current, description: event.target.value }))}
              />
            </div>

            <div className="grid gap-4 md:grid-cols-2">
              <div className="space-y-2">
                <Label>Required value</Label>
                <Input
                  type="number"
                  min="0"
                  step="0.01"
                  value={ruleForm.threshold_value}
                  onChange={(event) => setRuleForm((current) => ({ ...current, threshold_value: event.target.value }))}
                />
              </div>
              <div className="space-y-2">
                <Label>Unit</Label>
                <Input
                  value={ruleForm.threshold_unit}
                  onChange={(event) => setRuleForm((current) => ({ ...current, threshold_unit: event.target.value }))}
                />
              </div>
            </div>

            {ruleForm.rule_type === 'subjects_required' ? (
              <div className="space-y-2">
                <Label>Subjects (comma separated)</Label>
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
              Save custom rule
            </Button>
            <p className="text-xs text-muted-foreground">
              New rule type: {selectedRuleType.label}. The dashboard will compare progress against {selectedRuleType.unit}.
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Custom compliance rules</CardTitle>
            <CardDescription>These rules apply in addition to the selected state defaults.</CardDescription>
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
                    Required: {rule.threshold_value} {rule.threshold_unit}
                    {rule.subjects_list?.length ? ` · ${rule.subjects_list.join(', ')}` : ''}
                  </p>
                </div>
              ))
            ) : (
              <p className="text-sm text-muted-foreground">No custom rules yet.</p>
            )}
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Grade scale settings</CardTitle>
          <CardDescription>Manage grade scales and choose the family-wide default GPA mapping.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-4">
            {scales.map((scale, scaleIndex) => (
              <div key={scale.id ?? `scale-${scaleIndex}`} className="space-y-4 rounded-lg border p-4">
                <div className="flex flex-wrap items-center gap-3">
                  <div className="min-w-[220px] flex-1 space-y-2">
                    <Label>Scale name</Label>
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
                    Default scale
                  </label>
                  <Button variant="ghost" size="sm" onClick={() => setScales((current) => current.filter((_, itemIndex) => itemIndex !== scaleIndex))}>
                    <Trash2 className="mr-2 h-3.5 w-3.5" />
                    Remove
                  </Button>
                </div>

                <div className="grid gap-3 md:grid-cols-5">
                  {scale.ranges.map((range, rangeIndex) => (
                    <div key={`${scale.id ?? scaleIndex}-${rangeIndex}`} className="space-y-2 rounded-md border p-3">
                      <Label>Letter</Label>
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
                      <Label>Min</Label>
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
                      <Label>Max</Label>
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
                      <Label>GPA</Label>
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
                  { name: `Scale ${current.length + 1}`, is_default: current.length === 0, ranges: defaultRanges },
                ])
              }
            >
              <Plus className="mr-2 h-4 w-4" />
              Add scale
            </Button>
            <Button onClick={() => void saveGradeScales()} disabled={saving || totalDefaults !== 1}>
              <Save className="mr-2 h-4 w-4" />
              Save settings
            </Button>
          </div>

          <p className="text-xs text-muted-foreground">Exactly one scale must be marked as default. Current default count: {totalDefaults}.</p>
          {message ? <p className="text-sm text-muted-foreground">{message}</p> : null}
          {error ? <p className="text-sm text-destructive">{error}</p> : null}
        </CardContent>
      </Card>
    </div>
  )
}
