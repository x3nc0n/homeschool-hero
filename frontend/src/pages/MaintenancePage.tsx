import type { MaintenanceStatus } from '@/types/api'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'

export function MaintenancePage({ maintenance, onRetry }: { maintenance: MaintenanceStatus; onRetry: () => void }) {
  return (
    <div className="flex min-h-screen items-center justify-center bg-background px-4 py-8">
      <Card className="w-full max-w-2xl">
        <CardHeader>
          <CardTitle>We&apos;ll be back soon</CardTitle>
          <CardDescription>Homeschool Hero is temporarily unavailable while maintenance is in progress.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <p className="text-sm text-muted-foreground">{maintenance.message}</p>
          {maintenance.start_at || maintenance.end_at ? (
            <div className="rounded-md border p-3 text-sm text-muted-foreground">
              {maintenance.start_at ? <p>Start: {new Date(maintenance.start_at).toLocaleString()}</p> : null}
              {maintenance.end_at ? <p>Expected end: {new Date(maintenance.end_at).toLocaleString()}</p> : null}
            </div>
          ) : null}
          <Button onClick={onRetry}>Try again</Button>
        </CardContent>
      </Card>
    </div>
  )
}
