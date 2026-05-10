import { cn } from "@/lib/utils"
import type { ReactNode } from "react"

interface MetricCardProps {
  label: string
  value: ReactNode
  sub?: string
  /** Optional Lucide icon component */
  icon?: ReactNode
  className?: string
}

export function MetricCard({ label, value, sub, icon, className }: MetricCardProps) {
  return (
    <div
      className={cn(
        "rounded-lg border border-surface-border bg-surface-card px-4 py-3",
        "flex flex-col gap-1 min-w-[140px]",
        className,
      )}
    >
      <div className="flex items-center gap-2 text-muted text-xs uppercase tracking-widest">
        {icon && <span className="opacity-60">{icon}</span>}
        {label}
      </div>
      <div className="text-2xl font-bold text-slate-100 leading-none">{value}</div>
      {sub && <div className="text-xs text-muted">{sub}</div>}
    </div>
  )
}
