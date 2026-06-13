import { useCallback, useEffect, useMemo, useState } from 'react'
import { BookOpen, ExternalLink, Globe, Import, Search } from 'lucide-react'
import { api } from '@/lib/api'
import type { CurriculumImportDetail, CurriculumSourceSearchResult, CurriculumSourceSummary } from '@/types/api'
import { cn } from '@/lib/utils'
import { EmptyState } from '@/components/common/EmptyState'
import { ErrorState } from '@/components/common/ErrorState'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'

type CurriculumSourceBrowserProps = {
  onImported: () => void
  onOpenLibrary: () => void
}

function SourceCardSkeleton() {
  return (
    <div className="space-y-3 rounded-xl border p-4">
      <div className="h-12 w-12 animate-pulse rounded-full bg-muted" />
      <div className="space-y-2">
        <div className="h-4 w-1/3 animate-pulse rounded bg-muted" />
        <div className="h-3 w-full animate-pulse rounded bg-muted" />
        <div className="h-3 w-5/6 animate-pulse rounded bg-muted" />
      </div>
      <div className="flex gap-2">
        <div className="h-5 w-16 animate-pulse rounded-full bg-muted" />
        <div className="h-5 w-16 animate-pulse rounded-full bg-muted" />
      </div>
    </div>
  )
}

function ResultCardSkeleton() {
  return (
    <div className="space-y-3 rounded-xl border p-4">
      <div className="h-5 w-2/3 animate-pulse rounded bg-muted" />
      <div className="h-4 w-1/4 animate-pulse rounded bg-muted" />
      <div className="space-y-2">
        <div className="h-3 w-full animate-pulse rounded bg-muted" />
        <div className="h-3 w-5/6 animate-pulse rounded bg-muted" />
      </div>
      <div className="h-9 w-24 animate-pulse rounded bg-muted" />
    </div>
  )
}

function SourceAvatar({ source }: { source: CurriculumSourceSummary }) {
  if (source.logo_url) {
    return <img src={source.logo_url} alt="" className="h-12 w-12 rounded-full border object-cover" />
  }

  const initials = source.name
    .split(/\s+/)
    .map((part) => part[0])
    .join('')
    .slice(0, 2)
    .toUpperCase()

  return (
    <div className="flex h-12 w-12 items-center justify-center rounded-full border bg-primary/10 text-sm font-semibold text-primary">
      {initials || 'CS'}
    </div>
  )
}

