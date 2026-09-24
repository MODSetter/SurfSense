type DashboardModule = typeof import("@/features/dashboard/dashboard-page")

export type DashboardComponent = DashboardModule["DashboardPage"]

let loading: Promise<DashboardComponent> | null = null

/**
 * The dashboard's code, fetched once and shared. Startup waits for it together
 * with its data, so the app turns ready with the dashboard already loaded and
 * never shows a second loader for the chunk. A failed load is forgotten, so
 * Retry fetches it again rather than replaying the failure.
 */
export function loadDashboard(): Promise<DashboardComponent> {
  loading ??= import("@/features/dashboard/dashboard-page").then(
    (module) => module.DashboardPage,
    (error: unknown) => {
      loading = null
      throw error
    }
  )
  return loading
}
