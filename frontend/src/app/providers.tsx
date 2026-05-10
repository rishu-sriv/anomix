/**
 * App-level providers — wrap the entire component tree.
 *
 * TanStack Query is configured here:
 * - staleTime: 25s (data is "fresh" for 25s before refetch)
 * - retry: 2 (network blips shouldn't crash the UI)
 * - refetchOnWindowFocus: false (prevents jarring refetches when switching tabs)
 *
 * DevTools are included in development builds only.
 */

import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import type { ReactNode } from "react"

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 25_000,
      retry: 2,
      refetchOnWindowFocus: false,
    },
  },
})

interface ProvidersProps {
  children: ReactNode
}

export function Providers({ children }: ProvidersProps) {
  return (
    <QueryClientProvider client={queryClient}>
      {children}
    </QueryClientProvider>
  )
}
