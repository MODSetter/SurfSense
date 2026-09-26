import { askEgress } from "@/features/egress/ask-egress"

import { updatesBridge, useUpdatePrefs } from "./use-update-state"

/**
 * The one way to check: Settings › About, the sidebar's update row and the app
 * menu. Checking asks github.com, and Settings › Network promises that call is
 * refused until allowed, so while update checks are off it asks first.
 */
export function useCheckForUpdates() {
  const { prefs, setAutomatic } = useUpdatePrefs()
  return async () => {
    const updates = updatesBridge()
    if (!updates) return
    const current = prefs ?? (await updates.prefs())
    if (current.automatic) return void updates.check()
    const allowed = await askEgress({
      destination: "app_updates",
      host: "github.com",
      allow: () => setAutomatic(true),
    })
    if (allowed) await updates.check()
  }
}
