import { askEgress } from "@/features/egress/ask-egress"
import { privacyBridge } from "@/features/privacy-choices/use-privacy-state"

import { updatesBridge, useUpdatePrefs } from "./use-update-state"

// SurfSense's feed, where a check goes unless an admin policy names a mirror.
const UPDATE_HOST = "updates.surfsense.com"
// Where an Electron main from before the privacy bridge reads releases.
const GITHUB_HOST = "github.com"

/**
 * The one way to check: Settings › About, the sidebar's update row and the app
 * menu. Settings › Network promises a check is refused until allowed, so while
 * update checks are off it asks first, naming where the check goes. Resolves
 * to whether a check was started.
 */
export function useCheckForUpdates() {
  const { prefs, setAutomatic } = useUpdatePrefs()
  return async (): Promise<boolean> => {
    const updates = updatesBridge()
    if (!updates) return false
    const bridge = privacyBridge()
    const privacy = bridge ? await bridge.getState().catch(() => null) : null
    // A policy that turned updates off leaves nothing to ask or check.
    if (privacy?.updates.locked) return false
    const current = prefs ?? (await updates.prefs())
    if (current.automatic) {
      await updates.check()
      return true
    }
    const allowed = await askEgress({
      destination: "app_updates",
      host: bridge ? (privacy?.updates.host ?? UPDATE_HOST) : GITHUB_HOST,
      // A mirror has no GitHub fallback; a main without the bridge reads GitHub alone.
      purpose: !bridge
        ? "github_releases"
        : privacy?.updates.fallbackHost === null
          ? "update_mirror"
          : undefined,
      allow: () => setAutomatic(true),
    })
    if (allowed) await updates.check()
    return allowed
  }
}
