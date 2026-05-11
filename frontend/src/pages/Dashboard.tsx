/**
 * Dashboard — the single page of FinPulse V1.
 *
 * Layout:
 * ┌────────────────────────────────────────────────────────┐
 * │  Header (title, ticker badge, health indicator)        │
 * ├────────────────────────────────────────────────────────┤
 * │  Metric strip (anomalies today, last ingestion, etc.)  │
 * ├────────────────────────────────────────────────────────┤
 * │  AnomalyFeed (scrollable, 30s polling)                 │
 * │                                          ReportDrawer  │
 * └────────────────────────────────────────────────────────┘
 */

import { useQuery } from "@tanstack/react-query"
import { Activity, Database, Radio, Zap } from "lucide-react"
import { AnomalyFeed } from "@/features/anomalies/AnomalyFeed"
import { ReportDrawer } from "@/features/reports/ReportDrawer"
import { MetricCard } from "@/components/MetricCard"
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
  return (
    <header className="flex items-center gap-4 px-6 py-4 border-b border-surface-border bg-surface-card">
      <div className="flex items-center gap-2">
        <Zap size={18} className="text-accent" />
        <span className="text-base font-bold tracking-tight text-slate-100">FinPulse</span>
      </div>

      {/* Ticker badge */}
      <span className="rounded border border-accent/40 bg-accent-muted px-2 py-0.5 text-[11px] font-bold text-accent tracking-wider">
        TSLA
      </span>

      <span className="text-xs text-muted ml-1">V1 · Z-score anomaly detection</span>

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
        sub="TSLA · 1m candles"
        icon={<Radio size={13} />}
      />
      <MetricCard
        label="Ticker"
        value="TSLA"
        sub="Tesla Inc."
        icon={<Zap size={13} />}
      />
    </div>
  )
}

// ── Dashboard ─────────────────────────────────────────────────────────────────

export function Dashboard() {
  const { data: health } = useHealth()

  return (
    <div className="flex flex-col h-screen bg-surface overflow-hidden">
      <Header health={health} />
      <MetricStrip health={health} />

      {/* Main content: anomaly feed */}
      <main className="flex-1 overflow-y-auto px-6 py-5">
        <AnomalyFeed />
      </main>

      {/* Report drawer — renders as fixed overlay when open */}
      <ReportDrawer />
    </div>
  )
}
