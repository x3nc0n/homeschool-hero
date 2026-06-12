import type { CalendarEventType, TermType } from '@/types/api'

export type SchoolYearTemplateId = 'traditional' | 'year_round' | 'calendar_year' | 'custom'
export type HolidayPresetId = 'federal' | 'religious' | 'state'

export type WizardTermDraft = {
  id: string
  name: string
  start_date: string
  end_date: string
}

export type WizardBreakDraft = {
  id: string
  name: string
  start_date: string
  end_date: string
  notes: string
}

export type WizardEventDraft = {
  date: string
  name: string
  event_type: CalendarEventType
  is_instructional_day: boolean
  notes?: string | null
  source: HolidayPresetId | 'custom'
}

export type TemplateDefaults = {
  name: string
  start_date: string
  end_date: string
}

export type SchoolYearTemplateOption = {
  id: SchoolYearTemplateId
  label: string
  description: string
}

export type StateHolidayPreset = {
  stateCode: string
  label: string
  description: string
}

const DAY_IN_MS = 24 * 60 * 60 * 1000

const templateOptions: SchoolYearTemplateOption[] = [
  {
    id: 'traditional',
    label: 'Traditional August–May',
    description: 'A classic homeschool year with a summer break and holidays spread through the fall and spring.',
  },
  {
    id: 'year_round',
    label: 'Year-round',
    description: 'A balanced year that runs through the summer with shorter breaks built in.',
  },
  {
    id: 'calendar_year',
    label: 'January–December',
    description: 'A single calendar-year schedule for families who plan around the calendar year.',
  },
  {
    id: 'custom',
    label: 'Custom dates',
    description: 'Start with smart defaults, then tailor the year for your family.',
  },
]

const stateHolidayPresets: Record<string, StateHolidayPreset> = {
  AK: {
    stateCode: 'AK',
    label: 'Alaska Day',
    description: 'Adds Alaska Day in October as a state-specific closure.',
  },
  CA: {
    stateCode: 'CA',
    label: 'Cesar Chavez Day',
    description: 'Adds Cesar Chavez Day for California-based families.',
  },
  HI: {
    stateCode: 'HI',
    label: 'Prince Kūhiō and Kamehameha Day',
    description: 'Adds two common Hawaii state holidays.',
  },
  LA: {
    stateCode: 'LA',
    label: 'Mardi Gras',
    description: 'Adds Mardi Gras day as a Louisiana-specific closure.',
  },
  MA: {
    stateCode: 'MA',
    label: 'Patriots’ Day',
    description: 'Adds Patriots’ Day in April.',
  },
  ME: {
    stateCode: 'ME',
    label: 'Patriots’ Day',
    description: 'Adds Patriots’ Day in April.',
  },
  NV: {
    stateCode: 'NV',
    label: 'Nevada Day',
    description: 'Adds Nevada Day in October.',
  },
  TX: {
    stateCode: 'TX',
    label: 'San Jacinto Day',
    description: 'Adds San Jacinto Day in April as an optional Texas closure.',
  },
  UT: {
    stateCode: 'UT',
    label: 'Pioneer Day',
    description: 'Adds Pioneer Day in July.',
  },
}

function parseDate(value: string) {
  const [year, month, day] = value.split('-').map(Number)
  return new Date(year, month - 1, day)
}

