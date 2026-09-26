import { useQueryClient } from "@tanstack/react-query"

/**
 * Every model query sits under this key, so one change refreshes every view of
 * model data at once: settings, onboarding and the composer's picker.
 */
export const MODELS_QUERY_KEY = ["models"] as const

export function useRefreshModels() {
  const queryClient = useQueryClient()
  return () => queryClient.invalidateQueries({ queryKey: MODELS_QUERY_KEY })
}
