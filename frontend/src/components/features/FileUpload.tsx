import { useMemo, useState } from 'react'
import { Camera, FileText, Upload } from 'lucide-react'
import type { Assignment, Student, Submission } from '@/types/api'
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
import { Progress } from '@/components/ui/progress'

export function FileUpload({
  students,
  assignments,
  onUploaded,
}: {
  students: Student[]
  assignments: Assignment[]
  onUploaded: (submission: Submission) => void
}) {
  const [selectedStudent, setSelectedStudent] = useState<string>('')
  const [selectedAssignment, setSelectedAssignment] = useState<string>('')
  const [file, setFile] = useState<File | null>(null)
  const [previewUrl, setPreviewUrl] = useState<string>('')
  const [isDragging, setIsDragging] = useState(false)
  const [progress, setProgress] = useState(0)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')

  const isImage = useMemo(() => file?.type.startsWith('image/'), [file])

  const onFileChange = (picked?: File) => {
    if (!picked) return
    setFile(picked)
    setError('')
    const objectUrl = URL.createObjectURL(picked)
    setPreviewUrl(objectUrl)
  }

  const handleSubmit = async () => {
    if (!file || !selectedStudent || !selectedAssignment) {
      setError('Please choose a student, assignment, and file.')
      return
    }

    setSubmitting(true)
    setProgress(0)
    setError('')

    try {
      const result = await api.uploadSubmission(
        {
          file,
          student_id: Number(selectedStudent),
          assignment_id: Number(selectedAssignment),
        },
        setProgress,
      )
      setProgress(100)
      onUploaded(result)
      setFile(null)
      setPreviewUrl('')
      setSelectedStudent('')
      setSelectedAssignment('')
    } catch (uploadError) {
      setError(uploadError instanceof Error ? uploadError.message : 'Upload failed.')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Submit student work</CardTitle>
        <CardDescription>Drag and drop a scan/photo or use camera capture on mobile.</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="grid gap-4 md:grid-cols-2">
          <div className="space-y-2">
            <Label>Student</Label>
            <Select value={selectedStudent} onValueChange={setSelectedStudent}>
              <SelectTrigger>
                <SelectValue placeholder="Choose student" />
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
            <Label>Assignment</Label>
            <Select value={selectedAssignment} onValueChange={setSelectedAssignment}>
              <SelectTrigger>
                <SelectValue placeholder="Choose assignment" />
              </SelectTrigger>
              <SelectContent>
                {assignments.map((assignment) => (
                  <SelectItem key={assignment.id} value={String(assignment.id)}>
                    {assignment.title}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </div>

        <div
          className={`rounded-lg border-2 border-dashed p-6 text-center transition ${
            isDragging ? 'border-primary bg-primary/10' : 'border-muted-foreground/30'
          }`}
          onDragOver={(event) => {
            event.preventDefault()
            setIsDragging(true)
          }}
          onDragLeave={() => setIsDragging(false)}
          onDrop={(event) => {
            event.preventDefault()
            setIsDragging(false)
            onFileChange(event.dataTransfer.files?.[0])
          }}
        >
          <Upload className="mx-auto mb-2 h-7 w-7 text-muted-foreground" />
          <p className="text-sm font-medium">Drop file here or browse</p>
          <p className="mt-1 text-xs text-muted-foreground">Images and PDF files supported</p>
          <div className="mt-3 flex flex-col justify-center gap-2 sm:flex-row">
            <Label htmlFor="file-upload" className="cursor-pointer">
              <Input
                id="file-upload"
                type="file"
                className="hidden"
                accept="image/*,application/pdf"
                onChange={(event) => onFileChange(event.target.files?.[0])}
              />
              <Button type="button" variant="secondary">
                <FileText className="mr-2 h-4 w-4" />
                Choose file
              </Button>
            </Label>
            <Label htmlFor="camera-upload" className="cursor-pointer">
              <Input
                id="camera-upload"
                type="file"
                className="hidden"
                accept="image/*"
                capture="environment"
                onChange={(event) => onFileChange(event.target.files?.[0])}
              />
              <Button type="button" variant="outline">
                <Camera className="mr-2 h-4 w-4" />
                Use camera
              </Button>
            </Label>
          </div>
        </div>

        {file ? (
          <div className="rounded-lg border bg-muted/20 p-3 text-sm">
            <p className="font-medium">Selected: {file.name}</p>
            <p className="text-muted-foreground">{Math.round(file.size / 1024)} KB</p>
            {previewUrl ? (
              <div className="mt-3">
                {isImage ? (
                  <img alt="Submission preview" src={previewUrl} className="max-h-56 rounded-md border object-contain" />
                ) : (
                  <iframe title="PDF preview" src={previewUrl} className="h-64 w-full rounded-md border" />
                )}
              </div>
            ) : null}
          </div>
        ) : null}

        {submitting ? (
          <div className="space-y-2">
            <Progress value={progress} />
            <p className="text-xs text-muted-foreground">Uploading… {progress}%</p>
          </div>
        ) : null}

        {error ? <p className="text-sm text-destructive">{error}</p> : null}

        <Button type="button" onClick={() => void handleSubmit()} disabled={submitting || !file}>
          Upload submission
        </Button>
      </CardContent>
    </Card>
  )
}
