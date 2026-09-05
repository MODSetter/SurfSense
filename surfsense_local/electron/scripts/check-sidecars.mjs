// Proves the sidecar lifecycle end to end: start the API + worker, wait for
// /health, stop them, and confirm the OS reaped both process groups.
// Needs `uv sync` in ../backend. Node strips the imported .ts types (>=22.18).
import assert from "node:assert/strict"
import { mkdtempSync } from "node:fs"
import { tmpdir } from "node:os"
import { join } from "node:path"
import { fileURLToPath } from "node:url"

import { getFreePort, waitForHealth } from "../src/main/net.ts"
import { startSidecars, stopSidecars } from "../src/main/sidecars.ts"

const here = fileURLToPath(new URL(".", import.meta.url))
const backendDir = join(here, "..", "..", "backend")

const isAlive = (pid) => {
  try {
    process.kill(pid, 0)
    return true
  } catch {
    return false
  }
}

const host = "127.0.0.1"
const port = await getFreePort(host)
const sidecars = startSidecars({
  backendDir,
  binariesDir: "",
  host,
  port,
  dataDir: mkdtempSync(join(tmpdir(), "surfsense-sidecar-check-")),
  packaged: false,
})
const { pid: apiPid } = sidecars.api
const { pid: workerPid } = sidecars.worker

try {
  await waitForHealth(host, port, { child: sidecars.api })
  console.log(`health ok on ${host}:${port}`)
} finally {
  await stopSidecars(sidecars)
}

await new Promise((r) => setTimeout(r, 500)) // let the OS reap the groups
assert.ok(!isAlive(apiPid), "api sidecar still running after stop")
assert.ok(!isAlive(workerPid), "worker sidecar still running after stop")
console.log("sidecars stopped cleanly, no orphans")
