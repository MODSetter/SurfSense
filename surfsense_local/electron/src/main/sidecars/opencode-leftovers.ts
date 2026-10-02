/**
 * An opencode left running by a run of the app that crashed. `serve` does not
 * notice its parent dying, so without this each crash leaves one more server
 * holding its memory and port. Only the recorded password proves a process is
 * ours: by the next boot, its pid may belong to anything.
 */
import { spawnSync } from "node:child_process"
import { readFileSync, rmSync, writeFileSync } from "node:fs"
import { join } from "node:path"

import { isWindows } from "./platform.ts"

const RECORD_FILE = "opencode-process.json"
// A live opencode answers its health route at once; a wait longer than this is not one.
const HEALTH_TIMEOUT_MS = 2000

interface Started {
  pid: number
  port: number
  password: string
}

/** Note what was just started, for the next boot to find if this run crashes. */
export function recordOpencode(agentDir: string, started: Started): void {
  writeFileSync(join(agentDir, RECORD_FILE), JSON.stringify(started), { mode: 0o600 })
}

/** Stop the recorded opencode if it is still ours and still running, then forget it. */
export async function stopLeftoverOpencode(agentDir: string, host: string): Promise<void> {
  const record = join(agentDir, RECORD_FILE)
  let started: Started
  try {
    started = JSON.parse(readFileSync(record, "utf8")) as Started
  } catch {
    return // nothing recorded, or nothing readable
  }
  if (await answersAsOurs(host, started)) stopTree(started.pid)
  rmSync(record, { force: true })
}

/** Whether the recorded port takes the recorded password, as only our opencode would. */
async function answersAsOurs(host: string, started: Started): Promise<boolean> {
  const credentials = Buffer.from(`opencode:${started.password}`).toString("base64")
  try {
    const response = await fetch(`http://${host}:${started.port}/global/health`, {
      headers: { Authorization: `Basic ${credentials}` },
      signal: AbortSignal.timeout(HEALTH_TIMEOUT_MS),
    })
    return response.ok
  } catch {
    return false
  }
}

/** Kill the server and everything it started; it was its own process group. */
function stopTree(pid: number): void {
  if (isWindows) {
    spawnSync("taskkill", ["/pid", String(pid), "/t", "/f"], { windowsHide: true })
    return
  }
  try {
    process.kill(-pid, "SIGKILL")
  } catch {
    // gone between the check and now
  }
}
