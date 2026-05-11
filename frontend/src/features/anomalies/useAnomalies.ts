/**
 * TanStack Query hook for the anomalies list.
 *
 * Polls every 30 seconds (V1 spec). Zod validates the response before
 * it enters the React render cycle — type errors surface at the boundary,
 * not deep in components.
 */

import { useQuery } from "@tanstack/react-query"
import { api } from "@/lib/api"
import { AnomalyListResponseSchema, type AnomalyListResponse } from "@/lib/schemas"

interface UseAnomaliesOptions {
  ticker?: string
  severity?: string
  hours?: number
}

export function useAnomalies(options: UseAnomaliesOptions = {}) {
  const { ticker, severity, hours = 24 } = options

  return useQuery<AnomalyListResponse, Error>({
    queryKey: ["anomalies", { ticker, severity, hours }],
    queryFn: async () => {
      const params: Record<string, string | number> = { hours }
      if (ticker) params.ticker = ticker
      if (severity) params.severity = severity

      const { data } = await api.get("/anomalies", { params })
      return AnomalyListResponseSchema.parse(data)
    },
    // Poll every 30 seconds — V1 polling strategy (no WebSocket yet)
    refetchInterval: 30_000,
  })
}
