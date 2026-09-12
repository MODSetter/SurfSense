// Proves the sidecar lifecycle end to end: start the API + worker, wait for
// /health, stop them, and confirm the OS reaped both process groups.
// Needs `uv sync` in ../backend. Node strips the imported .ts types (>=22.18).
import assert from "node:assert/strict"
import { mkdtempSync } from "node:fs"
import { tmpdir } from "node:os"
import { join } from "node:path"
import { fileURLToPath } from "node:url"

import { getFreePort, waitForHealth } from "../src/main/net.ts"
import { apiSpec, workerSpec } from "../src/main/sidecars/python.ts"
import { startAll, stopAll } from "../src/main/sidecars/supervisor.ts"

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
const ctx = {
  packaged: false,
  backendDir,
  binariesDir: "",
  host,
  apiPort: port,
  dataDir: mkdtempSync(join(tmpdir(), "surfsense-sidecar-check-")),
}
const sidecars = startAll([apiSpec(ctx), workerSpec(ctx)])
const apiPid = sidecars.get("api").pid
const workerPid = sidecars.get("worker").pid

try {
  await waitForHealth(host, port, { child: sidecars.get("api") })
  console.log(`health ok on ${host}:${port}`)
} finally {
  await stopAll(sidecars)
}

await new Promise((r) => setTimeout(r, 500)) // let the OS reap the groups
assert.ok(!isAlive(apiPid), "api sidecar still running after stop")
assert.ok(!isAlive(workerPid), "worker sidecar still running after stop")
console.log("sidecars stopped cleanly, no orphans")
