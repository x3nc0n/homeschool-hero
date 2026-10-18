import { useRef, useState } from 'react'
import { Download, Loader2, Upload } from 'lucide-react'
import { api } from '@/lib/api'
import type { SchoolYear, Student } from '@/types/api'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'

type Props = {
  schoolYears: SchoolYear[]
  students: Student[]
  schoolYearId: string
  weekStart: string
  studentId: string
  grade: string
  text: string
  file: File | null
  inputMode: 'paste' | 'file'
  busy: boolean
  onSchoolYear: (value: string) => void
  onWeek: (value: string) => void
  onStudent: (value: string) => void
  onGrade: (value: string) => void
  onText: (value: string) => void
  onFile: (file: File | undefined) => void
  onInputMode: (mode: 'paste' | 'file') => void
  onAnalyze: () => void
  onError: (message: string) => void
}

export function WeeklyPlanningInput(props: Props) {
  const [downloading, setDownloading] = useState(false)
  const fileInputRef = useRef<HTMLInputElement | null>(null)

  const download = async (format: 'csv' | 'xlsx') => {
    setDownloading(true)
    props.onError('')
    try {
      const blob = await api.downloadWeeklyPlanTemplate(format)
      const url = URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      link.download = `weekly-plan-example.${format}`
      link.click()
      window.setTimeout(() => URL.revokeObjectURL(url), 1000)
    } catch (error) {
      props.onError(error instanceof Error ? error.message : 'Unable to download the planning template.')
    } finally {
      setDownloading(false)
    }
  }

  return (
    <div className="space-y-4">
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <div className="space-y-2">
          <Label htmlFor="weekly-plan-date">Week containing</Label>
          <Input id="weekly-plan-date" type="date" value={props.weekStart} disabled={props.busy}
            onChange={(event) => props.onWeek(event.target.value)} />
        </div>
        <div className="space-y-2">
          <Label htmlFor="weekly-plan-year">School year</Label>
          <select id="weekly-plan-year" className="h-10 w-full rounded-md border bg-background px-3 text-sm"
            value={props.schoolYearId} disabled={props.busy} onChange={(event) => props.onSchoolYear(event.target.value)}>
            <option value="">Choose school year</option>
            {props.schoolYears.map((year) => <option key={year.id} value={year.id}>{year.name}</option>)}
          </select>
        </div>
        <div className="space-y-2">
          <Label htmlFor="weekly-plan-student">Default student</Label>
          <select id="weekly-plan-student" className="h-10 w-full rounded-md border bg-background px-3 text-sm"
            value={props.studentId} disabled={props.busy} onChange={(event) => props.onStudent(event.target.value)}>
            <option value="">Use names in plan</option>
            {props.students.map((student) => <option key={student.id} value={student.id}>{student.name}</option>)}
          </select>
        </div>
        <div className="space-y-2">
          <Label htmlFor="weekly-plan-grade">Default grade</Label>
          <Input id="weekly-plan-grade" value={props.grade} disabled={props.busy} placeholder="For example, 7"
            onChange={(event) => props.onGrade(event.target.value)} />
        </div>
      </div>
      <p className="text-sm text-muted-foreground">
        Weekdays use the Monday-Sunday week containing your selected date. Review actual dates before confirming.
        Existing curriculum is reused; new subjects include the grade, such as Spelling - 7th Grade.
      </p>
      <div className="flex flex-wrap gap-2" role="group" aria-label="Plan input">
        <Button type="button" variant={props.inputMode === 'paste' ? 'secondary' : 'outline'}
          aria-pressed={props.inputMode === 'paste'} disabled={props.busy} onClick={() => props.onInputMode('paste')}>Paste plan</Button>
        <Button type="button" variant={props.inputMode === 'file' ? 'secondary' : 'outline'}
          aria-pressed={props.inputMode === 'file'} disabled={props.busy} onClick={() => props.onInputMode('file')}>Upload CSV / Excel</Button>
      </div>
      {props.inputMode === 'paste' ? (
        <div className="space-y-2">
          <Label htmlFor="weekly-plan-text">Your weekly lessons</Label>
          <Textarea id="weekly-plan-text" rows={10} value={props.text} disabled={props.busy}
            onChange={(event) => props.onText(event.target.value)}
            placeholder={'Lucas - 7th Grade\nSpelling - Lesson 6\nTuesday - page 25\nWednesday - page 26\n\nMath - Unit 4\nTuesday - Lesson 4.4 - Textbook pages 99-102 and Worksheet pages 71-72'} />
          <p className="text-xs text-muted-foreground">AI organizes your text into a draft. Nothing is created until you review and confirm.</p>
        </div>
      ) : (
        <div className="space-y-3 rounded-lg border p-4">
          <div className="flex flex-wrap gap-2">
            <Button type="button" variant="outline" disabled={downloading} onClick={() => void download('csv')}>
              <Download className="h-4 w-4" /> Download example CSV
            </Button>
            <Button type="button" variant="outline" disabled={downloading} onClick={() => void download('xlsx')}>
              <Download className="h-4 w-4" /> Download example XLSX
            </Button>
          </div>
          <Button type="button" variant="outline" disabled={props.busy} onClick={() => fileInputRef.current?.click()}>
            <Upload className="h-4 w-4" /> Choose CSV or Excel file
          </Button>
          <input ref={fileInputRef} id="weekly-plan-file" aria-label="Weekly planning file" type="file" className="sr-only" disabled={props.busy}
            accept=".csv,.xlsx,text/csv,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            onChange={(event) => props.onFile(event.target.files?.[0])} />
          <p className="text-sm" aria-live="polite">{props.file?.name || 'No file selected'}</p>
          <p className="text-xs text-muted-foreground">
            You can also upload a weekly Excel grid with subjects down the left and weekdays across the top.
            Include the student and date range in the title; blank cells and completion-check columns are not assignments.
          </p>
          <details className="text-sm">
            <summary className="cursor-pointer font-medium">Columns and spreadsheet guidance</summary>
            <p className="mt-2 text-muted-foreground">
              One row per student&apos;s daily assignment. Required: student, grade, subject, unit, lesson,
              instructions, and date or day. Optional: curriculum, category, estimated_minutes, resource_url,
              max_score, weight. Use YYYY-MM-DD for dates or full weekday names. Leave date blank to use day.
              Templates import without AI. Save CSV as UTF-8; use plain values, not formulas.
            </p>
          </details>
        </div>
      )}
      <Button type="button" onClick={props.onAnalyze}
        disabled={props.busy || !props.schoolYearId || !props.weekStart || (props.inputMode === 'paste' ? !props.text.trim() : !props.file)}>
        {props.busy ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
        {props.busy ? 'Preparing draft...' : 'Review weekly plan'}
      </Button>
    </div>
  )
}
