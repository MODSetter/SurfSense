import { useEffect } from "react"
import { useQuery, useQueryClient } from "@tanstack/react-query"

import { updatePrefsQueryKey } from "@/features/updates/use-update-state"
import type { PrivacyState, UpdatePrefs } from "@/lib/api"

export const privacyStateQueryKey = ["privacy-state"] as const

// The preload bridge, absent in a bare browser and in the web build.
export function privacyBridge() {
  return typeof window === "undefined" ? undefined : window.surfsense?.privacy
}

/**
 * Where update checks and usage statistics go, what each last sent, and what a
 * policy locks, as Electron main holds them (contract 05, part C). `state` is
 * undefined while it is read and null outside the desktop app; `failed` says
 * the bridge is there but could not answer.
 */
export function usePrivacyState() {
  const privacy = privacyBridge()
  const queryClient = useQueryClient()
  const { data, isError } = useQuery({
    queryKey: privacyStateQueryKey,
    queryFn: async () => (await privacy?.getState()) ?? null,
    enabled: Boolean(privacy),
  })

  useEffect(() => {
    if (!privacy) return
    return privacy.onStateChanged((state) => {
      queryClient.setQueryData(privacyStateQueryKey, state)
      // The same switch the updates bridge reads, so Check now and the sidebar agree.
      queryClient.setQueryData(
        updatePrefsQueryKey,
        (prefs: UpdatePrefs | null | undefined) => ({
          ...prefs,
          automatic: state.updates.automatic,
          lastCheckedAt: state.updates.lastCheckedAt ?? undefined,
        })
      )
    })
  }, [privacy, queryClient])

  const setUsageStatistics = async (enabled: boolean) => {
    if (!privacy) return
    // Moves the switch now; main pushes what it stored.
    queryClient.setQueryData(
      privacyStateQueryKey,
      (state: PrivacyState | null | undefined) =>
        state
          ? {
              ...state,
              usageStatistics: { ...state.usageStatistics, enabled },
            }
          : state
    )
    await privacy.setUsageStatistics(enabled)
    await queryClient.invalidateQueries({ queryKey: privacyStateQueryKey })
  }

  return {
    state: privacy ? data : null,
    failed: Boolean(privacy) && isError,
    setUsageStatistics,
  }
}
