/**
 * An opencode left running by a run of the app that crashed. `serve` does not
 * notice its parent dying, so without this each crash leaves one more server
 * holding its memory and port. By the next boot its pid may belong to anything,
 * so a process is ours only if the recorded port takes the recorded password and,
 * on 2.x, names the recorded pid.
 */
import { spawnSync } from "node:child_process"
import { readFileSync, rmSync, writeFileSync } from "node:fs"
import { join } from "node:path"

import { isWindows } from "./platform.ts"

const RECORD_FILE = "opencode-process.json"
// A live opencode answers at once; a wait longer than this is not one.
const ANSWER_TIMEOUT_MS = 2000

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
  // 2.x names its pid even while booting, when it answers 503.
  const info = await ask(host, started, "/api/info")
  const pid = await pidIn(info)
  if (pid != null) return pid === started.pid
  // A 1.x leftover from the release before has no pid to give.
  return (await ask(host, started, "/global/health"))?.ok ?? false
}

async function ask(host: string, started: Started, route: string): Promise<Response | null> {
  const credentials = Buffer.from(`opencode:${started.password}`).toString("base64")
  try {
    return await fetch(`http://${host}:${started.port}${route}`, {
      headers: { Authorization: `Basic ${credentials}` },
      signal: AbortSignal.timeout(ANSWER_TIMEOUT_MS),
    })
  } catch {
    return null
  }
}

async function pidIn(response: Response | null): Promise<number | null> {
  if (response == null || response.status === 401) return null
  try {
    const { pid } = (await response.json()) as { pid?: unknown }
    return typeof pid === "number" ? pid : null
  } catch {
    return null
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
