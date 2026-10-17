import { execFile } from "node:child_process"

import { apiCommand } from "../sidecars/python.ts"
import type { SidecarContext } from "../sidecars/types.ts"
import type { GoBackResult, GoingBackOptions, Way } from "./offer-going-back.ts"

const OPTIONS_TIMEOUT_MS = 60_000

export interface BackendCommands {
  options: () => Promise<GoingBackOptions>
  goBack: (way: Way) => Promise<GoBackResult>
}

/** The two backend commands, run with the API's binary; `log` gets why one failed. */
export function backendCommands(
  ctx: SidecarContext,
  log: (text: string) => void,
): BackendCommands {
  return {
    options: async () => {
      const result = await run(ctx, ["--going-back-options"], OPTIONS_TIMEOUT_MS)
      if (!result.ok) log(`going back: could not read the options: ${result.stderr}`)
      return parseGoingBackOptions(result.stdout)
    },
    goBack: async (way) => {
      // No time limit: killing it skips loading the set-aside copy back, and
      // SQLite's busy timeout already bounds every lock wait.
      const result = await run(ctx, ["--go-back", way])
      if (!result.ok) log(`going back (${way}) failed: ${result.stderr}`)
      return parseGoBackResult(result)
    },
  }
}

export function parseGoingBackOptions(stdout: string): GoingBackOptions {
  try {
    const parsed = JSON.parse(stdout) as { can_undo?: unknown; backup_saved_at?: unknown }
    return {
      canUndo: parsed.can_undo === true,
      backupSavedAt:
        typeof parsed.backup_saved_at === "string" ? new Date(parsed.backup_saved_at) : null,
    }
  } catch {
    return { canUndo: false, backupSavedAt: null }
  }
}

export function parseGoBackResult(result: { exitCode: number | null; stdout: string }): GoBackResult {
  if (result.exitCode === 0) return "went-back"
  try {
    const parsed = JSON.parse(result.stdout) as { data_unchanged?: unknown }
    if (parsed.data_unchanged === true) return "failed-data-unchanged"
  } catch {
    // Killed or crashed: nothing says the copy was loaded back.
  }
  return "failed-data-may-have-changed"
}

interface RunResult {
  ok: boolean
  exitCode: number | null
  stdout: string
  stderr: string
}

function run(ctx: SidecarContext, args: string[], timeout?: number): Promise<RunResult> {
  const command = apiCommand(ctx, args)
  return new Promise((resolve) => {
    execFile(
      command.cmd,
      command.args,
      { cwd: command.cwd, env: { ...process.env, ...command.env }, timeout, windowsHide: true },
      (error, stdout, stderr) => {
        // A non-numeric code is a spawn failure such as ENOENT, not an exit.
        const code = error === null ? 0 : typeof error.code === "number" ? error.code : null
        resolve({ ok: error === null, exitCode: code, stdout, stderr })
      },
    )
  })
}
