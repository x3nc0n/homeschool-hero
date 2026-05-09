import { ChevronRight } from 'lucide-react'
import { Link, useLocation } from 'react-router-dom'
import { cn } from '@/lib/utils'

type Crumb = {
  label: string
  to?: string
}

const labelMap: Record<string, string> = {
  students: 'Students',
  assignments: 'Assignments',
  grades: 'Grade Book',
  calendar: 'Calendar',
  curriculum: 'Curriculum',
  'lesson-plans': 'Lesson Plans',
  review: 'Review Queue',
  notifications: 'Notifications',
  'report-cards': 'Report Cards',
  transcripts: 'Transcripts',
  compliance: 'Compliance',
  'compliance-reports': 'Compliance Reports',
  portfolio: 'Portfolio',
  imports: 'Imports',
  exports: 'Exports',
  resources: 'Resources',
  invitations: 'Invitations',
  audit: 'Audit Log',
  search: 'Search',
  upload: 'Uploads',
  planner: 'Planner',
  settings: 'Settings',
  family: 'Family',
  backups: 'Backups',
  status: 'System Status',
  restore: 'Restore',
}

function buildCrumbs(pathname: string): Crumb[] {
  const segments = pathname.split('/').filter(Boolean)
  const crumbs: Crumb[] = [{ label: 'Dashboard', to: '/' }]

  if (!segments.length || (segments.length === 1 && segments[0] === 'dashboard')) {
    return [{ label: 'Dashboard' }]
  }

  let currentPath = ''
  segments.forEach((segment, index) => {
    currentPath += `/${segment}`
    const isNumeric = /^\d+$/.test(segment)
    const prevSegment = segments[index - 1]
    let label = labelMap[segment] || segment.replace(/-/g, ' ')

    if (isNumeric && prevSegment === 'students') {
      label = 'Student Profile'
    } else if (isNumeric && prevSegment === 'review') {
      label = 'Review Detail'
    } else if (isNumeric) {
      label = 'Detail'
    }

    crumbs.push({
      label: label
        .split(' ')
        .map((part) => (part ? part[0].toUpperCase() + part.slice(1) : part))
        .join(' '),
      to: index === segments.length - 1 ? undefined : currentPath,
    })
  })

  return crumbs
}

export function Breadcrumbs() {
  const location = useLocation()
  const crumbs = buildCrumbs(location.pathname)

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
