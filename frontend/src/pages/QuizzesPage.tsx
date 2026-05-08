import { useEffect, useState } from 'react'
import { QuizBuilder } from '@/components/features/QuizBuilder'
import { QuizTaker } from '@/components/features/QuizTaker'
import { EmptyState } from '@/components/common/EmptyState'
import { ErrorState } from '@/components/common/ErrorState'
import { LoadingState } from '@/components/common/LoadingState'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { api } from '@/lib/api'
import type { Quiz, Student, Subject } from '@/types/api'

export function QuizzesPage() {
  const [quizzes, setQuizzes] = useState<Quiz[]>([])
  const [subjects, setSubjects] = useState<Subject[]>([])
  const [students, setStudents] = useState<Student[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const load = async () => {
    setLoading(true)
    setError('')
    try {
      const [quizData, subjectData, studentData] = await Promise.all([
        api.listQuizzes(),
        api.listSubjects(),
        api.listStudents(),
      ])
      setQuizzes(quizData)
      setSubjects(subjectData)
      setStudents(studentData)
    } catch (quizError) {
      setError(quizError instanceof Error ? quizError.message : 'Unable to load quizzes')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void load()
  }, [])

  if (loading) return <LoadingState message="Loading quizzes…" />
  if (error) return <ErrorState message={error} onRetry={() => void load()} />

  return (
    <div className="space-y-4">
      <QuizBuilder
        subjects={subjects}
        onCreated={(quiz) => {
          setQuizzes((prev) => [quiz, ...prev])
        }}
      />

      <QuizTaker quizzes={quizzes} students={students} />

      <Card>
        <CardHeader>
          <CardTitle>Saved quizzes</CardTitle>
        </CardHeader>
        <CardContent>
          {quizzes.length ? (
            <div className="space-y-2">
              {quizzes.map((quiz) => (
                <div key={quiz.id} className="rounded-md border p-3 text-sm">
                  <p className="font-semibold">{quiz.title}</p>
                  <p className="text-muted-foreground">{quiz.questions.length} questions</p>
                </div>
              ))}
            </div>
          ) : (
            <EmptyState title="No quizzes yet" description="Use the builder above to create your first quiz." />
          )}
        </CardContent>
      </Card>
    </div>
  )
}
