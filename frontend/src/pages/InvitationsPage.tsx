import { useEffect, useState } from 'react'
import { Copy, MailPlus, Trash2 } from 'lucide-react'
import { api } from '@/lib/api'
import type { CreateInvitationPayload, FamilyRole, Invitation, Student } from '@/types/api'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { LoadingState } from '@/components/common/LoadingState'
import { ErrorState } from '@/components/common/ErrorState'
import { EmptyState } from '@/components/common/EmptyState'

const roleOptions: Array<{ value: FamilyRole; label: string }> = [
  { value: 'co-parent', label: 'Co-parent' },
  { value: 'tutor', label: 'Tutor' },
  { value: 'student_viewer', label: 'Student viewer' },
]

export function InvitationsPage() {
  const [invitations, setInvitations] = useState<Invitation[]>([])
  const [students, setStudents] = useState<Student[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [copyMessage, setCopyMessage] = useState('')
  const [form, setForm] = useState<CreateInvitationPayload>({
    email: '',
    role: 'co-parent',
    expires_in_days: 7,
  })

  const load = async () => {
    setLoading(true)
    setError('')
    try {
      const [inviteData, studentData] = await Promise.all([api.listInvitations(), api.listStudents()])
      setInvitations(inviteData)
      setStudents(studentData)
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : 'Unable to load invitations')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void load()
  }, [])

  const createInvite = async () => {
    setError('')
    try {
      await api.createInvitation({
        ...form,
        student_id: form.role === 'student_viewer' ? form.student_id : undefined,
        expires_in_days: Number(form.expires_in_days || 7),
      })
      setForm({ email: '', role: 'co-parent', expires_in_days: 7 })
      await load()
    } catch (createError) {
      setError(createError instanceof Error ? createError.message : 'Unable to create invitation')
    }
  }

  const copyValue = async (value?: string | null) => {
    if (!value) return
    await navigator.clipboard.writeText(value)
    setCopyMessage('Invite copied to clipboard.')
    window.setTimeout(() => setCopyMessage(''), 2500)
  }

  if (loading) return <LoadingState message="Loading invitations…" />
  if (error) return <ErrorState message={error} onRetry={() => void load()} />

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <CardTitle>Invite family members</CardTitle>
          <CardDescription>Create time-limited links for co-parents, tutors, and student viewers.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-4 md:grid-cols-2">
            <div className="space-y-2">
              <Label>Email</Label>
              <Input value={form.email} onChange={(event) => setForm((prev) => ({ ...prev, email: event.target.value }))} />
            </div>
            <div className="space-y-2">
              <Label>Role</Label>
              <Select value={form.role} onValueChange={(value: FamilyRole) => setForm((prev) => ({ ...prev, role: value }))}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {roleOptions.map((role) => (
                    <SelectItem key={role.value} value={role.value}>
                      {role.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            {form.role === 'student_viewer' ? (
              <div className="space-y-2">
                <Label>Student</Label>
                <Select value={String(form.student_id || '')} onValueChange={(value) => setForm((prev) => ({ ...prev, student_id: Number(value) }))}>
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
            ) : null}
            <div className="space-y-2">
              <Label>Expires in days</Label>
              <Input
                type="number"
                min={1}
                max={30}
                value={String(form.expires_in_days || 7)}
                onChange={(event) => setForm((prev) => ({ ...prev, expires_in_days: Number(event.target.value) || 7 }))}
              />
            </div>
          </div>
          <Button onClick={() => void createInvite()}>
            <MailPlus className="mr-2 h-4 w-4" />
            Create invitation
          </Button>
          {copyMessage ? <p className="text-sm text-primary">{copyMessage}</p> : null}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Pending invitations</CardTitle>
        </CardHeader>
        <CardContent>
          {invitations.length ? (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Email</TableHead>
                  <TableHead>Role</TableHead>
                  <TableHead>Student</TableHead>
                  <TableHead>Expires</TableHead>
                  <TableHead>Delivery</TableHead>
                  <TableHead className="w-[220px]">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {invitations.map((invite) => (
                  <TableRow key={invite.id}>
                    <TableCell>{invite.email}</TableCell>
                    <TableCell>{invite.role}</TableCell>
                    <TableCell>{invite.student_name || '—'}</TableCell>
                    <TableCell>
                      {new Date(invite.expires_at).toLocaleDateString()}
                      {invite.is_expired ? ' (expired)' : ''}
                    </TableCell>
                    <TableCell>{invite.email_sent ? 'Email sent' : 'Copy link'}</TableCell>
                    <TableCell className="space-x-2">
                      <Button size="sm" variant="outline" onClick={() => void copyValue(invite.invite_link || invite.invite_code)}>
                        <Copy className="mr-2 h-3.5 w-3.5" />
                        Copy
                      </Button>
                      <Button size="sm" variant="destructive" onClick={() => void api.revokeInvitation(invite.id).then(load)}>
                        <Trash2 className="mr-2 h-3.5 w-3.5" />
                        Revoke
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          ) : (
            <EmptyState title="No pending invitations" description="Create an invitation to add another family member." />
          )}
        </CardContent>
      </Card>
    </div>
  )
}
