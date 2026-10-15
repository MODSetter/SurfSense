import { execFile } from "node:child_process"

import { apiCommand } from "../sidecars/python.ts"
import type { SidecarContext } from "../sidecars/types.ts"
import type { GoingBackOptions, Way } from "./offer-going-back.ts"

// Going back copies the whole database at least once; a large one takes a while.
const GO_BACK_TIMEOUT_MS = 10 * 60_000
const OPTIONS_TIMEOUT_MS = 60_000

export interface BackendCommands {
  options: () => Promise<GoingBackOptions>
  goBack: (way: Way) => Promise<boolean>
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
      const result = await run(ctx, ["--go-back", way], GO_BACK_TIMEOUT_MS)
      if (!result.ok) log(`going back (${way}) failed: ${result.stderr}`)
      return result.ok
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

function run(
  ctx: SidecarContext,
  args: string[],
  timeout: number,
): Promise<{ ok: boolean; stdout: string; stderr: string }> {
  const command = apiCommand(ctx, args)
  return new Promise((resolve) => {
    execFile(
      command.cmd,
      command.args,
      { cwd: command.cwd, env: { ...process.env, ...command.env }, timeout, windowsHide: true },
      (error, stdout, stderr) => resolve({ ok: error === null, stdout, stderr }),
    )
  })
}
