import { useRef, useState } from 'react'
import { RefreshCcw } from 'lucide-react'

const TRIGGER_DISTANCE = 72

export function PullToRefresh({
  children,
  onRefresh,
}: {
  children: React.ReactNode
  onRefresh: () => Promise<void> | void
}) {
  const startY = useRef<number | null>(null)
  const refreshing = useRef(false)
  const [distance, setDistance] = useState(0)

  return (
    <div
      onTouchStart={(event) => {
        if (window.scrollY > 0 || refreshing.current) return
        startY.current = event.touches[0]?.clientY ?? null
      }}
      onTouchMove={(event) => {
        if (startY.current == null || window.scrollY > 0 || refreshing.current) return
        const nextDistance = Math.max(0, (event.touches[0]?.clientY ?? 0) - startY.current)
        setDistance(Math.min(nextDistance, TRIGGER_DISTANCE))
      }}
      onTouchEnd={() => {
        const shouldRefresh = distance >= TRIGGER_DISTANCE
        startY.current = null
        setDistance(0)
        if (!shouldRefresh || refreshing.current) return
        refreshing.current = true
        Promise.resolve(onRefresh()).finally(() => {
          refreshing.current = false
        })
      }}
    >
      <div className="flex items-center justify-center overflow-hidden text-xs text-muted-foreground transition-[height,opacity] duration-150" style={{ height: distance, opacity: distance ? 1 : 0 }}>
        <RefreshCcw className="mr-2 h-3.5 w-3.5" />
        Pull to refresh
      </div>
      {children}
    </div>
  )
}
