import type { BackupStatus } from '@/types/api'

export type ServiceHealthLevel = 'healthy' | 'degraded' | 'unhealthy' | 'not_configured'

export interface ServiceHealthStatus {
  name: string
  label: string
  required: boolean
  configured: boolean
  status: ServiceHealthLevel
  message: string
  checked_at: string
  response_time_ms?: number | null
  details: Record<string, unknown>
}

export interface DetailedHealthResponse {
  status: 'healthy' | 'degraded' | 'unhealthy'
  ready: boolean
  checked_at: string
  services: Record<string, ServiceHealthStatus>
  summary: {
    healthy: number
    degraded: number
    unhealthy: number
    not_configured: number
  }
  backup?: BackupStatus | null
  transport?: {
    tls_enabled: boolean
    https_redirect_enabled: boolean
    hsts_enabled: boolean
  }
  maintenance?: Record<string, unknown>
}

export interface ReadinessResponse {
  status: 'ready' | 'not_ready'
  ready: boolean
  checked_at: string
  checks: Record<string, string>
}

export interface SystemStatusResponse extends DetailedHealthResponse {
  version: string
  started_at: string
  uptime_seconds: number
  uptime_human: string
  disk: {
    path: string
    total_bytes: number
    used_bytes: number
    free_bytes: number
    used_percent: number
    warning_threshold_percent: number
    critical_threshold_percent: number
    status: Exclude<ServiceHealthLevel, 'not_configured'>
  }
}
