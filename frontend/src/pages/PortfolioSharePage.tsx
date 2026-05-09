import { Link2 } from 'lucide-react'
import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { api } from '@/lib/api'
import type { PublicPortfolioCollection } from '@/types/api'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { EmptyState } from '@/components/common/EmptyState'
import { ErrorState } from '@/components/common/ErrorState'
import { LoadingState } from '@/components/common/LoadingState'

function formatDateLabel(value: string) {
  return new Date(value).toLocaleDateString()
}

export function PortfolioSharePage() {
  const { shareToken } = useParams()
  const [collection, setCollection] = useState<PublicPortfolioCollection | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    const load = async () => {
      if (!shareToken) return
      setLoading(true)
      setError('')
      try {
        setCollection(await api.getPublicPortfolioCollection(shareToken))
      } catch (loadError) {
        setError(loadError instanceof Error ? loadError.message : 'Unable to load shared portfolio')
      } finally {
        setLoading(false)
      }
    }
    void load()
  }, [shareToken])

  if (loading) return <LoadingState message="Loading shared portfolio…" />
  if (error) return <ErrorState message={error} />
  if (!collection) return <EmptyState title="Share unavailable" description="This portfolio share link is missing or expired." />

  return (
    <div className="mx-auto min-h-screen max-w-4xl space-y-4 px-4 py-8">
      <Card>
        <CardHeader>
          <CardTitle>{collection.name}</CardTitle>
          <p className="text-sm text-muted-foreground">{collection.description || 'Shared portfolio collection'}</p>
        </CardHeader>
      </Card>
      {collection.entries.length ? (
        collection.entries.map((entry) => (
          <Card key={entry.id}>
            <CardHeader>
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div>
                  <CardTitle className="text-lg">{entry.title}</CardTitle>
                  <p className="text-sm text-muted-foreground">{formatDateLabel(entry.date)}</p>
                </div>
                <Badge>{entry.entry_type.replace('_', ' ')}</Badge>
              </div>
            </CardHeader>
            <CardContent className="space-y-3">
              <p className="whitespace-pre-wrap text-sm text-muted-foreground">{entry.description || 'No description provided.'}</p>
              <div className="flex flex-wrap gap-2">
                {entry.subject?.name ? <Badge variant="outline">{entry.subject.name}</Badge> : null}
                {entry.assignment?.title ? <Badge variant="secondary">{entry.assignment.title}</Badge> : null}
                {entry.tags.map((tag) => (
                  <span key={tag} className="rounded-full bg-muted px-2 py-0.5 text-xs text-muted-foreground">
                    #{tag}
                  </span>
                ))}
              </div>
              {entry.attachment_urls.length ? (
                <div className="space-y-2">
                  {entry.attachment_urls.map((url, index) => (
                    <a key={url} className="flex items-center gap-2 text-sm text-primary hover:underline" href={url} target="_blank" rel="noreferrer">
                      <Link2 className="h-4 w-4" />
                      Attachment {index + 1}
                    </a>
                  ))}
                </div>
              ) : null}
            </CardContent>
          </Card>
        ))
      ) : (
        <EmptyState title="No shared entries" description="This collection does not contain any entries yet." />
      )}
    </div>
  )
}
