import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { AlertTriangle, CheckCircle2, ShieldAlert } from 'lucide-react'
import { api } from '@/lib/api'
import type { ComplianceDashboard, ComplianceState, ComplianceStatus, RequiredComplianceReport, SchoolYear } from '@/types/api'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { LoadingState } from '@/components/common/LoadingState'
import { ErrorState } from '@/components/common/ErrorState'
import { EmptyState } from '@/components/common/EmptyState'

const statusConfig: Record<
  ComplianceState,
  { label: string; icon: typeof CheckCircle2; className: string; tone: 'secondary' | 'outline' | 'destructive' }
> = {
  compliant: {
    label: 'Compliant',
    icon: CheckCircle2,
    className: 'text-emerald-700 border-emerald-200 bg-emerald-50',
    tone: 'secondary',
  },
  warning: {
    label: 'Warning',
    icon: AlertTriangle,
    className: 'text-amber-700 border-amber-200 bg-amber-50',
    tone: 'outline',
  },
  non_compliant: {
    label: 'Non-compliant',
    icon: ShieldAlert,
    className: 'text-destructive',
    tone: 'destructive',
  },
}

function formatRequirement(status: ComplianceStatus) {
  const unit = status.rule.threshold_unit.replace('_', ' ')
  return `${status.current_value} / ${status.required_value} ${unit}`
}

export function CompliancePage() {
  const [dashboard, setDashboard] = useState<ComplianceDashboard | null>(null)
  const [schoolYears, setSchoolYears] = useState<SchoolYear[]>([])
  const [requiredReports, setRequiredReports] = useState<RequiredComplianceReport[]>([])
  const [selectedYearId, setSelectedYearId] = useState<number | undefined>(undefined)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const [schoolYearData, dashboardData] = await Promise.all([
        api.listSchoolYears(),
        api.getComplianceDashboard(selectedYearId),
      ])
      const resolvedYearId = selectedYearId || dashboardData.school_year_id || schoolYearData.find((schoolYear) => schoolYear.is_active)?.id
      const requiredData = await api.listRequiredComplianceReports({
        state: dashboardData.state_code,
        school_year_id: resolvedYearId,
      })
      setSchoolYears(schoolYearData)
      setDashboard(dashboardData)
      setRequiredReports(requiredData.items)
      if (!selectedYearId) {
        setSelectedYearId(dashboardData.school_year_id ?? schoolYearData.find((schoolYear) => schoolYear.is_active)?.id)
      }
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : 'Unable to load compliance dashboard')
    } finally {
      setLoading(false)
    }
  }, [selectedYearId])

  useEffect(() => {
    void load()
  }, [load])

  const alertItems = useMemo(
    () =>
      (dashboard?.students ?? []).flatMap((studentRow) =>
        studentRow.statuses
          .filter((status) => status.status !== 'compliant')
          .map((status) => ({ student: studentRow.student.name, status })),
      ),
    [dashboard],
  )
  const outstandingReports = useMemo(
    () => requiredReports.reduce((total, item) => total + item.outstanding_count, 0),
    [requiredReports],
  )

  if (loading) return <LoadingState message="Loading compliance dashboard…" />
  if (error) return <ErrorState message={error} onRetry={() => void load()} />

  if (!dashboard?.students.length) {
    return (
      <EmptyState
        title="No compliance data yet"
        description="Create a school year and add students to start tracking state requirements."
      />
    )
  }

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
          <div>
            <CardTitle>Compliance dashboard</CardTitle>
            <CardDescription>
              State {dashboard.state_code} · Checked {new Date(dashboard.checked_at).toLocaleString()}
            </CardDescription>
          </div>
          <div className="flex flex-wrap gap-2">
            {schoolYears.map((schoolYear) => (
              <Button
                key={schoolYear.id}
                variant={schoolYear.id === selectedYearId ? 'secondary' : 'outline'}
                size="sm"
                onClick={() => setSelectedYearId(schoolYear.id)}
              >
                {schoolYear.name}
              </Button>
            ))}
          </div>
        </CardHeader>
      </Card>

      <Card>
        <CardHeader className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
          <div>
            <CardTitle>Compliance reporting workspace</CardTitle>
            <CardDescription>
              {requiredReports.length - outstandingReports} report requirements complete · {outstandingReports} still outstanding
            </CardDescription>
          </div>
          <Button asChild variant="outline">
            <Link to="/compliance-reports">Open reports</Link>
          </Button>
        </CardHeader>
        <CardContent className="grid gap-3 md:grid-cols-3">
          {requiredReports.map((item) => (
            <div key={item.report_type} className="rounded-md border p-3">
              <p className="font-medium">{item.label}</p>
              <p className="mt-1 text-sm text-muted-foreground">{item.description}</p>
              <p className="mt-2 text-xs text-muted-foreground">
                {item.completed_count}/{item.required_count} complete
              </p>
            </div>
          ))}
        </CardContent>
      </Card>

      {alertItems.length ? (
        <Card>
          <CardHeader>
            <CardTitle>Alerts</CardTitle>
            <CardDescription>Rules that need attention before the school year closes.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-2">
            {alertItems.map(({ student, status }) => (
              <div key={`${student}-${status.id}`} className="rounded-md border p-3">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <p className="font-medium">
                    {student} · {status.rule.rule_name}
                  </p>
                  <Badge
                    variant={statusConfig[status.status].tone}
                    className={status.status === 'warning' ? statusConfig.warning.className : undefined}
                  >
                    {statusConfig[status.status].label}
                  </Badge>
                </div>
                <p className="mt-1 text-sm text-muted-foreground">{status.notes || status.rule.description}</p>
              </div>
            ))}
          </CardContent>
        </Card>
      ) : null}

      <div className="grid gap-4 xl:grid-cols-2">
        {dashboard.students.map((studentRow) => (
          <Card key={studentRow.student.id}>
            <CardHeader>
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div>
                  <CardTitle>{studentRow.student.name}</CardTitle>
                  <CardDescription>Traffic-light view by state rule.</CardDescription>
                </div>
                <div className="flex gap-2">
                  <Badge variant="secondary">{studentRow.summary_counts.compliant || 0} compliant</Badge>
                  <Badge variant="outline" className="text-amber-700 border-amber-200 bg-amber-50">
                    {studentRow.summary_counts.warning || 0} warnings
                  </Badge>
                  <Badge variant="destructive">{studentRow.summary_counts.non_compliant || 0} non-compliant</Badge>
                </div>
              </div>
            </CardHeader>
            <CardContent className="space-y-3">
              {studentRow.statuses.map((status) => {
                const config = statusConfig[status.status]
                const Icon = config.icon
                return (
                  <div key={status.id} className="rounded-lg border p-3">
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div className="space-y-1">
                        <div className="flex items-center gap-2">
                          <Icon className="h-4 w-4" />
                          <p className="font-medium">{status.rule.rule_name}</p>
                        </div>
                        <p className="text-sm text-muted-foreground">{status.rule.description}</p>
                        <p className="text-xs text-muted-foreground">{formatRequirement(status)}</p>
                      </div>
                      <Badge variant={config.tone} className={status.status === 'warning' ? config.className : undefined}>
                        {config.label}
                      </Badge>
                    </div>
                    {status.rule.subjects_list?.length ? (
                      <p className="mt-2 text-xs text-muted-foreground">
                        Required subjects: {status.rule.subjects_list.join(', ')}
                      </p>
                    ) : null}
                    {status.notes ? <p className="mt-2 text-sm text-muted-foreground">{status.notes}</p> : null}
                  </div>
                )
              })}
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  )
}
