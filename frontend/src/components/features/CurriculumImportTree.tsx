import { Badge } from '@/components/ui/badge'
import { cn } from '@/lib/utils'
import type { NormalizedCurriculumImport } from '@/lib/curriculumImport'
import { formatDurationMinutes } from '@/lib/curriculumImport'

type CurriculumImportTreeProps = {
  curriculum: NormalizedCurriculumImport
  className?: string
  expandAll?: boolean
}

function MetadataBadges({ values }: { values: string[] }) {
  if (!values.length) return null
  return (
    <div className="flex flex-wrap gap-2">
      {values.map((value) => (
        <Badge key={value} variant="outline">
          {value}
        </Badge>
      ))}
    </div>
  )
}

export function CurriculumImportTree({ curriculum, className, expandAll = true }: CurriculumImportTreeProps) {
  return (
    <div className={cn('space-y-3', className)}>
      {curriculum.subjects.map((subject) => (
        <details key={`${subject.id ?? subject.name}-${subject.sequenceOrder}`} className="rounded-lg border bg-card" open={expandAll}>
          <summary className="cursor-pointer list-inside px-4 py-3 font-medium">
            <div className="inline-flex flex-wrap items-center gap-2">
              <span>{subject.name}</span>
              <Badge variant="secondary">{subject.units.length} unit{subject.units.length === 1 ? '' : 's'}</Badge>
              <Badge variant="outline">
                {subject.units.reduce((count, unit) => count + unit.lessons.length, 0)} lesson
                {subject.units.reduce((count, unit) => count + unit.lessons.length, 0) === 1 ? '' : 's'}
              </Badge>
            </div>
          </summary>
          <div className="space-y-3 border-t px-4 py-4">
            {subject.description ? <p className="text-sm text-muted-foreground">{subject.description}</p> : null}
            <MetadataBadges values={subject.metadata.gradeLevels} />
            {subject.units.map((unit) => (
              <details key={`${unit.id ?? unit.name}-${unit.sequenceOrder}`} className="rounded-lg border bg-muted/20" open={expandAll}>
                <summary className="cursor-pointer list-inside px-4 py-3 font-medium">
                  <div className="inline-flex flex-wrap items-center gap-2">
                    <span>{unit.name}</span>
                    <Badge variant="outline">{unit.lessons.length} lessons</Badge>
                  </div>
                </summary>
                <div className="space-y-3 border-t px-4 py-4">
                  {unit.description ? <p className="text-sm text-muted-foreground">{unit.description}</p> : null}
                  {unit.lessons.map((lesson) => (
                    <details key={`${lesson.id ?? lesson.name}-${lesson.sequenceOrder}`} className="rounded-lg border bg-background" open={expandAll}>
                      <summary className="cursor-pointer list-inside px-4 py-3 font-medium">
                        <div className="inline-flex flex-wrap items-center gap-2">
                          <span>{lesson.name}</span>
                          <Badge variant="secondary">{formatDurationMinutes(lesson.estimatedMinutes)}</Badge>
                          {lesson.resources.length ? <Badge variant="outline">{lesson.resources.length} resources</Badge> : null}
                        </div>
                      </summary>
                      <div className="space-y-3 border-t px-4 py-4 text-sm">
                        {lesson.description ? <p className="text-muted-foreground">{lesson.description}</p> : null}
                        {lesson.objectives.length ? (
                          <div className="space-y-2">
                            <p className="font-medium">Objectives</p>
                            <ul className="list-disc space-y-1 pl-5 text-muted-foreground">
                              {lesson.objectives.map((objective) => (
                                <li key={objective}>{objective}</li>
                              ))}
                            </ul>
                          </div>
                        ) : null}
                        {lesson.standardsAlignment.length ? (
                          <div className="space-y-2">
                            <p className="font-medium">Standards</p>
                            <MetadataBadges values={lesson.standardsAlignment} />
                          </div>
                        ) : null}
                        {lesson.prerequisites.length ? (
                          <div className="space-y-2">
                            <p className="font-medium">Prerequisites</p>
                            <MetadataBadges values={lesson.prerequisites} />
                          </div>
                        ) : null}
                        {lesson.resources.length ? (
                          <div className="space-y-2">
                            <p className="font-medium">Resources</p>
                            <div className="space-y-2">
                              {lesson.resources.map((resource) => (
                                <div key={`${resource.resourceType}-${resource.name}`} className="rounded-lg border p-3">
                                  <div className="flex flex-wrap items-center gap-2">
                                    <p className="font-medium">{resource.name}</p>
                                    <Badge variant="outline">{resource.resourceType}</Badge>
                                  </div>
                                  {resource.description ? <p className="mt-1 text-muted-foreground">{resource.description}</p> : null}
                                  {resource.url ? (
                                    <a
                                      className="mt-2 inline-flex text-sm text-primary underline underline-offset-4"
                                      href={resource.url}
                                      rel="noreferrer"
                                      target="_blank"
                                    >
                                      Open resource
                                    </a>
                                  ) : null}
                                </div>
                              ))}
                            </div>
                          </div>
                        ) : null}
                      </div>
                    </details>
                  ))}
                </div>
              </details>
            ))}
          </div>
        </details>
      ))}
    </div>
  )
}
