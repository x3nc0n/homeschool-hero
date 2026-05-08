import { useEffect, useMemo, useState } from 'react'
import { api } from '@/lib/api'
import type { Grade, Student, Subject } from '@/types/api'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { LoadingState } from '@/components/common/LoadingState'
import { ErrorState } from '@/components/common/ErrorState'
import { EmptyState } from '@/components/common/EmptyState'

export function GradesPage() {
  const [grades, setGrades] = useState<Grade[]>([])
  const [students, setStudents] = useState<Student[]>([])
  const [subjects, setSubjects] = useState<Subject[]>([])
  const [selectedStudent, setSelectedStudent] = useState('all')
  const [selectedSubject, setSelectedSubject] = useState('all')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const load = async () => {
    setLoading(true)
    setError('')
    try {
      const [gradeData, studentData, subjectData] = await Promise.all([
        api.listGrades(),
        api.listStudents(),
        api.listSubjects(),
      ])
      setGrades(gradeData)
      setStudents(studentData)
      setSubjects(subjectData)
    } catch (gradeError) {
      setError(gradeError instanceof Error ? gradeError.message : 'Unable to load grade book')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void load()
  }, [])

  const filteredGrades = useMemo(
    () =>
      grades.filter((grade) => {
        const studentMatch = selectedStudent === 'all' || String(grade.student_id) === selectedStudent
        const subjectMatch = selectedSubject === 'all' || String(grade.subject_id) === selectedSubject
        return studentMatch && subjectMatch
      }),
    [grades, selectedStudent, selectedSubject],
  )

  const averageByStudent = useMemo(() => {
    const buckets = new Map<number, number[]>()

    filteredGrades.forEach((grade) => {
      const current = buckets.get(grade.student_id) || []
      current.push((grade.score / grade.max_score) * 100)
      buckets.set(grade.student_id, current)
    })

    return Array.from(buckets.entries()).map(([studentId, scores]) => ({
      studentId,
      average: scores.reduce((sum, value) => sum + value, 0) / scores.length,
    }))
  }, [filteredGrades])

  if (loading) return <LoadingState message="Loading grade book…" />
  if (error) return <ErrorState message={error} onRetry={() => void load()} />
  if (!grades.length) return <EmptyState title="No grades yet" description="Grades will appear after submissions are scored." />

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <CardTitle>Grade book</CardTitle>
          <CardDescription>Filter by student and subject, with automatic averages.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-4 md:grid-cols-2">
            <Select value={selectedStudent} onValueChange={setSelectedStudent}>
              <SelectTrigger>
                <SelectValue placeholder="All students" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All students</SelectItem>
                {students.map((student) => (
                  <SelectItem key={student.id} value={String(student.id)}>
                    {student.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>

            <Select value={selectedSubject} onValueChange={setSelectedSubject}>
              <SelectTrigger>
                <SelectValue placeholder="All subjects" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All subjects</SelectItem>
                {subjects.map((subject) => (
                  <SelectItem key={subject.id} value={String(subject.id)}>
                    {subject.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Student</TableHead>
                <TableHead>Assignment</TableHead>
                <TableHead>Score</TableHead>
                <TableHead>Letter</TableHead>
                <TableHead>Graded by</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {filteredGrades.map((grade) => (
                <TableRow key={grade.id}>
                  <TableCell>
                    {grade.student?.name || students.find((student) => student.id === grade.student_id)?.name || grade.student_id}
                  </TableCell>
                  <TableCell>{grade.assignment?.title || `Assignment #${grade.assignment_id || '—'}`}</TableCell>
                  <TableCell>{grade.score}/{grade.max_score}</TableCell>
                  <TableCell>{grade.letter_grade || '—'}</TableCell>
                  <TableCell>{grade.graded_by || 'human'}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Averages</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2">
          {averageByStudent.map((entry) => (
            <div key={entry.studentId} className="flex items-center justify-between rounded-md border p-3 text-sm">
              <span>{students.find((student) => student.id === entry.studentId)?.name || `Student #${entry.studentId}`}</span>
              <span className="font-semibold">{entry.average.toFixed(1)}%</span>
            </div>
          ))}
        </CardContent>
      </Card>
    </div>
  )
}