function formatDate(date: Date) {
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`
}

function addDays(value: string, days: number) {
  const next = parseDate(value)
  next.setDate(next.getDate() + days)
  return formatDate(next)
}

function addDaysToDate(date: Date, days: number) {
  const next = new Date(date)
  next.setDate(next.getDate() + days)
  return next
}

function compareDates(left: string, right: string) {
  return parseDate(left).getTime() - parseDate(right).getTime()
}

function differenceInDaysInclusive(startDate: string, endDate: string) {
  const diff = parseDate(endDate).getTime() - parseDate(startDate).getTime()
  return Math.floor(diff / DAY_IN_MS) + 1
}

function isDateWithinRange(date: string, startDate: string, endDate: string) {
  return compareDates(date, startDate) >= 0 && compareDates(date, endDate) <= 0
}

function enumerateDates(startDate: string, endDate: string) {
  const dates: string[] = []
  const totalDays = differenceInDaysInclusive(startDate, endDate)
  for (let dayIndex = 0; dayIndex < totalDays; dayIndex += 1) {
    dates.push(addDays(startDate, dayIndex))
  }
  return dates
}

function nthWeekdayOfMonth(year: number, monthIndex: number, weekday: number, occurrence: number) {
  const firstDay = new Date(year, monthIndex, 1)
  const offset = (7 + weekday - firstDay.getDay()) % 7
  return new Date(year, monthIndex, 1 + offset + (occurrence - 1) * 7)
}

function lastWeekdayOfMonth(year: number, monthIndex: number, weekday: number) {
  const lastDay = new Date(year, monthIndex + 1, 0)
  const offset = (7 + lastDay.getDay() - weekday) % 7
  return new Date(year, monthIndex + 1, 0 - offset)
}

function observedFixedHoliday(year: number, monthIndex: number, dayOfMonth: number) {
  const holiday = new Date(year, monthIndex, dayOfMonth)
  if (holiday.getDay() === 0) {
    return addDaysToDate(holiday, 1)
  }
  if (holiday.getDay() === 6) {
    return addDaysToDate(holiday, -1)
  }
  return holiday
}

function calculateEaster(year: number) {
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
  return new Date(year, month - 1, day)
}

function currentPlanningYear(referenceDate: Date, startMonthIndex: number) {
  return referenceDate.getMonth() >= startMonthIndex - 3 ? referenceDate.getFullYear() : referenceDate.getFullYear() - 1
}

export function buildSchoolYearName(startDate: string, endDate: string) {
  const startYear = parseDate(startDate).getFullYear()
  const endYear = parseDate(endDate).getFullYear()
  return startYear === endYear ? `${startYear}` : `${startYear}-${endYear}`
}

export function getTemplateOptions() {
  return templateOptions
}

export function getStateHolidayPreset(stateCode?: string | null) {
  if (!stateCode) return null
  return stateHolidayPresets[stateCode.toUpperCase()] ?? null
}

export function getTemplateDefaults(templateId: SchoolYearTemplateId, referenceDate = new Date()): TemplateDefaults {
  if (templateId === 'calendar_year') {
    const year = referenceDate.getFullYear()
    const start_date = `${year}-01-01`
    const end_date = `${year}-12-31`
    return {
      name: buildSchoolYearName(start_date, end_date),
      start_date,
      end_date,
    }
  }

  if (templateId === 'year_round') {
    const year = currentPlanningYear(referenceDate, 6)
    const start_date = `${year}-07-01`
    const end_date = `${year + 1}-06-30`
    return {
      name: buildSchoolYearName(start_date, end_date),
      start_date,
      end_date,
    }
  }

  const year = currentPlanningYear(referenceDate, 7)
  const start_date = `${year}-08-15`
  const end_date = `${year + 1}-05-31`
  return {
    name: buildSchoolYearName(start_date, end_date),
    start_date,
    end_date,
  }
}

export function createDefaultCustomTerms(startDate: string, endDate: string): WizardTermDraft[] {
  return [{ id: 'custom-term-1', name: 'Term 1', start_date: startDate, end_date: endDate }]
}

function buildGeneratedTerm(name: string, startDate: string, endDate: string, termType: TermType, index: number) {
  return {
    id: `${termType}-${index + 1}`,
    name,
    start_date: startDate,
    end_date: endDate,
    term_type: termType,
  }
}

export function buildGeneratedTerms(startDate: string, endDate: string, termType: TermType, customTerms: WizardTermDraft[]) {
  if (!startDate || !endDate || compareDates(startDate, endDate) > 0) {
    return []
  }

  if (termType === 'custom') {
    return customTerms
      .filter((term) => term.name.trim() && term.start_date && term.end_date)
      .map((term, index) => buildGeneratedTerm(term.name.trim(), term.start_date, term.end_date, 'custom', index))
  }

  const segments = termType === 'semester' ? 2 : termType === 'quarter' ? 4 : 3
  const totalDays = differenceInDaysInclusive(startDate, endDate)
  const labelPrefix = termType === 'semester' ? 'Semester' : termType === 'quarter' ? 'Quarter' : 'Trimester'

  return Array.from({ length: segments }, (_, index) => {
    const startOffset = Math.floor((totalDays * index) / segments)
    const endOffset = Math.floor((totalDays * (index + 1)) / segments) - 1
    const segmentStart = addDays(startDate, startOffset)
    const segmentEnd = index === segments - 1 ? endDate : addDays(startDate, endOffset)
    return buildGeneratedTerm(`${labelPrefix} ${index + 1}`, segmentStart, segmentEnd, termType, index)
  })
}

function createEvent(date: Date, name: string, source: HolidayPresetId): WizardEventDraft {
  return {
    date: formatDate(date),
    name,
    event_type: 'holiday',
    is_instructional_day: false,
    source,
  }
}

function federalHolidayEventsForYear(year: number) {
  return [
    createEvent(observedFixedHoliday(year, 0, 1), 'New Year’s Day', 'federal'),
    createEvent(nthWeekdayOfMonth(year, 0, 1, 3), 'Martin Luther King Jr. Day', 'federal'),
    createEvent(nthWeekdayOfMonth(year, 1, 1, 3), 'Presidents Day', 'federal'),
    createEvent(lastWeekdayOfMonth(year, 4, 1), 'Memorial Day', 'federal'),
    createEvent(observedFixedHoliday(year, 5, 19), 'Juneteenth', 'federal'),
    createEvent(observedFixedHoliday(year, 6, 4), 'Independence Day', 'federal'),
    createEvent(nthWeekdayOfMonth(year, 8, 1, 1), 'Labor Day', 'federal'),
    createEvent(nthWeekdayOfMonth(year, 9, 1, 2), 'Indigenous Peoples’ Day', 'federal'),
    createEvent(observedFixedHoliday(year, 10, 11), 'Veterans Day', 'federal'),
    createEvent(nthWeekdayOfMonth(year, 10, 4, 4), 'Thanksgiving Day', 'federal'),
    createEvent(observedFixedHoliday(year, 11, 25), 'Christmas Day', 'federal'),
  ]
}

function religiousHolidayEventsForYear(year: number) {
  const easter = calculateEaster(year)
  const goodFriday = addDaysToDate(easter, -2)
  const easterMonday = addDaysToDate(easter, 1)
  const christmasBreakStart = `${year}-12-24`
  const christmasBreakEnd = `${year + 1}-01-01`

  return [
    createEvent(goodFriday, 'Good Friday', 'religious'),
    createEvent(easterMonday, 'Easter Monday', 'religious'),
    ...enumerateDates(christmasBreakStart, christmasBreakEnd).map((date) => ({
      date,
      name: 'Christmas Break',
      event_type: 'holiday' as CalendarEventType,
      is_instructional_day: false,
      notes: 'Holiday preset',
      source: 'religious' as const,
    })),
  ]
}

function stateHolidayEventsForYear(year: number, stateCode: string) {
  const normalized = stateCode.toUpperCase()
  switch (normalized) {
    case 'AK':
      return [createEvent(observedFixedHoliday(year, 9, 18), 'Alaska Day', 'state')]
    case 'CA':
      return [createEvent(observedFixedHoliday(year, 2, 31), 'Cesar Chavez Day', 'state')]
    case 'HI':
      return [
        createEvent(observedFixedHoliday(year, 2, 26), 'Prince Kūhiō Day', 'state'),
        createEvent(observedFixedHoliday(year, 5, 11), 'Kamehameha Day', 'state'),
      ]
    case 'LA': {
      const easter = calculateEaster(year)
      return [createEvent(addDaysToDate(easter, -47), 'Mardi Gras', 'state')]
    }
    case 'MA':
    case 'ME':
      return [createEvent(nthWeekdayOfMonth(year, 3, 1, 3), 'Patriots’ Day', 'state')]
    case 'NV':
      return [createEvent(lastWeekdayOfMonth(year, 9, 5), 'Nevada Day', 'state')]
    case 'TX':
      return [createEvent(observedFixedHoliday(year, 3, 21), 'San Jacinto Day', 'state')]
    case 'UT':
      return [createEvent(observedFixedHoliday(year, 6, 24), 'Pioneer Day', 'state')]
    default:
      return []
  }
}

function filterEventsToRange(events: WizardEventDraft[], startDate: string, endDate: string) {
  const deduped = new Map<string, WizardEventDraft>()
  for (const event of events) {
    if (!isDateWithinRange(event.date, startDate, endDate)) continue
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

export function buildPresetEvents({
  startDate,
  endDate,
  includeFederal,
  includeReligious,
  includeState,
  stateCode,
}: {
  startDate: string
  endDate: string
  includeFederal: boolean
  includeReligious: boolean
  includeState: boolean
  stateCode?: string | null
}) {
  if (!startDate || !endDate || compareDates(startDate, endDate) > 0) {
    return []
  }

  const startYear = parseDate(startDate).getFullYear() - 1
  const endYear = parseDate(endDate).getFullYear() + 1
  const events: WizardEventDraft[] = []

  for (let year = startYear; year <= endYear; year += 1) {
    if (includeFederal) {
      events.push(...federalHolidayEventsForYear(year))
    }
    if (includeReligious) {
      events.push(...religiousHolidayEventsForYear(year))
    }
    if (includeState && stateCode) {
      events.push(...stateHolidayEventsForYear(year, stateCode))
    }
  }

  return filterEventsToRange(events, startDate, endDate)
}

export function expandCustomBreaks(customBreaks: WizardBreakDraft[]) {
  return customBreaks
    .filter((customBreak) => customBreak.name.trim() && customBreak.start_date && customBreak.end_date)
    .flatMap((customBreak) =>
      enumerateDates(customBreak.start_date, customBreak.end_date).map((date) => ({
        date,
        name: customBreak.name.trim(),
        event_type: 'closure' as CalendarEventType,
        is_instructional_day: false,
        notes: customBreak.notes.trim() || null,
        source: 'custom' as const,
      })),
    )
}

export function buildInstructionalDayPreview(startDate: string, endDate: string, events: WizardEventDraft[]) {
  if (!startDate || !endDate || compareDates(startDate, endDate) > 0) {
    return {
      weekdayDays: 0,
      nonInstructionalOverrides: 0,
      instructionalOverrides: 0,
      instructionalDays: 0,
    }
  }

  let weekdayDays = 0
  for (const date of enumerateDates(startDate, endDate)) {
    const current = parseDate(date)
    if (current.getDay() !== 0 && current.getDay() !== 6) {
      weekdayDays += 1
    }
  }

  const nonInstructional = new Set<string>()
  let instructionalOverrides = 0
  for (const event of events) {
    const current = parseDate(event.date)
    const isWeekday = current.getDay() !== 0 && current.getDay() !== 6
    if (event.is_instructional_day) {
      if (!isWeekday) {
        instructionalOverrides += 1
      }
      continue
    }
    if (isWeekday) {
      nonInstructional.add(event.date)
    }
  }

  return {
    weekdayDays,
    nonInstructionalOverrides: nonInstructional.size,
    instructionalOverrides,
    instructionalDays: Math.max(weekdayDays - nonInstructional.size + instructionalOverrides, 0),
  }
}

export function validateSchoolYearRange(startDate: string, endDate: string) {
  if (!startDate || !endDate) {
    return 'Choose a start and end date before moving to the next step.'
  }
  if (compareDates(startDate, endDate) > 0) {
    return 'The school year end date needs to be after the start date.'
  }
  return ''
}

export function validateCustomTerms(startDate: string, endDate: string, customTerms: WizardTermDraft[]) {
  const yearError = validateSchoolYearRange(startDate, endDate)
  if (yearError) return yearError
  const filtered = customTerms.filter((term) => term.name.trim() || term.start_date || term.end_date)
  if (!filtered.length) {
    return 'Add at least one custom term.'
  }

  const sorted = filtered
    .map((term) => ({ ...term, name: term.name.trim() }))
    .sort((left, right) => compareDates(left.start_date, right.start_date))

  for (const term of sorted) {
    if (!term.name || !term.start_date || !term.end_date) {
      return 'Every custom term needs a name, start date, and end date.'
    }
    if (compareDates(term.start_date, term.end_date) > 0) {
      return `${term.name} ends before it starts.`
    }
    if (!isDateWithinRange(term.start_date, startDate, endDate) || !isDateWithinRange(term.end_date, startDate, endDate)) {
      return `${term.name} needs to stay inside the school year.`
    }
  }

  for (let index = 1; index < sorted.length; index += 1) {
    if (compareDates(sorted[index].start_date, sorted[index - 1].end_date) <= 0) {
      return `${sorted[index - 1].name} overlaps with ${sorted[index].name}.`
    }
  }

  return ''
}

export function validateCustomBreaks(startDate: string, endDate: string, customBreaks: WizardBreakDraft[]) {
  const yearError = validateSchoolYearRange(startDate, endDate)
  if (yearError) return yearError

  for (const customBreak of customBreaks) {
    const name = customBreak.name.trim()
    if (!name && !customBreak.start_date && !customBreak.end_date && !customBreak.notes.trim()) continue
    if (!name || !customBreak.start_date || !customBreak.end_date) {
      return 'Each custom break needs a name plus a start and end date.'
    }
    if (compareDates(customBreak.start_date, customBreak.end_date) > 0) {
      return `${name} ends before it starts.`
    }
    if (!isDateWithinRange(customBreak.start_date, startDate, endDate) || !isDateWithinRange(customBreak.end_date, startDate, endDate)) {
      return `${name} needs to stay inside the school year.`
    }
  }

  return ''
}
