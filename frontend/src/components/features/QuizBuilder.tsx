import { useState } from 'react'
import { Plus, Trash2 } from 'lucide-react'
import type { Quiz, QuizQuestion, QuizQuestionType, Subject } from '@/types/api'
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
import { Textarea } from '@/components/ui/textarea'
import { api } from '@/lib/api'

const emptyQuestion: QuizQuestion = {
  type: 'multiple_choice',
  prompt: '',
  options: ['', '', '', ''],
  correct_answer: '',
}

export function QuizBuilder({
  subjects,
  onCreated,
}: {
  subjects: Subject[]
  onCreated: (quiz: Quiz) => void
}) {
  const [title, setTitle] = useState('')
  const [subjectId, setSubjectId] = useState('')
  const [questions, setQuestions] = useState<QuizQuestion[]>([emptyQuestion])
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  const updateQuestion = (index: number, changes: Partial<QuizQuestion>) => {
    setQuestions((prev) => prev.map((question, idx) => (idx === index ? { ...question, ...changes } : question)))
  }

  const addQuestion = () => {
    setQuestions((prev) => [...prev, { ...emptyQuestion }])
  }

  const deleteQuestion = (index: number) => {
    setQuestions((prev) => prev.filter((_, idx) => idx !== index))
  }

  const handleTypeChange = (index: number, type: QuizQuestionType) => {
    updateQuestion(index, {
      type,
      options: type === 'multiple_choice' ? ['', '', '', ''] : undefined,
      correct_answer: '',
    })
  }

  const handleSave = async () => {
    const sanitizedQuestions = questions.map((question) => ({
      ...question,
      options: question.type === 'multiple_choice' ? question.options?.filter(Boolean) : undefined,
    }))

    const hasInvalidQuestion = sanitizedQuestions.some(
      (question) => !question.prompt.trim() || !String(question.correct_answer).trim(),
    )

    if (!title.trim() || hasInvalidQuestion) {
      setError('Please add a title and complete every question.')
      return
    }

    setSaving(true)
    setError('')

    try {
      const quiz = await api.createQuiz({
        title,
        subject_id: subjectId ? Number(subjectId) : undefined,
        questions: sanitizedQuestions,
      })
      onCreated(quiz)
      setTitle('')
      setSubjectId('')
      setQuestions([{ ...emptyQuestion }])
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : 'Unable to save quiz')
    } finally {
      setSaving(false)
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Create quiz</CardTitle>
        <CardDescription>Build multiple-choice, short-answer, and true/false assessments.</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="grid gap-4 md:grid-cols-2">
          <div className="space-y-2">
            <Label>Quiz title</Label>
            <Input value={title} onChange={(event) => setTitle(event.target.value)} placeholder="Unit 3 check-in" />
          </div>
          <div className="space-y-2">
            <Label>Subject</Label>
            <Select value={subjectId} onValueChange={setSubjectId}>
              <SelectTrigger>
                <SelectValue placeholder="Optional subject" />
              </SelectTrigger>
              <SelectContent>
                {subjects.map((subject) => (
                  <SelectItem key={subject.id} value={String(subject.id)}>
                    {subject.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </div>

        {questions.map((question, index) => (
          <div key={index} className="space-y-3 rounded-lg border p-4">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <h4 className="text-sm font-semibold">Question {index + 1}</h4>
              <div className="flex items-center gap-2">
                <Select value={question.type} onValueChange={(value: QuizQuestionType) => handleTypeChange(index, value)}>
                  <SelectTrigger className="w-[180px]">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="multiple_choice">Multiple choice</SelectItem>
                    <SelectItem value="short_answer">Short answer</SelectItem>
                    <SelectItem value="true_false">True / False</SelectItem>
                  </SelectContent>
                </Select>
                {questions.length > 1 ? (
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon"
                    aria-label={`Delete question ${index + 1}`}
                    onClick={() => deleteQuestion(index)}
                  >
                    <Trash2 aria-hidden="true" className="h-4 w-4" />
                  </Button>
                ) : null}
              </div>
            </div>

            <Textarea
              aria-label={`Question ${index + 1} prompt`}
              placeholder="Question prompt"
              value={question.prompt}
              onChange={(event) => updateQuestion(index, { prompt: event.target.value })}
            />

            {question.type === 'multiple_choice'
              ? question.options?.map((option, optionIndex) => (
                  <Input
                    key={optionIndex}
                    aria-label={`Question ${index + 1} option ${optionIndex + 1}`}
                    placeholder={`Option ${optionIndex + 1}`}
                    value={option}
                    onChange={(event) => {
                      const options = [...(question.options || [])]
                      options[optionIndex] = event.target.value
                      updateQuestion(index, { options })
                    }}
                  />
                ))
              : null}

            {question.type === 'true_false' ? (
              <Select
                value={question.correct_answer}
                onValueChange={(value) => updateQuestion(index, { correct_answer: value })}
              >
                <SelectTrigger>
                  <SelectValue placeholder="Correct answer" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="true">True</SelectItem>
                  <SelectItem value="false">False</SelectItem>
                </SelectContent>
              </Select>
            ) : (
              <Input
                aria-label={question.type === 'multiple_choice' ? `Question ${index + 1} correct option text` : `Question ${index + 1} expected answer`}
                placeholder={question.type === 'multiple_choice' ? 'Correct option text' : 'Expected answer'}
                value={question.correct_answer}
                onChange={(event) => updateQuestion(index, { correct_answer: event.target.value })}
              />
            )}
          </div>
        ))}

        <div className="flex flex-wrap gap-2">
          <Button type="button" variant="outline" onClick={addQuestion}>
            <Plus className="mr-2 h-4 w-4" />
            Add question
          </Button>
          <Button type="button" onClick={() => void handleSave()} disabled={saving}>
            Save quiz
          </Button>
        </div>
        {error ? (
          <p role="alert" aria-live="assertive" className="text-sm text-destructive">
            {error}
          </p>
        ) : null}
      </CardContent>
    </Card>
  )
}