function SourceMetadataBadges({ values }: { values: string[] | undefined }) {
  if (!values?.length) return null
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

function formatImportMessage(curriculum: CurriculumImportDetail) {
  return `${curriculum.name} is now in My Library.`
}

export function CurriculumSourceBrowser({ onImported, onOpenLibrary }: CurriculumSourceBrowserProps) {
  const [sources, setSources] = useState<CurriculumSourceSummary[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [activeSourceId, setActiveSourceId] = useState('')
  const [query, setQuery] = useState('')
  const [submittedQuery, setSubmittedQuery] = useState('')
  const [results, setResults] = useState<CurriculumSourceSearchResult[]>([])
  const [searching, setSearching] = useState(false)
  const [searchError, setSearchError] = useState('')
  const [importingId, setImportingId] = useState('')
  const [importMessage, setImportMessage] = useState('')

  const loadSources = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const availableSources = await api.listCurriculumSources()
      setSources(availableSources)
      setActiveSourceId((current) => current || availableSources[0]?.source || '')
      setQuery((current) => current || availableSources[0]?.search_hint || '')
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : 'Unable to load curriculum sources right now.')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void loadSources()
  }, [loadSources])

  const activeSource = useMemo(
    () => sources.find((source) => source.source === activeSourceId) ?? null,
    [activeSourceId, sources],
  )

  const handleSourceSelect = (source: CurriculumSourceSummary) => {
    setActiveSourceId(source.source)
    setQuery(source.search_hint || '')
    setResults([])
    setSubmittedQuery('')
    setSearchError('')
    setImportMessage('')
  }

  const handleSearch = async () => {
    if (!activeSource) return
    const trimmedQuery = query.trim()
    if (!trimmedQuery) {
      setSearchError('Enter a search term to browse this source.')
      setResults([])
      setSubmittedQuery('')
      return
    }

    setSearching(true)
    setSearchError('')
    setImportMessage('')
    setSubmittedQuery(trimmedQuery)
    try {
      const nextResults = await api.searchCurriculumSource(activeSource.source, trimmedQuery)
      setResults(nextResults)
    } catch (searchLoadError) {
      setSearchError(searchLoadError instanceof Error ? searchLoadError.message : 'Unable to search this curriculum source right now.')
      setResults([])
    } finally {
      setSearching(false)
    }
  }

  const handleImport = async (result: CurriculumSourceSearchResult) => {
    if (!activeSource) return
    setImportingId(result.item_id)
    setSearchError('')
    setImportMessage('')
    try {
      const imported = await api.importCurriculumSource(activeSource.source, result.item_id)
      setImportMessage(formatImportMessage(imported))
      onImported()
    } catch (importError) {
      setSearchError(importError instanceof Error ? importError.message : 'Unable to import this curriculum right now.')
    } finally {
      setImportingId('')
    }
  }

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <CardTitle>Browse external curriculum sources</CardTitle>
          <CardDescription>Search trusted providers, preview the metadata, and import a copy into your library.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {loading ? (
            <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
              {Array.from({ length: 3 }, (_, index) => (
                <SourceCardSkeleton key={index} />
              ))}
            </div>
          ) : error ? (
            <ErrorState message={error} onRetry={() => void loadSources()} />
          ) : !sources.length ? (
            <EmptyState title="No sources available" description="Connect a curriculum source or try again later." />
          ) : (
            <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
              {sources.map((source) => {
                const isActive = source.source === activeSourceId
                return (
                  <button
                    key={source.source}
                    type="button"
                    onClick={() => handleSourceSelect(source)}
                    className="w-full text-left"
                  >
                    <Card
                      size="sm"
                      className={cn(
                        'cursor-pointer border text-left transition hover:ring-primary/30',
                        isActive ? 'ring-2 ring-primary/50' : 'ring-1 ring-foreground/10',
                      )}
                    >
                      <CardHeader>
                        <div className="flex items-start gap-3">
                          <SourceAvatar source={source} />
                          <div className="space-y-1">
                            <CardTitle>{source.name}</CardTitle>
                            {source.provider ? <CardDescription>{source.provider}</CardDescription> : null}
                          </div>
                        </div>
                      </CardHeader>
                      <CardContent className="space-y-3">
                        <p className="text-sm text-muted-foreground">{source.description || 'Browse available curricula from this provider.'}</p>
                        <SourceMetadataBadges values={source.subjects} />
                        <SourceMetadataBadges values={source.grade_levels?.map((grade) => `Grade ${grade}`)} />
                      </CardContent>
                    </Card>
                  </button>
                )
              })}
            </div>
          )}
        </CardContent>
      </Card>

      {activeSource ? (
        <Card>
          <CardHeader>
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <CardTitle>{activeSource.name} search</CardTitle>
                <CardDescription>{activeSource.description || 'Find a curriculum to import.'}</CardDescription>
              </div>
              {activeSource.website_url ? (
                <a
                  href={activeSource.website_url}
                  target="_blank"
                  rel="noreferrer"
                  className="inline-flex items-center gap-1 text-sm text-primary underline underline-offset-4"
                >
                  Visit source
                  <ExternalLink className="h-4 w-4" />
                </a>
              ) : null}
            </div>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex flex-col gap-3 md:flex-row">
              <div className="relative flex-1">
                <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                <Input
                  value={query}
                  onChange={(event) => setQuery(event.target.value)}
                  onKeyDown={(event) => {
                    if (event.key === 'Enter') {
                      event.preventDefault()
                      void handleSearch()
                    }
                  }}
                  className="pl-9"
                  placeholder={`Search ${activeSource.name}`}
                />
              </div>
              <Button type="button" onClick={() => void handleSearch()} disabled={searching}>
                <Search className="h-4 w-4" />
                {searching ? 'Searching…' : 'Search'}
              </Button>
            </div>

            {importMessage ? (
              <div className="flex flex-col gap-3 rounded-lg border border-emerald-500/30 bg-emerald-500/10 p-4 md:flex-row md:items-center md:justify-between">
                <p className="text-sm text-emerald-900 dark:text-emerald-100">{importMessage}</p>
                <Button type="button" size="sm" variant="outline" onClick={onOpenLibrary}>
                  Open My Library
                </Button>
              </div>
            ) : null}

            {searchError ? <ErrorState message={searchError} onRetry={() => void handleSearch()} /> : null}

            {searching ? (
              <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
                {Array.from({ length: 3 }, (_, index) => (
                  <ResultCardSkeleton key={index} />
                ))}
              </div>
            ) : results.length ? (
              <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
                {results.map((result) => {
                  const isImporting = importingId === result.item_id
                  return (
                    <Card key={result.item_id}>
                      <CardHeader>
                        <div className="flex items-start gap-3">
                          <div className="rounded-full border bg-primary/10 p-2 text-primary">
                            {result.subject?.toLowerCase().includes('science') ? <Globe className="h-4 w-4" /> : <BookOpen className="h-4 w-4" />}
                          </div>
                          <div className="space-y-1">
                            <CardTitle>{result.title}</CardTitle>
                            <CardDescription>{result.subject || 'Curriculum source item'}</CardDescription>
                          </div>
                        </div>
                      </CardHeader>
                      <CardContent className="space-y-3">
                        <div className="flex flex-wrap gap-2">
                          {result.grade_levels?.map((gradeLevel) => (
                            <Badge key={gradeLevel} variant="outline">
                              Grade {gradeLevel}
                            </Badge>
                          ))}
                          {result.subjects?.map((subject) => (
                            <Badge key={subject} variant="secondary">
                              {subject}
                            </Badge>
                          ))}
                        </div>
                        <p className="text-sm text-muted-foreground">
                          {result.description || 'No description was provided by this curriculum source.'}
                        </p>
                        <Button type="button" disabled={isImporting} onClick={() => void handleImport(result)}>
                          <Import className="h-4 w-4" />
                          {isImporting ? 'Importing…' : 'Import'}
                        </Button>
                      </CardContent>
                    </Card>
                  )
                })}
              </div>
            ) : submittedQuery ? (
              <EmptyState
                title="No results"
                description={`No ${activeSource.name} results matched “${submittedQuery}”. Try a different keyword.`}
              />
            ) : (
              <EmptyState
                title="Pick a source and search"
                description={`Try “${activeSource.search_hint || 'biology'}” or another topic to browse ${activeSource.name}.`}
              />
            )}
          </CardContent>
        </Card>
      ) : null}
    </div>
  )
}
