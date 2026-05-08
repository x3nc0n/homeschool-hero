import { useMemo, useState } from 'react'
import type { Quiz, QuizQuestion, Student } from '@/types/api'
import { api } from '@/lib/api'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'

function scoreLocally(questions: QuizQuestion[], answers: string[]) {
  let score = 0
  questions.forEach((question, index) => {
    if ((answers[index] || '').trim().toLowerCase() === question.correct_answer.trim().toLowerCase()) {
      score += 1
    }
  })
  return score
}

export function QuizTaker({ quizzes, students }: { quizzes: Quiz[]; students: Student[] }) {
  const [quizId, setQuizId] = useState('')
  const [studentId, setStudentId] = useState('')
  const [answers, setAnswers] = useState<string[]>([])
  const [result, setResult] = useState<string>('')
  const [error, setError] = useState('')
  const [submitting, setSubmitting] = useState(false)

  const selectedQuiz = useMemo(() => quizzes.find((quiz) => String(quiz.id) === quizId), [quizzes, quizId])

  const syncAnswersLength = (count: number) => {
    setAnswers((prev) => {
      if (prev.length === count) return prev
      return Array.from({ length: count }, (_, index) => prev[index] || '')
    })
  }

  const submitAttempt = async () => {
    if (!selectedQuiz || !studentId) {
      setError('Choose a student and quiz before submitting.')
      return
    }

    setSubmitting(true)
    setError('')

    try {
      const maxScore = selectedQuiz.questions.length
      const localScore = scoreLocally(selectedQuiz.questions, answers)

      try {
        const serverResult = await api.submitQuizAttempt(selectedQuiz.id, {
          student_id: Number(studentId),
          answers,
        })
        setResult(`Submitted. Score: ${serverResult.score}/${serverResult.max_score}`)
      } catch {
        setResult(`Submitted locally. Score: ${localScore}/${maxScore}`)
      }
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : 'Unable to submit quiz')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Take quiz</CardTitle>
        <CardDescription>Run a quiz session and submit student responses.</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="grid gap-4 md:grid-cols-2">
          <div className="space-y-2">
            <Label>Student</Label>
            <Select value={studentId} onValueChange={setStudentId}>
              <SelectTrigger>
                <SelectValue placeholder="Select student" />
              </SelectTrigger>
              <SelectContent>
                {students.map((student) => (
                  <SelectItem key={student.id} value={String(student.id)}>
                    {student.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-2">
            <Label>Quiz</Label>
            <Select
              value={quizId}
              onValueChange={(value) => {
                setQuizId(value)
                const nextQuiz = quizzes.find((quiz) => String(quiz.id) === value)
                syncAnswersLength(nextQuiz?.questions.length || 0)
              }}
            >
              <SelectTrigger>
                <SelectValue placeholder="Select quiz" />
              </SelectTrigger>
              <SelectContent>
                {quizzes.map((quiz) => (
                  <SelectItem key={quiz.id} value={String(quiz.id)}>
                    {quiz.title}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </div>

        {selectedQuiz
          ? selectedQuiz.questions.map((question, index) => (
              <div key={index} className="space-y-2 rounded-lg border p-3">
                <p className="text-sm font-semibold">Q{index + 1}. {question.prompt}</p>
                {question.type === 'multiple_choice' ? (
                  <Select
                    value={answers[index] || ''}
                    onValueChange={(value) => {
                      const next = [...answers]
                      next[index] = value
                      setAnswers(next)
                    }}
                  >
                    <SelectTrigger>
                      <SelectValue placeholder="Select an answer" />
                    </SelectTrigger>
                    <SelectContent>
                      {question.options?.map((option) => (
                        <SelectItem key={option} value={option}>
                          {option}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                ) : question.type === 'true_false' ? (
                  <Select
                    value={answers[index] || ''}
                    onValueChange={(value) => {
                      const next = [...answers]
                      next[index] = value
                      setAnswers(next)
                    }}
                  >
                    <SelectTrigger>
                      <SelectValue placeholder="Select true or false" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="true">True</SelectItem>
                      <SelectItem value="false">False</SelectItem>
                    </SelectContent>
                  </Select>
                ) : (
                  <Input
                    value={answers[index] || ''}
                    onChange={(event) => {
                      const next = [...answers]
                      next[index] = event.target.value
                      setAnswers(next)
                    }}
                    placeholder="Type answer"
                  />
                )}
              </div>
            ))
          : null}

        <Button type="button" disabled={submitting || !selectedQuiz} onClick={() => void submitAttempt()}>
          Submit quiz
        </Button>

        {result ? <p className="text-sm text-primary">{result}</p> : null}
        {error ? <p className="text-sm text-destructive">{error}</p> : null}
      </CardContent>
    </Card>
  )
}
