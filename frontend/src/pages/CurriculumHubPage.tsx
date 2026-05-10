import { useEffect } from 'react'
import { useSearchParams } from 'react-router-dom'
import type { FamilyRole } from '@/types/api'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { useAuth } from '@/context/AuthContext'
import { CurriculumPage } from './CurriculumPage'
import { LessonPlansPage } from './LessonPlansPage'
import { ResourceLibraryPage } from './ResourceLibraryPage'

const TABS = ['curriculum', 'lesson-plans', 'resources'] as const

type TabValue = (typeof TABS)[number]

const tabRoles: Record<TabValue, FamilyRole[]> = {
  curriculum: ['parent', 'co-parent', 'tutor'],
  'lesson-plans': ['parent', 'co-parent', 'tutor', 'student_viewer'],
  resources: ['parent', 'co-parent', 'tutor'],
}

export default function CurriculumHubPage() {
  const { role } = useAuth()
  const [searchParams, setSearchParams] = useSearchParams()
  const availableTabs = TABS.filter((tab) => (role ? tabRoles[tab].includes(role) : false))
  const fallbackTab = availableTabs[0] ?? 'curriculum'
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
      <h1 className="text-3xl font-bold">Curriculum</h1>
      <Tabs value={activeTab} onValueChange={handleTabChange}>
        <TabsList>
          {availableTabs.includes('curriculum') ? <TabsTrigger value="curriculum">Packages</TabsTrigger> : null}
          <TabsTrigger value="lesson-plans">Lesson Plans</TabsTrigger>
          {availableTabs.includes('resources') ? <TabsTrigger value="resources">Resources</TabsTrigger> : null}
        </TabsList>
        {availableTabs.includes('curriculum') ? (
          <TabsContent value="curriculum">
            <CurriculumPage />
          </TabsContent>
        ) : null}
        <TabsContent value="lesson-plans">
          <LessonPlansPage />
        </TabsContent>
        {availableTabs.includes('resources') ? (
          <TabsContent value="resources">
            <ResourceLibraryPage />
          </TabsContent>
        ) : null}
      </Tabs>
    </div>
  )
}
