export type HolidayCategory = 'federal' | 'religious'

export interface HolidayOccurrence {
  date: string
  name: string
}

export interface HolidayPreset {
  key: string
  name: string
  category: HolidayCategory
  defaultSelected: boolean
  compute: (year: number) => HolidayOccurrence[]
}

export interface ComputedHolidayPreset extends HolidayPreset {
  occurrences: HolidayOccurrence[]
  dateLabel: string
}

const DAY_IN_MS = 24 * 60 * 60 * 1000

function createUtcDate(year: number, month: number, day: number) {
  return new Date(Date.UTC(year, month - 1, day))
}

function addUtcDays(date: Date, days: number) {
  return new Date(date.getTime() + days * DAY_IN_MS)
}

function toIsoDate(date: Date) {
  return date.toISOString().slice(0, 10)
}

function formatDateLabel(date: string) {
  return new Date(`${date}T00:00:00Z`).toLocaleDateString(undefined, {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
    timeZone: 'UTC',
  })
}

function getNthWeekdayOfMonth(year: number, month: number, weekday: number, occurrence: number) {
  const firstDay = createUtcDate(year, month, 1)
  const offset = (7 + weekday - firstDay.getUTCDay()) % 7
  return createUtcDate(year, month, 1 + offset + (occurrence - 1) * 7)
}

function getLastWeekdayOfMonth(year: number, month: number, weekday: number) {
  const lastDay = createUtcDate(year, month + 1, 0)
  const offset = (7 + lastDay.getUTCDay() - weekday) % 7
  return createUtcDate(year, month, lastDay.getUTCDate() - offset)
}

// Anonymous Gregorian algorithm.
function getEasterSunday(year: number) {
  const a = year % 19
  const b = Math.floor(year / 100)
  const c = year % 100
  const d = Math.floor(b / 4)
  const e = b % 4
  const f = Math.floor((b + 8) / 25)
  const g = Math.floor((b - f + 1) / 3)
  const h = (19 * a + b - d - g + 15) % 30
  const i = Math.floor(c / 4)
  const k = c % 4
  const l = (32 + 2 * e + 2 * i - h - k) % 7
  const m = Math.floor((a + 11 * h + 22 * l) / 451)
  const month = Math.floor((h + l - 7 * m + 114) / 31)
  const day = ((h + l - 7 * m + 114) % 31) + 1
  return createUtcDate(year, month, day)
}

function getCalendarParts(date: Date, calendarLocale: string) {
  try {
    const formatter = new Intl.DateTimeFormat(calendarLocale, {
      day: 'numeric',
      month: 'long',
      year: 'numeric',
      timeZone: 'UTC',
    })

    const month = formatter.formatToParts(date).find((part) => part.type === 'month')?.value
    const day = Number(formatter.formatToParts(date).find((part) => part.type === 'day')?.value)

    return { month, day }
  } catch {
    return { month: undefined, day: Number.NaN }
  }
}

function findCalendarDate(
  year: number,
  calendarLocale: string,
  targetMonth: string,
  targetDay: number,
  startMonth = 1,
  startDay = 1,
  endMonth = 12,
  endDay = 31,
) {
  const start = createUtcDate(year, startMonth, startDay)
  const end = createUtcDate(year, endMonth, endDay)

  for (let current = start; current <= end; current = addUtcDays(current, 1)) {
    const parts = getCalendarParts(current, calendarLocale)
    if (parts.month === targetMonth && parts.day === targetDay) {
      return toIsoDate(current)
    }
  }

  return ''
}

function buildRangeOccurrences(name: string, start: Date, end: Date) {
  const occurrences: HolidayOccurrence[] = []

  for (let current = start; current <= end; current = addUtcDays(current, 1)) {
    occurrences.push({
      date: toIsoDate(current),
      name,
    })
  }

  return occurrences
}

function formatOccurrencesLabel(occurrences: HolidayOccurrence[]) {
  if (!occurrences.length) return ''
  if (occurrences.length === 1) return formatDateLabel(occurrences[0].date)

  const sorted = [...occurrences].sort((left, right) => left.date.localeCompare(right.date))
  const contiguous = sorted.every((occurrence, index) => {
    if (!index) return true
    const previous = new Date(`${sorted[index - 1].date}T00:00:00Z`).getTime()
    const current = new Date(`${occurrence.date}T00:00:00Z`).getTime()
    return current - previous === DAY_IN_MS
  })

  if (contiguous) {
    return `${formatDateLabel(sorted[0].date)} – ${formatDateLabel(sorted[sorted.length - 1].date)}`
  }

  return sorted.map((occurrence) => formatDateLabel(occurrence.date)).join(', ')
}

