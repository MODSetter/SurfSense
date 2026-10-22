import type { UpdatePrefs, Updates } from "../updater.ts"

export type CheckKind = "automatic" | "manual"

/**
 * One update check, automatic or Check now: refused while a policy turns updates
 * off, otherwise stamped as Settings' "last call" and run. Check now ignores the
 * daily limit, which only automatic checks keep.
 */
export function updateCheckRunner(deps: {
  locked: boolean
  updates: Pick<Updates, "check">
  readPrefs: () => UpdatePrefs
  writePrefs: (prefs: UpdatePrefs) => void
  now?: () => Date
  log?: (line: string) => void
  onChecked?: () => void
}): (kind: CheckKind) => boolean {
  const now = deps.now ?? (() => new Date())
  const log = deps.log ?? (() => undefined)
  return (kind) => {
    if (deps.locked) {
      log(`${kind} check not run: turned off by policy`)
      return false
    }
    deps.writePrefs({ ...deps.readPrefs(), lastCheckedAt: now().toISOString() })
    log(`${kind} check`)
    deps.onChecked?.()
    void deps.updates.check()
    return true
  }
}
