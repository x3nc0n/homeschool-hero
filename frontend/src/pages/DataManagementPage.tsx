import { useEffect } from 'react'
import { useSearchParams } from 'react-router-dom'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { useAuth } from '@/context/AuthContext'
import { BackupsPage } from './BackupsPage'
import { ExportsPage } from './ExportsPage'
import { ImportsPage } from './ImportsPage'
import { RestorePage } from './RestorePage'

const TABS = ['imports', 'exports', 'backups', 'restore'] as const

type TabValue = (typeof TABS)[number]

export default function DataManagementPage() {
  const { hasCapability } = useAuth()
  const [searchParams, setSearchParams] = useSearchParams()
  const canManageImports = hasCapability('manage_curriculum') || hasCapability('manage_grading') || hasCapability('manage_platform')
  const canManagePlatform = hasCapability('manage_platform')
  const availableTabs = TABS.filter((tab) => {
    if (tab === 'imports') {
      return canManageImports
    }
    return canManagePlatform
  })
  const fallbackTab = availableTabs[0] ?? 'imports'
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
      <h1 className="text-2xl font-semibold">Data Management</h1>
      <Tabs value={activeTab} onValueChange={handleTabChange}>
        <TabsList>
          {availableTabs.includes('imports') ? <TabsTrigger value="imports">Import</TabsTrigger> : null}
          {availableTabs.includes('exports') ? <TabsTrigger value="exports">Export</TabsTrigger> : null}
          {availableTabs.includes('backups') ? <TabsTrigger value="backups">Backups</TabsTrigger> : null}
          {availableTabs.includes('restore') ? <TabsTrigger value="restore">Restore</TabsTrigger> : null}
        </TabsList>
        {availableTabs.includes('imports') ? (
          <TabsContent value="imports">
            <ImportsPage />
          </TabsContent>
        ) : null}
        {availableTabs.includes('exports') ? (
          <TabsContent value="exports">
            <ExportsPage />
          </TabsContent>
        ) : null}
        {availableTabs.includes('backups') ? (
          <TabsContent value="backups">
            <BackupsPage />
          </TabsContent>
        ) : null}
        {availableTabs.includes('restore') ? (
          <TabsContent value="restore">
            <RestorePage />
          </TabsContent>
        ) : null}
      </Tabs>
    </div>
  )
}
