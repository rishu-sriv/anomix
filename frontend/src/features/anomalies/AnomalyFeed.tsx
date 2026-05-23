/**
 * AnomalyFeed — scrollable list of AnomalyCards.
 *
 * V2 changes:
 * - Ticker filter via TickerSelector (drives Zustand selectedTicker)
 * - Infinite scroll via IntersectionObserver + useInfiniteQuery
 * - WebSocket invalidation handled in Dashboard (useWebSocket hook)
 *
 * States handled:
 * - Loading (first fetch): skeleton shimmer
 * - Error: red error message with retry hint
 * - Empty: "No anomalies detected" message
 * - Data: list of AnomalyCard components with load-more sentinel
 */

import { useEffect, useRef } from "react"
import { RefreshCw, AlertTriangle, CheckCircle2 } from "lucide-react"
import { AnomalyCard } from "./AnomalyCard"
import { TickerSelector } from "./TickerSelector"
import { useAnomalies } from "./useAnomalies"
import { useUIStore } from "@/app/store"

export function AnomalyFeed() {
  const selectedTicker = useUIStore((s) => s.selectedTicker)

  const {
    data,
    isLoading,
    isError,
    error,
    isFetching,
    fetchNextPage,
    hasNextPage,
    isFetchingNextPage,
  } = useAnomalies({
    hours: 24,
    ticker: selectedTicker ?? undefined,
  })

  // Infinite scroll sentinel
  const sentinelRef = useRef<HTMLDivElement>(null)
  useEffect(() => {
    const el = sentinelRef.current
    if (!el) return
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting && hasNextPage && !isFetchingNextPage) {
          void fetchNextPage()
        }
      },
      { threshold: 0.1 },
    )
    observer.observe(el)
    return () => observer.disconnect()
  }, [hasNextPage, isFetchingNextPage, fetchNextPage])

  if (isLoading) {
    return (
      <div className="flex flex-col gap-3">
        {Array.from({ length: 4 }).map((_, i) => (
          <div
            key={i}
            className="h-24 rounded-lg border border-surface-border bg-surface-card animate-pulse"
          />
        ))}
      </div>
    )
  }

  if (isError) {
    return (
      <div className="flex flex-col items-center justify-center gap-2 py-16 text-center">
        <AlertTriangle size={32} className="text-severity-high opacity-70" />
        <p className="text-sm text-severity-high">Failed to load anomalies</p>
        <p className="text-xs text-muted">{error?.message}</p>
        <p className="text-xs text-muted mt-1">Retrying automatically…</p>
      </div>
    )
  }

  const anomalies = data?.pages.flatMap((p) => p.data) ?? []

  return (
    <div className="flex flex-col gap-1">
      {/* Feed header */}
      <div className="flex items-center gap-2 mb-3">
        <h2 className="text-xs font-bold uppercase tracking-widest text-muted">
          Live Feed
        </h2>
        <span className="text-xs text-muted">— last 24h</span>

        <TickerSelector />

        {isFetching && !isFetchingNextPage && (
          <RefreshCw size={11} className="ml-auto text-accent animate-spin" />
        )}
        {!isFetching && (
          <span className="ml-auto flex items-center gap-1 text-xs text-green-400">
            <CheckCircle2 size={11} />
            live
          </span>
        )}
      </div>

      {anomalies.length === 0 ? (
        <div className="flex flex-col items-center justify-center gap-2 py-16 text-center">
          <CheckCircle2 size={32} className="text-severity-low opacity-50" />
          <p className="text-sm text-muted">No anomalies detected in the last 24h</p>
          <p className="text-xs text-muted opacity-60">Polling every 30 seconds · live via WebSocket</p>
        </div>
      ) : (
        <div className="flex flex-col gap-2">
          {anomalies.map((anomaly) => (
            <AnomalyCard key={anomaly.id} anomaly={anomaly} />
          ))}

          {/* Infinite scroll sentinel */}
          <div ref={sentinelRef} className="py-2 flex justify-center">
            {isFetchingNextPage && (
              <RefreshCw size={14} className="text-accent animate-spin" />
            )}
            {!hasNextPage && anomalies.length > 0 && (
              <p className="text-xs text-muted opacity-40">All anomalies loaded</p>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
