/**
 * Dashboard — the single page of FinPulse V2.
 *
 * Layout:
 * ┌────────────────────────────────────────────────────────────┐
 * │  Header (title, system status)                             │
 * ├────────────────────────────────────────────────────────────┤
 * │  Metric strip (anomalies today, last ingestion, etc.)      │
 * ├────────────────────────────────────────────────────────────┤
 * │  TradingView chart (live price chart for active ticker)    │
 * ├────────────────────────────────────────────────────────────┤
 * │  AnomalyFeed (ticker filter + infinite scroll)  ReportDrawer│
 * └────────────────────────────────────────────────────────────┘
 *
 * V2 additions:
 * - useWebSocket(): invalidates anomaly list on report_ready events
 * - TradingViewChart: embedded live price chart per active ticker
 * - Ticker-aware header badge (from Zustand selectedTicker)
 */

import { useQuery } from "@tanstack/react-query"
import { Activity, Database, Radio, Zap } from "lucide-react"
import { AnomalyFeed } from "@/features/anomalies/AnomalyFeed"
import { ReportDrawer } from "@/features/reports/ReportDrawer"
import { MetricCard } from "@/components/MetricCard"
import { TradingViewChart } from "@/components/TradingViewChart"
import { useUIStore } from "@/app/store"
import { useWebSocket } from "@/lib/useWebSocket"
import { api } from "@/lib/api"
import { HealthSchema, type Health } from "@/lib/schemas"
import { formatTime } from "@/lib/utils"

// ── Health hook ───────────────────────────────────────────────────────────────

function useHealth() {
  return useQuery<Health, Error>({
    queryKey: ["health"],
    queryFn: async () => {
      const { data } = await api.get("/health")
      return HealthSchema.parse(data)
    },
    refetchInterval: 30_000,
  })
}

// ── Header ────────────────────────────────────────────────────────────────────

function Header({ health }: { health: Health | undefined }) {
  const isHealthy = health?.status === "healthy"
  const selectedTicker = useUIStore((s) => s.selectedTicker)
  const displayTicker = selectedTicker ?? "ALL"

  return (
    <header className="flex items-center gap-4 px-6 py-4 border-b border-surface-border bg-surface-card">
      <div className="flex items-center gap-2">
        <Zap size={18} className="text-accent" />
        <span className="text-base font-bold tracking-tight text-slate-100">FinPulse</span>
      </div>

      {/* Active ticker badge */}
      <span className="rounded border border-accent/40 bg-accent-muted px-2 py-0.5 text-[11px] font-bold text-accent tracking-wider">
        {displayTicker}
      </span>

      <span className="text-xs text-muted ml-1">V2 · Z-score + IQR anomaly detection</span>

      {/* System status */}
      <div className="ml-auto flex items-center gap-2">
        <span
          className={`h-2 w-2 rounded-full ${isHealthy ? "bg-green-500 animate-pulse-slow" : "bg-red-500"}`}
        />
        <span className="text-xs text-muted">
          {health ? (isHealthy ? "Systems nominal" : "Degraded") : "Connecting…"}
        </span>
      </div>
    </header>
  )
}

// ── Metric strip ──────────────────────────────────────────────────────────────

function MetricStrip({ health }: { health: Health | undefined }) {
  const selectedTicker = useUIStore((s) => s.selectedTicker)

  return (
    <div className="flex gap-3 px-6 py-4 overflow-x-auto border-b border-surface-border">
      <MetricCard
        label="Anomalies (24h)"
        value={health?.anomalies_24h ?? "—"}
        icon={<Activity size={13} />}
      />
      <MetricCard
        label="Database"
        value={health?.db === "ok" ? "OK" : "Error"}
        sub={health?.db === "ok" ? "TimescaleDB healthy" : "Connection issue"}
        icon={<Database size={13} />}
      />
      <MetricCard
        label="Last Ingestion"
        value={health?.last_ingestion ? formatTime(health.last_ingestion) : "—"}
        sub={`${selectedTicker ?? "All tickers"} · 1m candles`}
        icon={<Radio size={13} />}
      />
      <MetricCard
        label="Detection"
        value="Z + IQR"
        sub="Volume spike + price swing"
        icon={<Zap size={13} />}
      />
    </div>
  )
}

// ── Dashboard ─────────────────────────────────────────────────────────────────

export function Dashboard() {
  const { data: health } = useHealth()
  const selectedTicker = useUIStore((s) => s.selectedTicker)

  // Connect to WebSocket — invalidates ['anomalies'] query on report_ready events.
  useWebSocket()

  return (
    <div className="flex flex-col h-screen bg-surface overflow-hidden">
      <Header health={health} />
      <MetricStrip health={health} />

      {/* Scrollable main content */}
      <main className="flex-1 overflow-y-auto">
        {/* TradingView chart — live price for active ticker */}
        <div className="px-6 pt-5">
          <TradingViewChart ticker={selectedTicker ?? "TSLA"} height={340} />
        </div>

        {/* Anomaly feed with ticker filter + infinite scroll */}
        <div className="px-6 py-5">
          <AnomalyFeed />
        </div>
      </main>

      {/* Report drawer — renders as fixed overlay when open */}
      <ReportDrawer />
    </div>
  )
}
