/**
 * TanStack Query hook for a single report.
 *
 * Polling behaviour:
 * - If report_status is "pending", poll every 5 seconds until completed/failed.
 * - Once the report is completed or failed, stop polling (refetchInterval=false).
 *
 * The hook is disabled when anomalyId is null (drawer closed).
 */

import { useQuery } from "@tanstack/react-query"
import { api } from "@/lib/api"
import { ReportResponseSchema, type ReportResponse } from "@/lib/schemas"

export function useReport(anomalyId: string | null) {
  return useQuery<ReportResponse, Error>({
    queryKey: ["report", anomalyId],
    queryFn: async () => {
      const { data } = await api.get(`/reports/${anomalyId}`)
      return ReportResponseSchema.parse(data)
    },
    enabled: anomalyId !== null,
    // Poll every 5s while pending; stop once the report settles
    refetchInterval: (query) => {
      const d = query.state.data
      if (!d) return false
      if ("status" in d && d.status === "pending") return 5_000
      return false
    },
  })
}
