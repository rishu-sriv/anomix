/**
 * AnomalyCard — clickable card for a single detected anomaly.
 *
 * Clicking opens the ReportDrawer for this anomaly (via Zustand).
 * Shows: ticker, severity, anomaly type, Z-score, IQR flag (V2), time, report status.
 */

import { Activity, FileText, Clock, TrendingUp } from "lucide-react"
import { SeverityBadge } from "@/components/SeverityBadge"
import { useUIStore } from "@/app/store"
import { cn, timeAgo, round } from "@/lib/utils"
import type { Anomaly } from "@/lib/schemas"

const REPORT_STATUS_LABEL: Record<string, { label: string; color: string }> = {
  pending: { label: "generating…", color: "text-amber-400" },
  completed: { label: "report ready", color: "text-green-400" },
  failed: { label: "report failed", color: "text-red-400" },
}

interface AnomalyCardProps {
  anomaly: Anomaly
}

export function AnomalyCard({ anomaly }: AnomalyCardProps) {
  const openDrawer = useUIStore((s) => s.openDrawer)
  const selectedId = useUIStore((s) => s.selectedAnomalyId)
  const isSelected = selectedId === anomaly.id

  const reportMeta = REPORT_STATUS_LABEL[anomaly.report_status]

  return (
    <button
      type="button"
      onClick={() => openDrawer(anomaly.id)}
      className={cn(
        "w-full text-left rounded-lg border bg-surface-card px-4 py-3",
        "transition-colors duration-150 hover:bg-surface-elevated",
        "focus:outline-none focus-visible:ring-2 focus-visible:ring-accent",
        isSelected
          ? "border-accent/60 bg-surface-elevated"
          : "border-surface-border",
      )}
    >
      {/* Top row: ticker + severity + type */}
      <div className="flex items-center gap-2 mb-2">
        <span className="text-sm font-bold text-slate-100">{anomaly.ticker}</span>
        <SeverityBadge severity={anomaly.severity} />
        <span className="ml-auto text-xs text-muted capitalize font-mono">
          {anomaly.type.replace("_", " ")}
        </span>
      </div>

      {/* Middle row: Z-score + optional IQR flag */}
      <div className="flex items-center gap-4 mb-2">
        <div className="flex items-center gap-2">
          <Activity size={13} className="text-accent opacity-70" />
          <span className="text-xs text-muted">Z-score</span>
          <span
            className={cn(
              "font-mono text-sm font-semibold",
              anomaly.severity === "HIGH" ? "text-severity-high" : "text-severity-medium",
            )}
          >
            {anomaly.zscore !== null ? `+${round(anomaly.zscore, 2)}σ` : "—"}
          </span>
        </div>

        {anomaly.iqr_flag && (
          <div className="flex items-center gap-1">
            <TrendingUp size={12} className="text-amber-400" />
            <span className="text-[11px] text-amber-400 font-mono">price swing</span>
          </div>
        )}
      </div>

      {/* Bottom row: time + report status */}
      <div className="flex items-center gap-3 text-xs text-muted">
        <span className="flex items-center gap-1">
          <Clock size={11} />
          {timeAgo(anomaly.detected_at)}
        </span>
        <span className={cn("flex items-center gap-1 ml-auto", reportMeta.color)}>
          <FileText size={11} />
          {reportMeta.label}
        </span>
      </div>
    </button>
  )
}
