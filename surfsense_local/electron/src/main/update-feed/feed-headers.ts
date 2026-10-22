import type { OsLabel, PlatformLabel } from "../system-labels.ts"

/** The only headers SurfSense's feed gets (contract 05, part A); an unknown label is left out. */
export function feedHeaders(facts: {
  version: string
  platform: PlatformLabel | null
  os: OsLabel | null
}): Record<string, string> {
  return {
    "X-SurfSense-Version": facts.version,
    ...(facts.platform ? { "X-SurfSense-Platform": facts.platform } : {}),
    ...(facts.os ? { "X-SurfSense-OS": facts.os } : {}),
  }
}
