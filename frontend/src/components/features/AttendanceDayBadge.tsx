import { useTranslation } from 'react-i18next'
import { Badge } from '@/components/ui/badge'

export function AttendanceDayBadge({ isInstructionalDay }: { isInstructionalDay: boolean | null }) {
  const { t } = useTranslation()
  const label =
    isInstructionalDay === true
      ? t('attendance.calendar.instructional')
      : isInstructionalDay === false
        ? t('attendance.calendar.nonInstructional')
        : t('attendance.calendar.notRecorded')

  return <Badge variant={isInstructionalDay === true ? 'secondary' : 'outline'}>{label}</Badge>
}
