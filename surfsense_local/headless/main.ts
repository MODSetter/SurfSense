/**
 * The container's entry: boot the sidecars Electron boots, without a window.
 * The API's exit ends the process non-zero, so the container's restart policy
 * applies; any other sidecar is the supervisor's, as on the desktop.
 */
import { mkdirSync } from "node:fs"

import { announceApiUrl, withdrawApiUrl } from "../sidecars/api-url/announce-api-url.ts"
import { bootSidecars, type Booted } from "../sidecars/boot.ts"
import { stopAll } from "../sidecars/supervisor.ts"
import { containerEnv } from "./container-env.ts"
import { contextFromEnv } from "./context-from-env.ts"
import { resolveSecret } from "./secret.ts"

const unsettled = contextFromEnv(process.env, "")
const context = { ...unsettled, secret: resolveSecret(process.env, unsettled.dataDir) }
// The Python specs pass it on themselves; every other sidecar inherits this environment (ADR 0018).
delete process.env.SURFSENSE_LOCAL_SECRET
const environment = containerEnv(context.dataDir)
mkdirSync(environment.HOME, { recursive: true })
// The supervisor starts every sidecar on this environment.
Object.assign(process.env, environment)

let booted: Booted | null = null
let stopping = false

async function stop(code: number): Promise<never> {
  if (!stopping) {
    stopping = true
    booted?.stopWatching()
    withdrawApiUrl(context.dataDir)
    if (booted) await stopAll(booted.sidecars)
  }
  process.exit(code)
}

for (const signal of ["SIGTERM", "SIGINT"] as const) {
  process.on(signal, () => void stop(0))
}

booted = await bootSidecars(context, (name, code) => {
  console.error(`[headless] ${name} exited (code=${code})`)
  if (name === "api" && !stopping) void stop(1)
})
try {
  await booted.waitHealthy()
} catch (error) {
  console.error(`[headless] the API did not start: ${String(error)}`)
  await stop(1)
}
announceApiUrl(context.dataDir, booted.apiUrl)
console.log(`[headless] ready ${booted.apiUrl}`)
