/**
 * The mechanism: spawn a set of sidecars, forward their logs, and reap them.
 */
import { type ChildProcess, spawn } from "node:child_process"

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
  child.on("exit", (code, signal) => {
    if (stopping.has(child)) {
      process.stderr.write(`[${spec.name}] stopped (code=${code} signal=${signal})\n`)
      return
    }
    process.stderr.write(`[${spec.name}] crashed (code=${code} signal=${signal})\n`)
    onCrash?.(spec.name, code)
  })
  return child
}

export function startAll(specs: SidecarSpec[], onCrash?: CrashHandler): Sidecars {
  const children: Sidecars = new Map()
  for (const spec of specs) children.set(spec.name, spawnOne(spec, onCrash))
  return children
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
