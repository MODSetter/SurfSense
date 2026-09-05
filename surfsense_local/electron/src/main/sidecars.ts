/** 
 * Spawn and reap the two Python sidecars (API + worker).
 */
import { type ChildProcess, spawn } from "node:child_process"
import { join } from "node:path"

export interface SidecarConfig {
  /** Backend project root; the cwd for `uv run` in dev. */
  backendDir: string
  /** Directory holding the frozen `api`/`worker` binaries (packaged only). */
  binariesDir: string
  host: string
  port: number
  dataDir: string
  /** Dev spawns `uv run`; packaged spawns the frozen binaries. */
  packaged: boolean
}

/** Called when a sidecar exits without us asking it to. */
export type CrashHandler = (name: string, code: number | null) => void

export interface Sidecars {
  api: ChildProcess
  worker: ChildProcess
}

const isWindows = process.platform === "win32"

// children we asked to stop; their `exit` is a stop, not a crash
const stopping = new WeakSet<ChildProcess>()

function spawnSidecar(
  name: string,
  cmd: string,
  args: string[],
  cfg: SidecarConfig,
  onCrash?: CrashHandler,
): ChildProcess {
  const child = spawn(cmd, args, {
    cwd: cfg.packaged ? cfg.binariesDir : cfg.backendDir,
    // own process group: one signal reaches `uv` and its Python child
    detached: !isWindows,
    env: {
      ...process.env,
      PYTHONUNBUFFERED: "1", // unbuffered: startup + crash logs show immediately
      SURFSENSE_LOCAL_HOST: cfg.host,
      SURFSENSE_LOCAL_PORT: String(cfg.port),
      SURFSENSE_LOCAL_DATA_DIR: cfg.dataDir,
    },
  })
  child.stdout?.on("data", (b: Buffer) => process.stdout.write(`[${name}] ${b}`))
  child.stderr?.on("data", (b: Buffer) => process.stderr.write(`[${name}] ${b}`))
  child.on("exit", (code, signal) => {
    if (stopping.has(child)) {
      process.stderr.write(`[${name}] stopped (code=${code} signal=${signal})\n`)
      return
    }
    process.stderr.write(`[${name}] crashed (code=${code} signal=${signal})\n`)
    onCrash?.(name, code)
  })
  return child
}

export function startSidecars(cfg: SidecarConfig, onCrash?: CrashHandler): Sidecars {
  const [apiCmd, apiArgs]: [string, string[]] = cfg.packaged
    ? [join(cfg.binariesDir, "api", "api"), []]
    : ["uv", ["run", "main.py"]]
  const [workerCmd, workerArgs]: [string, string[]] = cfg.packaged
    ? [join(cfg.binariesDir, "worker", "worker"), []]
    : ["uv", ["run", "worker.py"]]
  return {
    api: spawnSidecar("api", apiCmd, apiArgs, cfg, onCrash),
    worker: spawnSidecar("worker", workerCmd, workerArgs, cfg, onCrash),
  }
}

function stopSidecar(child: ChildProcess, timeoutMs: number): Promise<void> {
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

export async function stopSidecars(s: Sidecars, timeoutMs = 5000): Promise<void> {
  await Promise.all([stopSidecar(s.api, timeoutMs), stopSidecar(s.worker, timeoutMs)])
}
