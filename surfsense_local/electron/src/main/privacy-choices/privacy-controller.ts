import {
  updatesLockReason,
  usageLockReason,
  type UpdatesLockReason,
  type UsageLockReason,
} from "../admin-policy/policy-locks.ts"
import type { AdminPolicy } from "../admin-policy/read-policy.ts"
import type { InstallChannel } from "../install-channel/install-channel.ts"
import type { ManifestRequest } from "../update-feed/latest-manifest.ts"
import type { UpdatePrefs } from "../updater.ts"
import type { PrivacyStore } from "../usage-statistics/privacy-file.ts"
import type { UsageReporter } from "../usage-statistics/usage-reporter.ts"

/** window.surfsense.privacy.getState() (contract 05, part C). */
export type PrivacyState = {
  updates: {
    automatic: boolean
    locked: boolean
    lockedReason: UpdatesLockReason | null
    /** The package manager that owns updates; null unless that is the lock. */
    channel: InstallChannel | null
    host: string
    fallbackHost: "github.com" | null
    lastCheckedAt: string | null
    lastRequest: ManifestRequest | null
  }
  usageStatistics: {
    enabled: boolean | null
    locked: boolean
    lockedReason: UsageLockReason | null
    host: string
    lastSent: { at: string; body: object } | null
  }
  firstRunAsked: boolean
}

export type FirstRunChoices = { updates: boolean; usageStatistics: boolean }

export type PrivacyController = {
  state(): PrivacyState
  /** updates.json as the older updates bridge reads it; a lock reads as off. */
  updatePrefs(): UpdatePrefs
  setUpdatesAutomatic(enabled: boolean): UpdatePrefs
  setUsageStatistics(enabled: boolean): void
  previewUsageReport(): Promise<object | null>
  completeFirstRun(choices: FirstRunChoices): void
  /** Tell the window something it shows has changed elsewhere: a check, a request, a report. */
  changed(): void
}

/**
 * The user's choices about updates and usage statistics, with what the admin
 * policy or a package manager forces.
 */
export function createPrivacyController(deps: {
  policy: AdminPolicy
  installChannel: InstallChannel | null
  store: PrivacyStore
  readUpdatePrefs: () => UpdatePrefs
  writeUpdatePrefs: (prefs: UpdatePrefs) => void
  updates: { host: string; fallbackHost: "github.com" | null }
  lastRequest: () => ManifestRequest | null
  usageHost: string
  reporter: Pick<UsageReporter, "preview" | "nudge">
  /** Run today's automatic check if it is due: the first-run yes is a launch's worth of consent. */
  checkIfDue: () => void
  onChange: (state: PrivacyState) => void
  log?: (line: string) => void
}): PrivacyController {
  const log = deps.log ?? (() => undefined)
  const updatesLock = updatesLockReason(deps.policy, deps.installChannel)
  const updatesOff = updatesLock !== null
  const usageLock = usageLockReason(deps.policy)

  const updatePrefs = (): UpdatePrefs => {
    const prefs = deps.readUpdatePrefs()
    return updatesOff ? { ...prefs, automatic: false } : prefs
  }

  const state = (): PrivacyState => {
    const prefs = updatePrefs()
    const file = deps.store.read()
    return {
      updates: {
        automatic: prefs.automatic,
        locked: updatesOff,
        lockedReason: updatesLock,
        channel: updatesLock === "channel" ? deps.installChannel : null,
        host: deps.updates.host,
        fallbackHost: deps.updates.fallbackHost,
        lastCheckedAt: prefs.lastCheckedAt ?? null,
        lastRequest: deps.lastRequest(),
      },
      usageStatistics: {
        enabled: usageLock === null ? file.usageStatistics : false,
        locked: usageLock !== null,
        lockedReason: usageLock,
        host: deps.usageHost,
        lastSent: file.lastSent,
      },
      firstRunAsked: file.firstRunAsked,
    }
  }

  const changed = () => deps.onChange(state())

  const applyUpdates = (enabled: boolean): boolean => {
    if (updatesOff) return false
    deps.writeUpdatePrefs({ ...deps.readUpdatePrefs(), automatic: enabled })
    log(`automatic update checks ${enabled ? "on" : "off"}`)
    return enabled
  }

  const applyUsage = (enabled: boolean): boolean => {
    if (usageLock !== null) return false
    deps.store.update((file) => ({ ...file, usageStatistics: enabled }))
    log(`usage statistics ${enabled ? "on" : "off"}`)
    return enabled
  }

  return {
    state,
    updatePrefs,
    setUpdatesAutomatic(enabled) {
      applyUpdates(enabled === true)
      changed()
      return updatePrefs()
    },
    setUsageStatistics(enabled) {
      if (applyUsage(enabled === true)) deps.reporter.nudge()
      changed()
    },
    previewUsageReport: () => deps.reporter.preview(),
    completeFirstRun(choices) {
      const updates = applyUpdates(choices.updates === true)
      const usage = applyUsage(choices.usageStatistics === true)
      deps.store.update((file) => ({ ...file, firstRunAsked: true }))
      changed()
      if (updates) deps.checkIfDue()
      if (usage) deps.reporter.nudge()
    },
    changed,
  }
}
