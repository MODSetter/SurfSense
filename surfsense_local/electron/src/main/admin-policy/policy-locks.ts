import type { InstallChannel } from "../install-channel/install-channel.ts"
import type { AdminPolicy } from "./read-policy.ts"

export type UsageLockReason = "policy" | "do_not_track"

/** Why the app never checks for updates: an admin's policy, or a package manager that owns them. */
export type UpdatesLockReason = "policy" | "channel"

/** Updates locked off: no automatic check and no Check now. */
export function updatesLocked(policy: AdminPolicy): boolean {
  return policy.updates === "off"
}

export function updatesLockReason(
  policy: AdminPolicy,
  channel: InstallChannel | null
): UpdatesLockReason | null {
  if (updatesLocked(policy)) return "policy"
  return channel ? "channel" : null
}

export function usageLockReason(policy: AdminPolicy): UsageLockReason | null {
  if (policy.usageStatistics === "off") return "policy"
  return policy.doNotTrack ? "do_not_track" : null
}
