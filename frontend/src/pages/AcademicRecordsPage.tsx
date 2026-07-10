import { useEffect } from 'react'
import { useSearchParams } from 'react-router-dom'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { ReportCardsPage } from './ReportCardsPage'
import { TranscriptsPage } from './TranscriptsPage'

const TABS = ['report-cards', 'transcripts'] as const

type TabValue = (typeof TABS)[number]

export default function AcademicRecordsPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const requestedTab = searchParams.get('tab')
  const activeTab = TABS.includes(requestedTab as TabValue) ? (requestedTab as TabValue) : 'report-cards'

  useEffect(() => {
    if (searchParams.get('tab') === activeTab) return
    const nextParams = new URLSearchParams(searchParams)
    nextParams.set('tab', activeTab)
    setSearchParams(nextParams, { replace: true })
  }, [activeTab, searchParams, setSearchParams])

  const handleTabChange = (value: string) => {
    const nextParams = new URLSearchParams(searchParams)
    nextParams.set('tab', value)
    setSearchParams(nextParams)
  }

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold">Academic Records</h1>
      <Tabs value={activeTab} onValueChange={handleTabChange}>
        <TabsList>
          <TabsTrigger value="report-cards">Report Cards</TabsTrigger>
          <TabsTrigger value="transcripts">Transcripts</TabsTrigger>
        </TabsList>
        <TabsContent value="report-cards">
          <ReportCardsPage />
        </TabsContent>
        <TabsContent value="transcripts">
          <TranscriptsPage />
        </TabsContent>
      </Tabs>
    </div>
  )
}
