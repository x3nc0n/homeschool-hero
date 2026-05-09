import { createContext, useContext, useEffect, useMemo, useRef, useState } from 'react'
import { registerSW } from 'virtual:pwa-register'

type BeforeInstallPromptEvent = Event & {
  prompt: () => Promise<void>
  userChoice: Promise<{ outcome: 'accepted' | 'dismissed'; platform: string }>
}

type PwaContextValue = {
  canInstall: boolean
  installApp: () => Promise<void>
  isOfflineReady: boolean
  isOnline: boolean
  needsRefresh: boolean
  dismissOfflineReady: () => void
  applyUpdate: () => Promise<void>
}

const PwaContext = createContext<PwaContextValue | undefined>(undefined)

export function PwaProvider({ children }: { children: React.ReactNode }) {
  const [isOnline, setIsOnline] = useState(() => navigator.onLine)
  const [isOfflineReady, setIsOfflineReady] = useState(false)
  const [needsRefresh, setNeedsRefresh] = useState(false)
  const [installPrompt, setInstallPrompt] = useState<BeforeInstallPromptEvent | null>(null)
  const updateServiceWorker = useRef<((reloadPage?: boolean) => Promise<void>) | null>(null)

  useEffect(() => {
    updateServiceWorker.current = registerSW({
      immediate: true,
      onNeedRefresh() {
        setNeedsRefresh(true)
      },
      onOfflineReady() {
        setIsOfflineReady(true)
      },
    })
  }, [])

  useEffect(() => {
    const handleOnline = () => setIsOnline(true)
    const handleOffline = () => setIsOnline(false)
    const handleBeforeInstallPrompt = (event: Event) => {
      event.preventDefault()
      setInstallPrompt(event as BeforeInstallPromptEvent)
    }
    const handleInstalled = () => setInstallPrompt(null)

    window.addEventListener('online', handleOnline)
    window.addEventListener('offline', handleOffline)
    window.addEventListener('beforeinstallprompt', handleBeforeInstallPrompt)
    window.addEventListener('appinstalled', handleInstalled)

    return () => {
      window.removeEventListener('online', handleOnline)
      window.removeEventListener('offline', handleOffline)
      window.removeEventListener('beforeinstallprompt', handleBeforeInstallPrompt)
      window.removeEventListener('appinstalled', handleInstalled)
    }
  }, [])

  const value = useMemo<PwaContextValue>(
    () => ({
      canInstall:
        Boolean(installPrompt) &&
        !(window.matchMedia('(display-mode: standalone)').matches || (navigator as Navigator & { standalone?: boolean }).standalone),
      installApp: async () => {
        if (!installPrompt) return
        await installPrompt.prompt()
        await installPrompt.userChoice.catch(() => undefined)
        setInstallPrompt(null)
      },
      isOfflineReady,
      isOnline,
      needsRefresh,
      dismissOfflineReady: () => setIsOfflineReady(false),
      applyUpdate: async () => {
        setNeedsRefresh(false)
        await updateServiceWorker.current?.(true)
      },
    }),
    [installPrompt, isOfflineReady, isOnline, needsRefresh],
  )

  return <PwaContext.Provider value={value}>{children}</PwaContext.Provider>
}

export function usePwa() {
  const context = useContext(PwaContext)
  if (!context) {
    throw new Error('usePwa must be used within a PwaProvider')
  }
  return context
}
