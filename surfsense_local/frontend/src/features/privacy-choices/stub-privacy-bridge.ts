import { vi } from "vitest"

import { stubUpdateBridge } from "@/features/updates/stub-bridge"
import type { PrivacyState } from "@/lib/api"

type Overrides = {
  updates?: Partial<PrivacyState["updates"]>
  usageStatistics?: Partial<PrivacyState["usageStatistics"]>
  firstRunAsked?: boolean
}

/**
 * Stands in for window.surfsense.privacy and the updates bridge beside it, the
 * way Electron main answers them: a switch writes the state and pushes it.
 */
export function stubPrivacyBridge(
  overrides: Overrides = {},
  nextReport: object | null = { schema: 1, app_version: "2.2.4" }
) {
  let state: PrivacyState = {
    updates: {
      automatic: false,
      locked: false,
      lockedReason: null,
      channel: null,
      host: "updates.surfsense.com",
      fallbackHost: "github.com",
      lastCheckedAt: null,
      lastRequest: null,
      ...overrides.updates,
    },
    usageStatistics: {
      enabled: null,
      locked: false,
      lockedReason: null,
      host: "usage.surfsense.com",
      lastSent: null,
      ...overrides.usageStatistics,
    },
    firstRunAsked: overrides.firstRunAsked ?? false,
  }
  const updates = stubUpdateBridge({
    automatic: state.updates.automatic,
    state: { status: "idle" },
  })
  const calls = updates.calls
  const listeners = new Set<(state: PrivacyState) => void>()
  const push = (next: PrivacyState) => {
    state = next
    for (const listener of listeners) listener(next)
  }
  const bridge = window.surfsense!
  const setAutomatic = bridge.updates.setAutomatic
  bridge.updates.setAutomatic = async (automatic) => {
    const prefs = await setAutomatic(automatic)
    push({ ...state, updates: { ...state.updates, automatic } })
    return prefs
  }
  bridge.openExternal = vi.fn()
  bridge.privacy = {
    getState: async () => state,
    setUsageStatistics: async (enabled) => {
      calls.push(`usage:${enabled}`)
      push({
        ...state,
        usageStatistics: { ...state.usageStatistics, enabled },
      })
    },
    setUpdatesAutomatic: async (enabled) => {
      await bridge.updates.setAutomatic(enabled)
    },
    previewUsageReport: async () => {
      calls.push("preview")
      return nextReport
    },
    completeFirstRun: async (choices) => {
      calls.push(
        `first-run:updates=${choices.updates},usage=${choices.usageStatistics}`
      )
      // Main stores both answers with the flag, as Settings would.
      push({
        updates: { ...state.updates, automatic: choices.updates },
        usageStatistics: {
          ...state.usageStatistics,
          enabled: choices.usageStatistics,
        },
        firstRunAsked: true,
      })
    },
    onStateChanged: (listener) => {
      listeners.add(listener)
      return () => void listeners.delete(listener)
    },
  }
  return {
    calls,
    push: (next: Overrides) =>
      push({
        updates: { ...state.updates, ...next.updates },
        usageStatistics: { ...state.usageStatistics, ...next.usageStatistics },
        firstRunAsked: next.firstRunAsked ?? state.firstRunAsked,
      }),
  }
}
