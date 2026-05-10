/**
 * AnomalyFeed — scrollable list of AnomalyCards, polling every 30s.
 *
 * States handled:
 * - Loading (first fetch): skeleton shimmer
 * - Error: red error message with retry hint
 * - Empty: "No anomalies detected" message
 * - Data: list of AnomalyCard components
 */

import { RefreshCw, AlertTriangle, CheckCircle2 } from "lucide-react"
import { AnomalyCard } from "./AnomalyCard"
import { useAnomalies } from "./useAnomalies"

export function AnomalyFeed() {
  const { data, isLoading, isError, error, isFetching } = useAnomalies({ hours: 24 })

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

  const anomalies = data?.data ?? []

  return (
    <div className="flex flex-col gap-1">
      {/* Feed header */}
      <div className="flex items-center gap-2 mb-3">
        <h2 className="text-xs font-bold uppercase tracking-widest text-muted">
          Live Feed
        </h2>
        <span className="text-xs text-muted">— last 24h</span>
        {isFetching && (
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
          <p className="text-xs text-muted opacity-60">Polling every 30 seconds</p>
        </div>
      ) : (
        <div className="flex flex-col gap-2">
          {anomalies.map((anomaly) => (
            <AnomalyCard key={anomaly.id} anomaly={anomaly} />
          ))}
          {data?.has_more && (
            <p className="text-center text-xs text-muted py-2 opacity-60">
              Showing most recent 50 — load more coming in V2
            </p>
          )}
        </div>
      )}
    </div>
  )
}
