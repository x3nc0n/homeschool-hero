import type { AssignmentCategory, AssignmentImportItem, Student, Subject, WeeklyPlanItem } from '@/types/api'
import { Badge } from '@/components/ui/badge'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'

type Props = {
  items: AssignmentImportItem[]
  students: Student[]
  subjects: Subject[]
  selectedIds: string[]
  busy: boolean
  onSelect: (id: string, selected: boolean) => void
  onEdit: (id: string, patch: Partial<AssignmentImportItem>) => void
}

const categories: AssignmentCategory[] = ['homework', 'quiz', 'test', 'project', 'participation', 'extra_credit', 'other']
const selectClass = 'h-10 w-full rounded-md border bg-background px-3 text-sm'

export function WeeklyPlanningPreview({ items, students, subjects, selectedIds, busy, onSelect, onEdit }: Props) {
  const groups = new Map<string, AssignmentImportItem[]>()
  for (const item of items) {
    const names = item.targets.map((target) => students.find((student) => student.id === target.student_id)?.name || 'Choose student').join(', ')
    const date = item.due_date?.slice(0, 10) || item.weekly?.scheduled_date || 'Choose date'
    const key = `${names || item.weekly?.student || 'Choose student'} | ${date}`
    groups.set(key, [...(groups.get(key) || []), item])
  }

  const editWeekly = (item: AssignmentImportItem, patch: Partial<WeeklyPlanItem>) => {
    const current = item.weekly
    if (!current) return
    onEdit(item.client_item_id, {
      weekly: {
        ...current,
        ...patch,
        ...('curriculum' in patch || 'subject' in patch || 'grade' in patch ? { package_id: null } : {}),
      },
    })
  }

  return (
    <div className="space-y-3">
      <p className="text-sm text-muted-foreground">
        Review actual dates and curriculum paths. Expand a row to edit it, then save to refresh matching.
        Confirmation creates the linked curriculum, lesson plans, and assignments together.
      </p>
      {[...groups].map(([group, rows]) => (
        <section key={group} aria-label={group} className="space-y-2 rounded-lg border p-3">
          <h3 className="text-sm font-semibold">{group} <span className="font-normal text-muted-foreground">({rows.length})</span></h3>
          {rows.map((item) => {
            const id = item.client_item_id
            const weekly = item.weekly
            return (
              <details key={id} className="rounded-md border bg-background">
                <summary className="cursor-pointer px-3 py-2 text-sm">
                  <span className="ml-2 inline-flex max-w-full flex-wrap items-center gap-2 align-middle">
                    <input type="checkbox" aria-label={`Include ${item.title || 'lesson'}`}
                      checked={selectedIds.includes(id)} disabled={busy}
                      onClick={(event) => event.stopPropagation()}
                      onChange={(event) => onSelect(id, event.target.checked)} />
                    <span className="font-medium">{weekly?.resolution?.subject_name || weekly?.subject || subjects.find((subject) => subject.id === item.subject_id)?.name || 'Choose subject'}</span>
                    <span>{item.title || weekly?.lesson || 'Untitled activity'}</span>
                    <Badge variant={item.status === 'invalid' ? 'destructive' : item.status === 'ready' ? 'secondary' : 'outline'}>
                      {item.status === 'ready' ? 'Ready' : item.status === 'invalid' ? 'Fix row' : 'Needs info'}
                    </Badge>
                    {(['subject', 'package', 'unit', 'activity'] as const).some((kind) => weekly?.resolution?.[kind] === 'new')
                      ? <Badge variant="outline">New curriculum</Badge> : null}
                    {weekly?.resolution?.duplicate ? <Badge variant="outline">Already planned - will skip</Badge> : null}
                  </span>
                </summary>
                <div className="space-y-3 border-t p-3">
                  <div className="grid gap-3 sm:grid-cols-2">
                    <div className="space-y-1">
                      <Label htmlFor={`${id}-title`}>Assignment title</Label>
                      <Input id={`${id}-title`} disabled={busy} value={item.title || ''}
                        onChange={(event) => onEdit(id, { title: event.target.value })} />
                    </div>
                    <div className="space-y-1">
                      <Label htmlFor={`${id}-date`}>School date</Label>
                      <Input id={`${id}-date`} type="date" disabled={busy} value={item.due_date?.slice(0, 10) || ''}
                        onChange={(event) => onEdit(id, {
                          due_date: event.target.value || null,
                          targets: item.targets.map((target) => ({ ...target, due_date: event.target.value || undefined })),
                          ...(weekly ? { weekly: { ...weekly, scheduled_date: event.target.value || null, day: null } } : {}),
                        })} />
                    </div>
                  </div>
                  {weekly ? (
                    <div className="space-y-3">
                      {weekly.source_week_label ? <p className="text-xs text-muted-foreground">Source week: {weekly.source_week_label}</p> : null}
                      <div className="flex flex-wrap gap-2" aria-label="Curriculum matching decisions">
                        {(['subject', 'package', 'unit', 'activity', 'lesson_plan', 'assignment'] as const).map((kind) => {
                          const decision = weekly.resolution?.[kind]
                          return decision ? (
                            <Badge key={kind} variant={decision === 'conflict' || decision === 'ambiguous' ? 'destructive' : 'outline'}>
                              {kind.replace('_', ' ')}: {decision}
                            </Badge>
                          ) : null
                        })}
                      </div>
                    <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                      {(['grade', 'subject', 'curriculum', 'unit', 'lesson'] as const).map((field) => (
                        <div key={field} className="space-y-1">
                          <Label htmlFor={`${id}-${field}`}>{field === 'curriculum' ? 'Curriculum package' : field === 'lesson' ? 'Curriculum activity' : `${field[0].toUpperCase()}${field.slice(1)}`}</Label>
                          <Input id={`${id}-${field}`} disabled={busy} value={weekly[field] || ''}
                            placeholder={field === 'curriculum' ? 'Reuse matching package or propose a new one' : undefined}
                            onChange={(event) => editWeekly(item, { [field]: event.target.value })} />
                        </div>
                      ))}
                    </div>
                    {weekly.resolution?.package_choices?.length ? (
                      <div className="space-y-1">
                        <Label htmlFor={`${id}-package-match`}>Choose existing curriculum package</Label>
                        <select id={`${id}-package-match`} className={selectClass} disabled={busy} value={weekly.package_id || ''}
                          onChange={(event) => editWeekly(item, { package_id: event.target.value ? Number(event.target.value) : null })}>
                          <option value="">Choose a matching package</option>
                          {weekly.resolution.package_choices.map((choice) => <option key={choice.id} value={choice.id}>{choice.label}</option>)}
                        </select>
                      </div>
                    ) : null}
                    {weekly.activity_name ? <p className="text-xs text-muted-foreground">Curriculum activity: {weekly.activity_name}</p> : null}
                    </div>
                  ) : null}
                  <div className="space-y-1">
                    <Label htmlFor={`${id}-instructions`}>Instructions</Label>
                    <Textarea id={`${id}-instructions`} disabled={busy} value={item.description || ''}
                      onChange={(event) => onEdit(id, {
                        description: event.target.value,
                        ...(weekly ? { weekly: { ...weekly, instructions: event.target.value } } : {}),
                      })} />
                  </div>
                  <div className="grid gap-3 sm:grid-cols-2">
                    <div className="space-y-1">
                      <Label htmlFor={`${id}-student`}>Student</Label>
                      <select id={`${id}-student`} className={selectClass} disabled={busy}
                        value={item.targets[0]?.student_id || ''}
                        onChange={(event) => onEdit(id, {
                          targets: event.target.value ? [{ student_id: Number(event.target.value), status: 'assigned', due_date: item.due_date || undefined }] : [],
                        })}>
                        <option value="">Choose student</option>
                        {students.map((student) => <option key={student.id} value={student.id}>{student.name}</option>)}
                      </select>
                    </div>
                    <div className="space-y-1">
                      <Label htmlFor={`${id}-subject-match`}>Existing subject match</Label>
                      <select id={`${id}-subject-match`} className={selectClass} disabled={busy} value={item.subject_id || ''}
                        onChange={(event) => onEdit(id, { subject_id: event.target.value ? Number(event.target.value) : null })}>
                        <option value="">Match or create from grade and subject</option>
                        {subjects.map((subject) => <option key={subject.id} value={subject.id}>{subject.name}</option>)}
                      </select>
                    </div>
                  </div>
                  <details className="rounded-md bg-muted/30 p-2 text-sm">
                    <summary className="cursor-pointer">Scoring, duration, and resource link</summary>
                    <div className="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                      <div className="space-y-1">
                        <Label htmlFor={`${id}-category`}>Category</Label>
                        <select id={`${id}-category`} className={selectClass} disabled={busy} value={item.category}
                          onChange={(event) => onEdit(id, { category: event.target.value as AssignmentCategory })}>
                          {categories.map((category) => <option key={category} value={category}>{category}</option>)}
                        </select>
                      </div>
                      {(['max_score', 'weight'] as const).map((field) => (
                        <div key={field} className="space-y-1">
                          <Label htmlFor={`${id}-${field}`}>{field === 'max_score' ? 'Maximum score' : 'Weight'}</Label>
                          <Input id={`${id}-${field}`} type="number" min={field === 'weight' ? 0 : 0.5} step="0.5"
                            disabled={busy} value={item[field]} onChange={(event) => onEdit(id, { [field]: Number(event.target.value) })} />
                        </div>
                      ))}
                      {weekly ? (
                        <>
                          <div className="space-y-1">
                            <Label htmlFor={`${id}-minutes`}>Estimated minutes</Label>
                            <Input id={`${id}-minutes`} type="number" min={1} max={1440} disabled={busy} value={weekly.estimated_minutes ?? ''}
                              onChange={(event) => editWeekly(item, { estimated_minutes: event.target.value ? Number(event.target.value) : null })} />
                          </div>
                          <div className="space-y-1 sm:col-span-2">
                            <Label htmlFor={`${id}-resource`}>Resource URL</Label>
                            <Input id={`${id}-resource`} type="url" disabled={busy} value={weekly.resource_url || ''}
                              onChange={(event) => editWeekly(item, { resource_url: event.target.value || null })} />
                          </div>
                        </>
                      ) : null}
                    </div>
                  </details>
                  {item.notes?.map((note) => <p key={note} className="text-xs text-muted-foreground">{note}</p>)}
                  {[...(item.errors || []), ...(item.validation_errors || [])].map((error) => <p key={error} className="text-sm text-destructive">{error}</p>)}
                  {item.missing_fields?.length ? <p className="text-xs text-destructive">Missing: {item.missing_fields.join(', ')}</p> : null}
                  {item.ambiguous_fields?.length ? <p className="text-xs text-destructive">Resolve matches: {item.ambiguous_fields.join(', ')}</p> : null}
                  {item.source_excerpt ? <p className="whitespace-pre-wrap text-xs text-muted-foreground">Source: {item.source_excerpt}</p> : null}
                </div>
              </details>
            )
          })}
        </section>
      ))}
    </div>
  )
}
