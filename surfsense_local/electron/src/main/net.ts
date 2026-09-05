// Localhost networking helpers for bringing the API sidecar up: probe its
// health, and (packaged only) pick a free port for it to bind.
import { type ChildProcess } from "node:child_process"
import http from "node:http"
import net from "node:net"

function pingHealth(host: string, port: number): Promise<boolean> {
  return new Promise((resolve) => {
    const req = http.get({ host, port, path: "/health", timeout: 1000 }, (res) => {
      res.resume()
      resolve(res.statusCode === 200)
    })
    req.on("error", () => resolve(false))
    req.on("timeout", () => {
      req.destroy()
      resolve(false)
    })
  })
}

const delay = (ms: number): Promise<void> => new Promise((r) => setTimeout(r, ms))

/**
 * Resolve once `/health` returns 200. Reject on timeout, or immediately if the
 * watched child exits first — a dead sidecar should fail fast, not stall.
 */
export async function waitForHealth(
  host: string,
  port: number,
  opts: { child?: ChildProcess; timeoutMs?: number } = {},
): Promise<void> {
  const { child, timeoutMs = 60_000 } = opts
  const deadline = Date.now() + timeoutMs

  let exited = false
  const onExit = (): void => {
    exited = true
  }
  child?.once("exit", onExit)
  try {
    while (Date.now() < deadline) {
      if (exited) throw new Error("sidecar exited during startup")
      if (await pingHealth(host, port)) return
      await delay(300)
    }
    throw new Error(`API on ${host}:${port} was not healthy within ${timeoutMs}ms`)
  } finally {
    child?.off("exit", onExit)
  }
}

/** Ask the OS for an unused TCP port (packaged app; dev uses a fixed one). */
export function getFreePort(host = "127.0.0.1"): Promise<number> {
  return new Promise((resolve, reject) => {
    const srv = net.createServer()
    srv.once("error", reject)
    srv.listen(0, host, () => {
      const addr = srv.address()
      srv.close(() =>
        addr && typeof addr === "object"
          ? resolve(addr.port)
          : reject(new Error("could not acquire a free port")),
      )
    })
  })
}
