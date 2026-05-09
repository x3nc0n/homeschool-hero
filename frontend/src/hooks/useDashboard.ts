import { useCallback, useEffect, useState } from 'react'
import { api } from '@/lib/api'
import type { DashboardData } from '@/types/api'

export function useDashboard(studentId?: number) {
  const [dashboard, setDashboard] = useState<DashboardData | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      setDashboard(await api.getDashboard(studentId))
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : 'Unable to load dashboard')
    } finally {
      setLoading(false)
    }
  }, [studentId])

  useEffect(() => {
    void load()
  }, [load])

  return { dashboard, loading, error, reload: load }
}
