/**
 * TanStack Query hook for the anomalies list — V2: useInfiniteQuery with cursor pagination.
 *
 * Polls every 30 seconds as a safety net (WebSocket invalidates immediately on new anomalies).
 * Zod validates every page response before it enters the React render cycle.
 *
 * Pagination: keyset cursor (UUID of last anomaly in previous page).
 * TanStack Query v5 refetches only the first page on interval/invalidation —
 * new anomalies appear at the top; deeper pages remain cached.
 */

import { useInfiniteQuery } from "@tanstack/react-query"
import { api } from "@/lib/api"
import { AnomalyListResponseSchema, type AnomalyListResponse } from "@/lib/schemas"

interface UseAnomaliesOptions {
  ticker?: string
  severity?: string
  hours?: number
}

export function useAnomalies(options: UseAnomaliesOptions = {}) {
  const { ticker, severity, hours = 24 } = options

  return useInfiniteQuery<AnomalyListResponse, Error>({
    queryKey: ["anomalies", { ticker, severity, hours }],
    queryFn: async ({ pageParam }) => {
      const params: Record<string, string | number> = { hours }
      if (ticker) params.ticker = ticker
      if (severity) params.severity = severity
      if (pageParam) params.cursor = pageParam as string

      const { data } = await api.get("/anomalies", { params })
      return AnomalyListResponseSchema.parse(data)
    },
    initialPageParam: undefined as string | undefined,
    getNextPageParam: (lastPage) => lastPage.next_cursor ?? undefined,
    // Poll every 30 seconds — fallback when WebSocket is disconnected.
    // On WS reconnect/message, queryClient.invalidateQueries fires immediately.
    refetchInterval: 30_000,
  })
}
