import { useEffect } from 'react'
import { useSearchParams } from 'react-router-dom'
import type { FamilyRole } from '@/types/api'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { useAuth } from '@/context/AuthContext'
import { GradesPage } from './GradesPage'
import { ReviewQueuePage } from './ReviewQueuePage'

const TABS = ['grades', 'review'] as const

type TabValue = (typeof TABS)[number]

const tabRoles: Record<TabValue, FamilyRole[]> = {
  grades: ['parent', 'co-parent', 'tutor', 'student_viewer'],
  review: ['parent', 'co-parent', 'tutor'],
}

export default function GradebookPage() {
  const { role } = useAuth()
  const [searchParams, setSearchParams] = useSearchParams()
  const availableTabs = TABS.filter((tab) => (role ? tabRoles[tab].includes(role) : false))
  const fallbackTab = availableTabs[0] ?? 'grades'
  const requestedTab = searchParams.get('tab')
  const activeTab = availableTabs.includes(requestedTab as TabValue) ? (requestedTab as TabValue) : fallbackTab

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
      <h1 className="text-3xl font-bold">Gradebook</h1>
      <Tabs value={activeTab} onValueChange={handleTabChange}>
        <TabsList>
          <TabsTrigger value="grades">Grades</TabsTrigger>
          {availableTabs.includes('review') ? <TabsTrigger value="review">Review Queue</TabsTrigger> : null}
        </TabsList>
        <TabsContent value="grades">
          <GradesPage />
        </TabsContent>
        {availableTabs.includes('review') ? (
          <TabsContent value="review">
            <ReviewQueuePage />
          </TabsContent>
        ) : null}
      </Tabs>
    </div>
  )
}
