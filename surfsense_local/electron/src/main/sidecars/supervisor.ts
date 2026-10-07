/**
 * The mechanism: spawn a set of sidecars, forward their logs, and reap them.
 */
import { type ChildProcess, spawn } from "node:child_process"
import { createWriteStream } from "node:fs"
import { createInterface } from "node:readline"
import type { Writable } from "node:stream"

import { sessionLog } from "../session-log/session-log.ts"
import { isWindows } from "./platform.ts"
import type { CrashHandler, SidecarSpec } from "./types.ts"

/** The running children, keyed by spec name so index.ts can wait on one. */
export type Sidecars = Map<string, ChildProcess>

/** Mirrors a sidecar's output to Electron's own stdout (1) or stderr (2). */
export type Echo = (fd: 1 | 2, text: string) => void

// Past this much the terminal has not taken yet, mirrored output is dropped;
// the session log still has every line.
const ECHO_BACKLOG_BYTES = 1 << 20

/**
 * On Windows Node writes a piped stdout synchronously, so a stalled terminal
 * froze the UI; an fs stream writes from libuv's pool. Elsewhere Node queues a
 * full pipe, which an fs stream would fail on instead (the pipe is non-blocking).
 */
export function terminal(fd: 1 | 2, windows = isWindows): Writable {
  if (windows) return createWriteStream("", { fd, autoClose: false })
  return fd === 1 ? process.stdout : process.stderr
}

/** An echo that drops what a stalled terminal has not taken past the backlog. */
export function createEcho(open: (fd: 1 | 2) => Writable = terminal): Echo {
  const streams = new Map<1 | 2, Writable | null>()
  return (fd, text) => {
    let stream = streams.get(fd)
    if (stream === undefined) {
      try {
        stream = open(fd)
        // A terminal that went away, or no console at all, must not crash main.
        stream.on("error", () => streams.set(fd, null))
      } catch {
        stream = null
      }
      streams.set(fd, stream)
    }
    if (stream && stream.writableLength < ECHO_BACKLOG_BYTES) stream.write(text)
  }
}

const mirror = createEcho()

// children we asked to stop; their `exit` is a stop, not a crash
const stopping = new WeakSet<ChildProcess>()

function spawnOne(
  spec: SidecarSpec,
  onCrash?: CrashHandler,
  echo: Echo = mirror,
): ChildProcess {
  const child = spawn(spec.cmd, spec.args, {
    cwd: spec.cwd,
    // own process group: one signal reaches a wrapper (uv) and its child
    detached: !isWindows,
    env: spec.inheritEnv === false ? spec.env : { ...process.env, ...spec.env },
  })
  child.stdout?.on("data", (b: Buffer) => echo(1, `[${spec.name}] ${b}`))
  child.stderr?.on("data", (b: Buffer) => echo(2, `[${spec.name}] ${b}`))
  // Whole lines for Report issue: a packaged app has no terminal to read.
  for (const stream of [child.stdout, child.stderr]) {
    if (!stream) continue
    createInterface({ input: stream, crlfDelay: Infinity }).on("line", (line) =>
      sessionLog.append(spec.name, line),
    )
  }
  // Written at once, not through the echo: the app exits right after its last
  // sidecar stops, which would discard a write still queued there.
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

export function startAll(
  specs: SidecarSpec[],
  onCrash?: CrashHandler,
  echo?: Echo,
): Sidecars {
  const children: Sidecars = new Map()
  for (const spec of specs) children.set(spec.name, spawnOne(spec, onCrash, echo))
  return children
}

/** Start one sidecar after boot. sd-server cannot run until a model is on disk. */
export function startOne(
  children: Sidecars,
  spec: SidecarSpec,
  onCrash?: CrashHandler,
  echo?: Echo,
): void {
  children.set(spec.name, spawnOne(spec, onCrash, echo))
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
    const pid = child.pid
    child.once("exit", () => {
      // The parent leaving does not prove its group has: a child that ignores
      // SIGTERM, such as a shell command the agent ran, would outlive the app.
      if (!isWindows) killGroup(pid)
      resolve()
    })

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
    const timer = setTimeout(() => killGroup(pid), timeoutMs)
    timer.unref()
  })
}

/** SIGKILL a sidecar's whole process group, which may already be gone. */
function killGroup(pid: number): void {
  try {
    process.kill(-pid, "SIGKILL")
  } catch {
    // reaped already
  }
}

export async function stopAll(children: Sidecars, timeoutMs = 5000): Promise<void> {
  await Promise.all([...children.values()].map((c) => stopOne(c, timeoutMs)))
}
