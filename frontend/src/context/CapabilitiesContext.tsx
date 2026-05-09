import { createContext, useContext, useEffect, useMemo, useState } from 'react'
import { api } from '@/lib/api'
import type { CapabilitiesResponse, CapabilityName, CapabilityStatus } from '@/types/api'

type CapabilityContextValue = {
  loading: boolean
  error: string
  status: 'ok' | 'degraded'
  capabilities: CapabilitiesResponse['capabilities']
  optionalUnavailable: CapabilityName[]
  refresh: () => Promise<void>
  isEnabled: (name: CapabilityName) => boolean
}

const defaultCapabilities = {
  ai_grading: {
    name: 'ai_grading',
    enabled: false,
    configured: false,
    status: 'disabled',
    reason: 'Capability status not loaded yet.',
    details: {},
    checked_at: '',
  },
  email: {
    name: 'email',
    enabled: false,
    configured: false,
    status: 'disabled',
    reason: 'Capability status not loaded yet.',
    details: {},
    checked_at: '',
  },
  backup: {
    name: 'backup',
    enabled: false,
    configured: false,
    status: 'disabled',
    reason: 'Capability status not loaded yet.',
    details: {},
    checked_at: '',
  },
  ocr: {
    name: 'ocr',
    enabled: false,
    configured: false,
    status: 'disabled',
    reason: 'Capability status not loaded yet.',
    details: {},
    checked_at: '',
  },
} satisfies Record<CapabilityName, CapabilityStatus>

const CapabilityContext = createContext<CapabilityContextValue | undefined>(undefined)

export function CapabilitiesProvider({ children }: { children: React.ReactNode }) {
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [status, setStatus] = useState<'ok' | 'degraded'>('degraded')
  const [capabilities, setCapabilities] = useState<CapabilitiesResponse['capabilities']>(defaultCapabilities)
  const [optionalUnavailable, setOptionalUnavailable] = useState<CapabilityName[]>(
    Object.keys(defaultCapabilities) as CapabilityName[],
  )

  const refresh = async () => {
    setLoading(true)
    try {
      const response = await api.getCapabilities()
      setCapabilities(response.capabilities)
      setOptionalUnavailable(response.optional_unavailable)
      setStatus(response.status)
      setError('')
    } catch (capabilityError) {
      setError(capabilityError instanceof Error ? capabilityError.message : 'Unable to load capability status')
      setStatus('degraded')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void refresh()
  }, [])

  const value = useMemo(
    () => ({
      loading,
      error,
      status,
      capabilities,
      optionalUnavailable,
      refresh,
      isEnabled: (name: CapabilityName) => capabilities[name]?.enabled ?? false,
    }),
    [capabilities, error, loading, optionalUnavailable, status],
  )

  return <CapabilityContext.Provider value={value}>{children}</CapabilityContext.Provider>
}

export function useCapabilities() {
  const context = useContext(CapabilityContext)
  if (!context) {
    throw new Error('useCapabilities must be used inside CapabilitiesProvider')
  }
  return context
}
