import { Link } from 'react-router-dom'
import { Button } from '@/components/ui/button'

export function NotFoundPage() {
  return (
    <div className="rounded-lg border bg-card p-10 text-center">
      <h2 className="text-xl font-semibold">Page not found</h2>
      <p className="mt-2 text-sm text-muted-foreground">The page you requested doesn't exist.</p>
      <Button asChild className="mt-4">
        <Link to="/dashboard">Back to dashboard</Link>
      </Button>
    </div>
  )
}
