import { useEffect, useState } from "react"
import { useQuery, useQueryClient } from "@tanstack/react-query"

import type { UpdatePrefs, UpdateState } from "@/lib/api"

const IDLE: UpdateState = { status: "idle" }

export const updatePrefsQueryKey = ["update-prefs"] as const

// The preload bridge, absent in a bare browser and in the web build.
export function updatesBridge() {
  return typeof window === "undefined" ? undefined : window.surfsense?.updates
}

export function useUpdateState() {
  const [state, setState] = useState<UpdateState>(IDLE)
  useEffect(() => {
    const updates = updatesBridge()
    if (!updates) return
    // An event that lands while the first read is in flight is the newer truth.
    let pushed = false
    const unsubscribe = updates.onState((state) => {
      pushed = true
      setState(state)
    })
    void updates.state().then((state) => {
      if (!pushed) setState(state)
    })
    return unsubscribe
  }, [])
  return state
}

/**
 * Whether reaching github.com is allowed, and the switch that changes it.
 *
 * Shared rather than read per component: the sidebar outlives the Settings
 * dialog, so a pref it read once at mount would still claim consent the user
 * has since withdrawn. `null` until read, and forever outside the desktop app.
 */
export function useUpdatePrefs() {
  const updates = updatesBridge()
  const queryClient = useQueryClient()
  const { data } = useQuery({
    queryKey: updatePrefsQueryKey,
    queryFn: () => updates?.prefs() ?? null,
    enabled: Boolean(updates),
  })
  return {
    prefs: data ?? null,
    setAutomatic: async (automatic: boolean) => {
      if (!updates) return
      // Moves the checkbox now; the write below settles what was stored.
      queryClient.setQueryData(
        updatePrefsQueryKey,
        (prefs: UpdatePrefs | null | undefined) => ({ ...prefs, automatic })
      )
      queryClient.setQueryData(
        updatePrefsQueryKey,
        await updates.setAutomatic(automatic)
      )
    },
  }
}
