import type { UpdatesLockReason } from "../admin-policy/policy-locks.ts"
import type { InstallChannel } from "../install-channel/install-channel.ts"
import type { UpdatePrefs, Updates } from "../updater.ts"

export type CheckKind = "automatic" | "manual"

/**
 * One update check, automatic or Check now: refused while a policy turns updates
 * off or a package manager owns them, otherwise stamped as Settings' "last call" and run. Check now ignores the
 * daily limit, which only automatic checks keep. Resolves true once a manifest
 * was read.
 */
export function updateCheckRunner(deps: {
  locked: UpdatesLockReason | null
  /** Named in the log when the channel is the lock. */
  channel?: InstallChannel | null
  updates: Pick<Updates, "check">
  readPrefs: () => UpdatePrefs
  writePrefs: (prefs: UpdatePrefs) => void
  now?: () => Date
  log?: (line: string) => void
  onChecked?: () => void
}): (kind: CheckKind) => Promise<boolean> {
  const now = deps.now ?? (() => new Date())
  const log = deps.log ?? (() => undefined)
  return async (kind) => {
    if (deps.locked) {
      const reason =
        deps.locked === "channel" ? `updates come from ${deps.channel}` : "turned off by policy"
      log(`${kind} check not run: ${reason}`)
      return false
    }
    deps.writePrefs({ ...deps.readPrefs(), lastCheckedAt: now().toISOString() })
    log(`${kind} check`)
    deps.onChecked?.()
    return deps.updates.check()
  }
}
