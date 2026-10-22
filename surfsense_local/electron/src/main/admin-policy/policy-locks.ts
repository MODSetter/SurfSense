import type { AdminPolicy } from "./read-policy.ts"

export type UsageLockReason = "policy" | "do_not_track"

/** Updates locked off: no automatic check and no Check now. */
export function updatesLocked(policy: AdminPolicy): boolean {
  return policy.updates === "off"
}

export function usageLockReason(policy: AdminPolicy): UsageLockReason | null {
  if (policy.usageStatistics === "off") return "policy"
  return policy.doNotTrack ? "do_not_track" : null
}
