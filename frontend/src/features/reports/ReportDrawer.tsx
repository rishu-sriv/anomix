/**
 * ReportDrawer — slide-in panel that shows the AI report for a selected anomaly.
 *
 * States:
 * - Closed (selectedAnomalyId = null): renders nothing
 * - Open + loading first fetch: spinner
 * - Open + pending report: "Generating report…" with pulse animation
 * - Open + completed: full report (summary, reasons, risk level, confidence)
 * - Open + failed: "Report unavailable" error state
 * - Open + 404: anomaly not found
 */

import { X, Loader2, AlertCircle, CheckCircle2, Clock } from "lucide-react"
import { useUIStore } from "@/app/store"
import { useReport } from "./useReport"
import { cn, formatDateTime, round } from "@/lib/utils"
import type { Report } from "@/lib/schemas"

// ── Sub-components ────────────────────────────────────────────────────────────

function ReportContent({ report }: { report: Report }) {
  const riskColor =
    report.risk_level.toLowerCase() === "high"
      ? "text-severity-high"
      : report.risk_level.toLowerCase() === "medium"
        ? "text-severity-medium"
        : "text-severity-low"

  return (
    <div className="flex flex-col gap-5">
      {/* Summary */}
      <section>
        <h3 className="text-[11px] uppercase tracking-widest text-muted mb-2">Summary</h3>
        <p className="text-sm text-slate-300 leading-relaxed">{report.summary}</p>
      </section>

      {/* Reasons */}
      <section>
        <h3 className="text-[11px] uppercase tracking-widest text-muted mb-2">
          Contributing Factors
        </h3>
        <ul className="flex flex-col gap-2">
          {report.reasons.map((reason, i) => (
            <li key={i} className="flex gap-2 text-sm text-slate-300">
              <span className="text-accent mt-0.5 shrink-0">›</span>
              <span className="leading-relaxed">{reason}</span>
            </li>
          ))}
        </ul>
      </section>

      {/* Metrics row */}
      <section className="grid grid-cols-2 gap-3">
        <div className="rounded-md border border-surface-border bg-surface p-3">
          <div className="text-[11px] uppercase tracking-widest text-muted mb-1">Risk Level</div>
          <div className={cn("text-base font-bold font-mono", riskColor)}>
            {report.risk_level}
          </div>
        </div>
        <div className="rounded-md border border-surface-border bg-surface p-3">
          <div className="text-[11px] uppercase tracking-widest text-muted mb-1">Confidence</div>
          <div className="text-base font-bold font-mono text-slate-100">
            {round(report.confidence * 100, 0)}%
          </div>
        </div>
      </section>

      {/* Footer meta */}
      <div className="flex items-center gap-3 text-xs text-muted border-t border-surface-border pt-3">
        <span className="flex items-center gap-1">
          <Clock size={11} />
          {formatDateTime(report.created_at)}
        </span>
        {report.tokens_used > 0 && (
          <span className="ml-auto">{report.tokens_used.toLocaleString()} tokens</span>
        )}
        {report.tokens_used === 0 && (
          <span className="ml-auto opacity-50">mock report (V1)</span>
        )}
      </div>
    </div>
  )
}

// ── Main drawer ───────────────────────────────────────────────────────────────

export function ReportDrawer() {
  const { selectedAnomalyId, isDrawerOpen, closeDrawer } = useUIStore()
  const { data, isLoading, isError, error } = useReport(selectedAnomalyId)

  if (!isDrawerOpen || !selectedAnomalyId) return null

  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-black/40 z-40"
        onClick={closeDrawer}
        aria-hidden="true"
      />

      {/* Drawer panel */}
      <aside
        role="dialog"
        aria-label="Anomaly report"
        className={cn(
          "fixed top-0 right-0 h-full w-full max-w-md z-50",
          "bg-surface-card border-l border-surface-border",
          "flex flex-col shadow-2xl",
          "transition-transform duration-300",
        )}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-surface-border shrink-0">
          <h2 className="text-sm font-bold tracking-wide text-slate-100">
            Anomaly Report
          </h2>
          <button
            type="button"
            onClick={closeDrawer}
            className={cn(
              "rounded p-1 text-muted hover:text-slate-200 hover:bg-surface-elevated",
              "transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-accent",
            )}
            aria-label="Close report"
          >
            <X size={16} />
          </button>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto px-5 py-5">
          {/* Loading state */}
          {isLoading && (
            <div className="flex flex-col items-center justify-center gap-3 py-16">
              <Loader2 size={28} className="text-accent animate-spin" />
              <p className="text-sm text-muted">Fetching report…</p>
            </div>
          )}

          {/* Error state */}
          {isError && (
            <div className="flex flex-col items-center gap-2 py-16 text-center">
              <AlertCircle size={28} className="text-severity-high" />
              <p className="text-sm text-severity-high">Failed to load report</p>
              <p className="text-xs text-muted">{error?.message}</p>
            </div>
          )}

          {/* Pending state */}
          {data && "status" in data && data.status === "pending" && (
            <div className="flex flex-col items-center gap-3 py-16 text-center">
              <Loader2 size={28} className="text-amber-400 animate-spin" />
              <p className="text-sm text-amber-400">Generating report…</p>
              <p className="text-xs text-muted">Checking every 5 seconds</p>
            </div>
          )}

          {/* Failed state */}
          {data && "status" in data && data.status === "failed" && (
            <div className="flex flex-col items-center gap-2 py-16 text-center">
              <AlertCircle size={28} className="text-severity-high opacity-70" />
              <p className="text-sm text-slate-300">Report Unavailable</p>
              <p className="text-xs text-muted">
                Report generation failed. The anomaly has been recorded.
              </p>
            </div>
          )}

          {/* Completed report */}
          {data && !("status" in data) && (
            <>
              <div className="flex items-center gap-2 mb-5 pb-4 border-b border-surface-border">
                <CheckCircle2 size={14} className="text-green-400" />
                <span className="text-xs text-green-400 uppercase tracking-wider">
                  Analysis complete
                </span>
              </div>
              <ReportContent report={data} />
            </>
          )}
        </div>
      </aside>
    </>
  )
}
