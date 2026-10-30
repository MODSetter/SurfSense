import type { OsLabel, PlatformLabel } from "../system-labels.ts"
import { isoWeek } from "../utc-calendar.ts"
import type { ActiveFlags } from "./active-flags.ts"
import type { ReportTrigger } from "./first-week.ts"
import { installAge, type InstallAge } from "./install-age.ts"
import { SETUP_STEPS } from "./setup-progress.ts"

// Every value is one of these, a boolean or a fixed format (contract 05, part B):
// whatever the local API answers, nothing else can reach the body.
const WEEK_VALUES = {
  chat_turns: ["0", "1-9", "10-49", "50+", "unknown"],
  agent_turns: ["0", "1-9", "10-49", "50+", "unknown"],
  model_source: ["none", "local", "remote", "both", "unknown"],
  sources: ["0", "1-9", "10-99", "100-999", "1000+", "unknown"],
  studio_outputs: ["0", "1-4", "5+", "unknown"],
  plugin_calls: ["0", "1-9", "10+", "unknown"],
  onboarding: [...SETUP_STEPS, "unknown"],
  // Revision 1.2: of the 7 and 28 UTC days before the report, how many show use.
  days_used_7: ["0", "1", "2-3", "4-6", "7", "unknown"],
  days_used_28: ["0", "1", "2-3", "4-7", "8-14", "15-28", "unknown"],
} as const
const RAM_GB = ["<8", "8-15", "16-31", "32-63", "64+"] as const
const GPU = ["nvidia", "amd", "intel", "apple", "none", "unknown"] as const
const VRAM_GB = ["0", "<4", "4-7", "8-11", "12-23", "24+", "unknown"] as const
// Whether the model runtime can use the card the OS sees.
const GPU_RUNTIME = ["reachable", "unreachable", "none", "unknown"] as const
const UI_LANGUAGES = ["en", "ja", "de"] as const

type WeekBlock = { [Key in keyof typeof WEEK_VALUES]: (typeof WEEK_VALUES)[Key][number] }
type HardwareBlock = {
  ram_gb: (typeof RAM_GB)[number]
  gpu: (typeof GPU)[number]
  vram_gb: (typeof VRAM_GB)[number]
  gpu_runtime: (typeof GPU_RUNTIME)[number]
}
type UiLanguage = (typeof UI_LANGUAGES)[number] | "other"

export type UsageReport = {
  schema: 1
  app_version: string
  platform: PlatformLabel
  os: OsLabel
  ui_language: UiLanguage
  install_week: string
  install_age: InstallAge
  trigger: ReportTrigger
  active: ActiveFlags
  hardware: HardwareBlock | null
  week: WeekBlock | null
}

function record(value: unknown): Record<string, unknown> {
  return typeof value === "object" && value !== null ? (value as Record<string, unknown>) : {}
}

function oneOf<T extends string>(allowed: readonly T[], value: unknown, fallback: T): T {
  return allowed.includes(value as T) ? (value as T) : fallback
}

function weekBlock(value: unknown): WeekBlock {
  const week = record(value)
  return {
    chat_turns: oneOf(WEEK_VALUES.chat_turns, week.chat_turns, "unknown"),
    agent_turns: oneOf(WEEK_VALUES.agent_turns, week.agent_turns, "unknown"),
    model_source: oneOf(WEEK_VALUES.model_source, week.model_source, "unknown"),
    sources: oneOf(WEEK_VALUES.sources, week.sources, "unknown"),
    studio_outputs: oneOf(WEEK_VALUES.studio_outputs, week.studio_outputs, "unknown"),
    plugin_calls: oneOf(WEEK_VALUES.plugin_calls, week.plugin_calls, "unknown"),
    onboarding: oneOf(WEEK_VALUES.onboarding, week.onboarding, "unknown"),
    days_used_7: oneOf(WEEK_VALUES.days_used_7, week.days_used_7, "unknown"),
    days_used_28: oneOf(WEEK_VALUES.days_used_28, week.days_used_28, "unknown"),
  }
}

// A "16 GB" machine reports a little under 16 GiB, so round before bucketing.
function ramBucket(totalMemoryBytes: number): HardwareBlock["ram_gb"] {
  const gib = Math.round(totalMemoryBytes / 2 ** 30)
  if (gib < 8) return "<8"
  if (gib < 16) return "8-15"
  if (gib < 32) return "16-31"
  if (gib < 64) return "32-63"
  return "64+"
}

function hardwareBlock(value: unknown, totalMemoryBytes: number): HardwareBlock {
  const hardware = record(value)
  return {
    ram_gb: oneOf(RAM_GB, hardware.ram_gb, ramBucket(totalMemoryBytes)),
    gpu: oneOf(GPU, hardware.gpu, "unknown"),
    vram_gb: oneOf(VRAM_GB, hardware.vram_gb, "unknown"),
    gpu_runtime: oneOf(GPU_RUNTIME, hardware.gpu_runtime, "unknown"),
  }
}

/** Main's interface language (i18n/app-locale.ts) in the contract's words. */
export function uiLanguage(locale: string): UiLanguage {
  return oneOf<UiLanguage>(UI_LANGUAGES, locale, "other")
}

/**
 * The report, key for key as contract 05 orders it. `summary` is the local API's
 * /usage-statistics/summary answer, or null when it could not be read; which
 * blocks a report carries is the caller's to decide (first-week.ts).
 */
export function buildUsageReport(input: {
  appVersion: string
  platform: PlatformLabel
  os: OsLabel
  firstRunAt: string
  at: Date
  trigger: ReportTrigger
  flags: ActiveFlags
  withHardware: boolean
  withWeek: boolean
  summary: unknown
  locale: string
  totalMemoryBytes: number
}): UsageReport {
  const summary = record(input.summary)
  return {
    schema: 1,
    app_version: input.appVersion,
    platform: input.platform,
    os: input.os,
    ui_language: oneOf<UiLanguage>(
      [...UI_LANGUAGES, "other"],
      summary.ui_language,
      uiLanguage(input.locale)
    ),
    install_week: isoWeek(new Date(input.firstRunAt)),
    install_age: installAge(input.firstRunAt, input.at),
    trigger: input.trigger,
    active: { ...input.flags },
    hardware: input.withHardware ? hardwareBlock(summary.hardware, input.totalMemoryBytes) : null,
    week: input.withWeek ? weekBlock(summary.week) : null,
  }
}
