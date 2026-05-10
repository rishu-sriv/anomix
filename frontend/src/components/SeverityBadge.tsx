import { cn } from "@/lib/utils"
import type { Severity } from "@/lib/schemas"

interface SeverityBadgeProps {
  severity: Severity
  className?: string
}

const config: Record<Severity, { label: string; classes: string }> = {
  HIGH: {
    label: "HIGH",
    classes:
      "bg-severity-high-bg text-severity-high border border-severity-high/30",
  },
  MEDIUM: {
    label: "MED",
    classes:
      "bg-severity-medium-bg text-severity-medium border border-severity-medium/30",
  },
  LOW: {
    label: "LOW",
    classes:
      "bg-severity-low-bg text-severity-low border border-severity-low/30",
  },
}

export function SeverityBadge({ severity, className }: SeverityBadgeProps) {
  const { label, classes } = config[severity]
  return (
    <span
      className={cn(
        "inline-flex items-center px-2 py-0.5 rounded text-[11px] font-bold tracking-wider font-mono",
        classes,
        className,
      )}
    >
      {label}
    </span>
  )
}
