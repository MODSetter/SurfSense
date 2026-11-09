import type { ActiveFlags } from "./active-flags.ts"
import type { SentHardware } from "./privacy-file.ts"

// Contract 05, revision 1.1: the first week runs seven days from firstRunAt, when
// most installs decide whether to stay, so its reports say more.
const WEEK_MS = 7 * 86_400_000

export type ReportTrigger = "daily" | "setup"

export function inFirstWeek(firstRunAt: string, at: Date): boolean {
  const start = Date.parse(firstRunAt)
  return at.getTime() >= start && at.getTime() < start + WEEK_MS
}

/** The week block counts the seven days before a report, or since the first run when that is later. */
export function weekSince(firstRunAt: string, at: Date): Date {
  return new Date(Math.max(Date.parse(firstRunAt), at.getTime() - WEEK_MS))
}

/** Every first-week report carries the week; after it, only a week's first report does. */
export function carriesWeek(trigger: ReportTrigger, flags: ActiveFlags, firstWeek: boolean): boolean {
  return trigger === "setup" || firstWeek || flags.week
}

/**
 * The first daily report carries the hardware; a first-week report carries it
 * again while the last one sent left part of it unknown.
 */
export function carriesHardware(input: {
  trigger: ReportTrigger
  flags: ActiveFlags
  firstWeek: boolean
  sent: SentHardware | null
}): boolean {
  if (input.trigger === "daily" && input.flags.first) return true
  return input.firstWeek && input.sent !== null && partlyUnknown(input.sent)
}

/** A first-week resend that would repeat the block already sent says nothing new. */
export function repeatsSentHardware(
  hardware: { gpu: string; vram_gb: string; gpu_runtime: string } | null,
  sent: SentHardware | null
): boolean {
  return (
    hardware !== null &&
    sent !== null &&
    hardware.gpu === sent.gpu &&
    hardware.vram_gb === sent.vram_gb &&
    hardware.gpu_runtime === sent.gpu_runtime
  )
}

// A block sent before gpu_runtime existed (null) never said whether the runtime reaches the card.
function partlyUnknown(sent: SentHardware): boolean {
  return (
    sent.gpu === "unknown" ||
    sent.vram_gb === "unknown" ||
    sent.gpu_runtime === null ||
    sent.gpu_runtime === "unknown"
  )
}
