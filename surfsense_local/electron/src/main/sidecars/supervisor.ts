/**
 * The mechanism: spawn a set of sidecars, forward their logs, and reap them.
 */
import { type ChildProcess, spawn } from "node:child_process"
import { createInterface } from "node:readline"

import { sessionLog } from "../session-log/session-log.ts"
import { isWindows } from "./platform.ts"
import type { CrashHandler, SidecarSpec } from "./types.ts"

/** The running children, keyed by spec name so index.ts can wait on one. */
export type Sidecars = Map<string, ChildProcess>

// children we asked to stop; their `exit` is a stop, not a crash
const stopping = new WeakSet<ChildProcess>()

function spawnOne(spec: SidecarSpec, onCrash?: CrashHandler): ChildProcess {
  const child = spawn(spec.cmd, spec.args, {
    cwd: spec.cwd,
    // own process group: one signal reaches a wrapper (uv) and its child
    detached: !isWindows,
    env: { ...process.env, ...spec.env },
  })
  child.stdout?.on("data", (b: Buffer) => process.stdout.write(`[${spec.name}] ${b}`))
  child.stderr?.on("data", (b: Buffer) => process.stderr.write(`[${spec.name}] ${b}`))
  // Whole lines for Report issue: a packaged app has no terminal to read.
  for (const stream of [child.stdout, child.stderr]) {
    if (!stream) continue
    createInterface({ input: stream, crlfDelay: Infinity }).on("line", (line) =>
      sessionLog.append(spec.name, line),
    )
  }
  const note = (text: string) => {
    process.stderr.write(`[${spec.name}] ${text}\n`)
    sessionLog.append(spec.name, text)
  }
  child.on("exit", (code, signal) => {
    if (stopping.has(child)) {
      note(`stopped (code=${code} signal=${signal})`)
      return
    }
    note(`crashed (code=${code} signal=${signal})`)
    onCrash?.(spec.name, code)
  })
  return child
}

export function startAll(specs: SidecarSpec[], onCrash?: CrashHandler): Sidecars {
  const children: Sidecars = new Map()
  for (const spec of specs) children.set(spec.name, spawnOne(spec, onCrash))
  return children
}

/** Start one sidecar after boot. sd-server cannot run until a model is on disk. */
export function startOne(
  children: Sidecars,
  spec: SidecarSpec,
  onCrash?: CrashHandler,
): void {
  children.set(spec.name, spawnOne(spec, onCrash))
}

/** Stop one sidecar and forget it, leaving the rest running. */
export async function stopNamed(
  children: Sidecars,
  name: string,
  timeoutMs = 5000,
): Promise<void> {
  const child = children.get(name)
  if (!child) return
  children.delete(name)
  await stopOne(child, timeoutMs)
}

function stopOne(child: ChildProcess, timeoutMs: number): Promise<void> {
  return new Promise((resolve) => {
    if (child.exitCode !== null || child.signalCode !== null || child.pid == null) {
      resolve()
      return
    }
    stopping.add(child)
    child.once("exit", () => resolve())

    if (isWindows) {
      // no POSIX groups on Windows: kill the tree; windowsHide avoids a console flash
      spawn("taskkill", ["/pid", String(child.pid), "/t", "/f"], { windowsHide: true })
      return
    }
    try {
      process.kill(-child.pid, "SIGTERM")
    } catch {
      resolve() // already gone
      return
    }
    const timer = setTimeout(() => {
      try {
        process.kill(-child.pid!, "SIGKILL")
      } catch {
        // reaped between the timeout and now
      }
    }, timeoutMs)
    timer.unref()
  })
}

export async function stopAll(children: Sidecars, timeoutMs = 5000): Promise<void> {
  await Promise.all([...children.values()].map((c) => stopOne(c, timeoutMs)))
}
