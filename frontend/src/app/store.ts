/**
 * Zustand store — UI state ONLY.
 *
 * Rule: server state (anomaly list, report data) lives in TanStack Query.
 * This store owns only ephemeral UI state: which drawer is open, which
 * anomaly is selected.
 */

import { create } from "zustand"

interface UIState {
  /** ID of the anomaly whose report drawer is open, or null if closed. */
  selectedAnomalyId: string | null
  isDrawerOpen: boolean

  /** Open the report drawer for a given anomaly. */
  openDrawer: (anomalyId: string) => void
  /** Close the report drawer and clear the selection. */
  closeDrawer: () => void
}

export const useUIStore = create<UIState>((set) => ({
  selectedAnomalyId: null,
  isDrawerOpen: false,

  openDrawer: (anomalyId) =>
    set({ selectedAnomalyId: anomalyId, isDrawerOpen: true }),

  closeDrawer: () =>
    set({ selectedAnomalyId: null, isDrawerOpen: false }),
}))