export const holidayPresets: HolidayPreset[] = [
  {
    key: 'new-years-day',
    name: "New Year's Day",
    category: 'federal',
    defaultSelected: true,
    compute: (year) => [{ date: toIsoDate(createUtcDate(year, 1, 1)), name: "New Year's Day" }],
  },
  {
    key: 'mlk-day',
    name: 'Martin Luther King Jr. Day',
    category: 'federal',
    defaultSelected: true,
    compute: (year) => [{ date: toIsoDate(getNthWeekdayOfMonth(year, 1, 1, 3)), name: 'Martin Luther King Jr. Day' }],
  },
  {
    key: 'presidents-day',
    name: "Presidents' Day",
    category: 'federal',
    defaultSelected: true,
    compute: (year) => [{ date: toIsoDate(getNthWeekdayOfMonth(year, 2, 1, 3)), name: "Presidents' Day" }],
  },
  {
    key: 'memorial-day',
    name: 'Memorial Day',
    category: 'federal',
    defaultSelected: true,
    compute: (year) => [{ date: toIsoDate(getLastWeekdayOfMonth(year, 5, 1)), name: 'Memorial Day' }],
  },
  {
    key: 'independence-day',
    name: 'Independence Day',
    category: 'federal',
    defaultSelected: true,
    compute: (year) => [{ date: toIsoDate(createUtcDate(year, 7, 4)), name: 'Independence Day' }],
  },
  {
    key: 'labor-day',
    name: 'Labor Day',
    category: 'federal',
    defaultSelected: true,
    compute: (year) => [{ date: toIsoDate(getNthWeekdayOfMonth(year, 9, 1, 1)), name: 'Labor Day' }],
  },
  {
    key: 'columbus-day',
    name: "Columbus / Indigenous Peoples' Day",
    category: 'federal',
    defaultSelected: true,
    compute: (year) => [{ date: toIsoDate(getNthWeekdayOfMonth(year, 10, 1, 2)), name: "Columbus / Indigenous Peoples' Day" }],
  },
  {
    key: 'veterans-day',
    name: 'Veterans Day',
    category: 'federal',
    defaultSelected: true,
    compute: (year) => [{ date: toIsoDate(createUtcDate(year, 11, 11)), name: 'Veterans Day' }],
  },
  {
    key: 'thanksgiving-break',
    name: 'Thanksgiving + Day After',
    category: 'federal',
    defaultSelected: true,
    compute: (year) => {
      const thanksgiving = getNthWeekdayOfMonth(year, 11, 4, 4)
      return [
        { date: toIsoDate(thanksgiving), name: 'Thanksgiving Day' },
        { date: toIsoDate(addUtcDays(thanksgiving, 1)), name: 'Day After Thanksgiving' },
      ]
    },
  },
  {
    key: 'christmas-day',
    name: 'Christmas Day',
    category: 'federal',
    defaultSelected: true,
    compute: (year) => [{ date: toIsoDate(createUtcDate(year, 12, 25)), name: 'Christmas Day' }],
  },
  {
    key: 'christmas-break',
    name: 'Christmas Break',
    category: 'religious',
    defaultSelected: false,
    compute: (year) => buildRangeOccurrences('Christmas Break', createUtcDate(year, 12, 23), createUtcDate(year + 1, 1, 2)),
  },
  {
    key: 'good-friday',
    name: 'Good Friday',
    category: 'religious',
    defaultSelected: false,
    compute: (year) => [{ date: toIsoDate(addUtcDays(getEasterSunday(year), -2)), name: 'Good Friday' }],
  },
  {
    key: 'easter-monday',
    name: 'Easter Monday',
    category: 'religious',
    defaultSelected: false,
    compute: (year) => [{ date: toIsoDate(addUtcDays(getEasterSunday(year), 1)), name: 'Easter Monday' }],
  },
  {
    key: 'rosh-hashanah',
    name: 'Rosh Hashanah',
    category: 'religious',
    defaultSelected: false,
    compute: (year) => {
      const date = findCalendarDate(year, 'en-u-ca-hebrew', 'Tishri', 1, 8, 15, 10, 31)
      return date ? [{ date, name: 'Rosh Hashanah' }] : []
    },
  },
  {
    key: 'yom-kippur',
    name: 'Yom Kippur',
    category: 'religious',
    defaultSelected: false,
    compute: (year) => {
      const date = findCalendarDate(year, 'en-u-ca-hebrew', 'Tishri', 10, 8, 15, 10, 31)
      return date ? [{ date, name: 'Yom Kippur' }] : []
    },
  },
  {
    key: 'eid-al-fitr',
    name: 'Eid al-Fitr',
    category: 'religious',
    defaultSelected: false,
    compute: (year) => {
      const date = findCalendarDate(year, 'en-u-ca-islamic-umalqura', 'Shawwal', 1)
      return date ? [{ date, name: 'Eid al-Fitr' }] : []
    },
  },
]

export function getHolidayPresetsForRange(startDate: string, endDate: string) {
  if (!startDate || !endDate || startDate > endDate) {
    return [] as ComputedHolidayPreset[]
  }

  const startYear = Number(startDate.slice(0, 4))
  const endYear = Number(endDate.slice(0, 4))

  return holidayPresets
    .map((preset) => {
      const occurrences = Array.from({ length: endYear - startYear + 1 }, (_, index) => startYear + index)
        .flatMap((year) => preset.compute(year))
        .filter((occurrence) => occurrence.date >= startDate && occurrence.date <= endDate)
        .sort((left, right) => left.date.localeCompare(right.date) || left.name.localeCompare(right.name))

      const dedupedOccurrences = occurrences.filter(
        (occurrence, index) => occurrences.findIndex((candidate) => candidate.date === occurrence.date && candidate.name === occurrence.name) === index,
      )

      return {
        ...preset,
        occurrences: dedupedOccurrences,
        dateLabel: formatOccurrencesLabel(dedupedOccurrences),
      }
    })
    .filter((preset) => preset.occurrences.length > 0)
}
