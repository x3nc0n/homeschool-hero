import { ChevronRight } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { Link, useLocation } from 'react-router-dom'
import { cn } from '@/lib/utils'

type Crumb = {
  label: string
  to?: string
}

const labelMap: Record<string, string> = {
  students: 'students',
  assignments: 'assignments',
  grades: 'grades',
  calendar: 'calendar',
  curriculum: 'curriculum',
  'lesson-plans': 'lesson-plans',
  review: 'review',
  notifications: 'notifications',
  'report-cards': 'report-cards',
  transcripts: 'transcripts',
  compliance: 'compliance',
  'compliance-reports': 'compliance-reports',
  portfolio: 'portfolio',
  imports: 'imports',
  exports: 'exports',
  resources: 'resources',
  invitations: 'invitations',
  audit: 'audit',
  search: 'search',
  upload: 'upload',
  planner: 'planner',
  settings: 'settings',
  family: 'family',
  backups: 'backups',
  status: 'status',
  restore: 'restore',
}

function buildCrumbs(pathname: string, t: (key: string) => string): Crumb[] {
  const segments = pathname.split('/').filter(Boolean)
  const crumbs: Crumb[] = [{ label: t('breadcrumbs.dashboard'), to: '/' }]

  if (!segments.length || (segments.length === 1 && segments[0] === 'dashboard')) {
    return [{ label: t('breadcrumbs.dashboard') }]
  }

  let currentPath = ''
  segments.forEach((segment, index) => {
    currentPath += `/${segment}`
    const isNumeric = /^\d+$/.test(segment)
    const prevSegment = segments[index - 1]
    let label = labelMap[segment] ? t(`breadcrumbs.${labelMap[segment]}`) : segment.replace(/-/g, ' ')

    if (isNumeric && prevSegment === 'students') {
      label = t('breadcrumbs.studentProfile')
    } else if (isNumeric && prevSegment === 'review') {
      label = t('breadcrumbs.reviewDetail')
    } else if (isNumeric) {
      label = t('breadcrumbs.detail')
    }

    crumbs.push({
      label,
      to: index === segments.length - 1 ? undefined : currentPath,
    })
  })

  return crumbs
}

export function Breadcrumbs() {
  const location = useLocation()
  const { t } = useTranslation('common')
  const crumbs = buildCrumbs(location.pathname, t)

  return (
    <nav aria-label="Breadcrumb" className="flex flex-wrap items-center gap-1 text-xs text-muted-foreground">
      {crumbs.map((crumb, index) => {
        const isLast = index === crumbs.length - 1
        return (
          <span key={`${crumb.label}-${index}`} className="flex items-center gap-1">
            {crumb.to && !isLast ? (
              <Link className="transition hover:text-foreground" to={crumb.to}>
                {crumb.label}
              </Link>
            ) : (
              <span className={cn(isLast && 'font-medium text-foreground')}>{crumb.label}</span>
            )}
            {!isLast ? <ChevronRight className="h-3 w-3" /> : null}
          </span>
        )
      })}
    </nav>
  )
}
