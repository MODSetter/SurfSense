import { readFileSync } from "node:fs"
import { posix, win32 } from "node:path"

/** What an administrator, or the environment, forces (contract 05, part C). Read once at startup. */
export type AdminPolicy = {
  updates: "off" | "user"
  usageStatistics: "off" | "user"
  /** An https mirror in place of updates.surfsense.com; it has no GitHub fallback. */
  updateFeed: string | null
  /** DO_NOT_TRACK=1 or SURFSENSE_NO_TELEMETRY=1: usage statistics off, updates untouched. */
  doNotTrack: boolean
  /** Why a policy file that exists was not taken as written, for the session log. */
  problem: string | null
}

type Env = Record<string, string | undefined>

export function policyPath(platform: string, env: Env): string | null {
  if (platform === "win32") {
    const programData = env.ProgramData ?? env.PROGRAMDATA ?? "C:\\ProgramData"
    return win32.join(programData, "SurfSense", "policy.json")
  }
  if (platform === "darwin") {
    return posix.join("/Library/Application Support/SurfSense", "policy.json")
  }
  if (platform === "linux") return "/etc/surfsense/policy.json"
  return null
}

function switchedOn(value: string | undefined): boolean {
  const normalized = value?.trim().toLowerCase()
  return normalized === "1" || normalized === "true"
}

function httpsUrl(value: unknown): string | null {
  if (typeof value !== "string") return null
  try {
    const url = new URL(value)
    return url.protocol === "https:" && !url.username && !url.password ? url.href : null
  } catch {
    return null
  }
}

// A value the admin wrote but we cannot read turns the setting off: a policy
// file exists to send less, so a typo must never send more.
function setting(value: unknown): "off" | "user" | "invalid" {
  if (value === undefined || value === "user") return "user"
  return value === "off" ? "off" : "invalid"
}

export function readPolicy(options: {
  platform: string
  env: Env
  readFile?: (path: string) => string
}): AdminPolicy {
  const { platform, env, readFile = (path) => readFileSync(path, "utf8") } = options
  const doNotTrack = switchedOn(env.DO_NOT_TRACK) || switchedOn(env.SURFSENSE_NO_TELEMETRY)
  const open: AdminPolicy = {
    updates: "user",
    usageStatistics: "user",
    updateFeed: null,
    doNotTrack,
    problem: null,
  }
  const closed = (problem: string): AdminPolicy => ({
    ...open,
    updates: "off",
    usageStatistics: "off",
    problem,
  })

  const path = policyPath(platform, env)
  if (path === null) return open
  let raw: string
  try {
    raw = readFile(path)
  } catch (error) {
    const code = (error as NodeJS.ErrnoException | null)?.code
    return code === "ENOENT" || code === "ENOTDIR" ? open : closed("unreadable")
  }
  let parsed: unknown
  try {
    parsed = JSON.parse(raw)
  } catch {
    return closed("not JSON")
  }
  if (typeof parsed !== "object" || parsed === null || Array.isArray(parsed)) {
    return closed("not a JSON object")
  }
  const record = parsed as Record<string, unknown>
  const problems: string[] = []
  const updates = setting(record.updates)
  const usageStatistics = setting(record.usageStatistics)
  if (updates === "invalid") problems.push("updates")
  if (usageStatistics === "invalid") problems.push("usageStatistics")
  const updateFeed = record.updateFeed === undefined ? null : httpsUrl(record.updateFeed)
  const badFeed = record.updateFeed !== undefined && updateFeed === null
  if (badFeed) problems.push("updateFeed")
  return {
    updates: updates === "user" && !badFeed ? "user" : "off",
    usageStatistics: usageStatistics === "user" ? "user" : "off",
    updateFeed,
    doNotTrack,
    problem: problems.length ? `unusable ${problems.join(", ")}` : null,
  }
}
