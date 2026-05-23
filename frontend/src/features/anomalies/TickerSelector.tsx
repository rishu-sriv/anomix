/**
 * TickerSelector — tab-style filter buttons for the anomaly feed.
 *
 * Drives selectedTicker in Zustand (UI state).
 * Tickers match the backend TICKERS env var (TSLA + BTC-USD in V2).
 * "All" maps to null (no filter) in the store.
 */

import { useUIStore } from "@/app/store"
import { cn } from "@/lib/utils"

const TICKERS = ["All", "TSLA", "BTC-USD"] as const
type TickerOption = (typeof TICKERS)[number]

export function TickerSelector() {
  const selectedTicker = useUIStore((s) => s.selectedTicker)
  const setTicker = useUIStore((s) => s.setTicker)

  const active: TickerOption = selectedTicker === null ? "All" : (selectedTicker as TickerOption)

  return (
    <div className="flex gap-1" role="group" aria-label="Filter by ticker">
      {TICKERS.map((t) => (
        <button
          key={t}
          type="button"
          onClick={() => setTicker(t === "All" ? null : t)}
          aria-pressed={active === t}
          className={cn(
            "px-2.5 py-1 rounded text-[11px] font-bold font-mono tracking-wider border",
            "transition-colors duration-150",
            "focus:outline-none focus-visible:ring-2 focus-visible:ring-accent",
            active === t
              ? "bg-accent/20 text-accent border-accent/60"
              : "bg-transparent text-muted border-surface-border hover:border-accent/40 hover:text-slate-300",
          )}
        >
          {t}
        </button>
      ))}
    </div>
  )
}
