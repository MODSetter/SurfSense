import { askEgress } from "@/features/egress/ask-egress"
import { privacyBridge } from "@/features/privacy-choices/use-privacy-state"

import { updatesBridge, useUpdatePrefs } from "./use-update-state"

// SurfSense's feed, where a check goes unless an admin policy names a mirror.
const UPDATE_HOST = "updates.surfsense.com"

/**
 * The one way to check: Settings › About, the sidebar's update row and the app
 * menu. Settings › Network promises a check is refused until allowed, so while
 * update checks are off it asks first, naming where the check goes.
 */
export function useCheckForUpdates() {
  const { prefs, setAutomatic } = useUpdatePrefs()
  return async () => {
    const updates = updatesBridge()
    if (!updates) return
    const privacy = (await privacyBridge()?.getState()) ?? null
    // A policy that turned updates off leaves nothing to ask or check.
    if (privacy?.updates.locked) return
    const current = prefs ?? (await updates.prefs())
    if (current.automatic) return void updates.check()
    const allowed = await askEgress({
      destination: "app_updates",
      host: privacy?.updates.host ?? UPDATE_HOST,
      // A mirror has no GitHub fallback, so its question says so.
      purpose:
        privacy?.updates.fallbackHost === null ? "update_mirror" : undefined,
      allow: () => setAutomatic(true),
    })
    if (allowed) await updates.check()
  }
}
