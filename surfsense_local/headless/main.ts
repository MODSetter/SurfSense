/**
 * The container's entry: boot the sidecars Electron boots, without a window,
 * then Caddy when a Caddyfile is given. The API's or Caddy's exit ends the
 * process non-zero, so the container's restart policy applies; any other sidecar
 * is the supervisor's, as on the desktop.
 */
import { mkdirSync } from "node:fs"
import type { AddressInfo } from "node:net"
import { join } from "node:path"
import { fileURLToPath } from "node:url"

import { announceApiUrl, withdrawApiUrl } from "../sidecars/api-url/announce-api-url.ts"
import { bootSidecars, type Booted } from "../sidecars/boot.ts"
import { stopOnce } from "../sidecars/stop-once.ts"
import { getFreePort } from "../sidecars/net.ts"
import { sidecarControl, stopAll } from "../sidecars/supervisor.ts"
import type { CrashHandler } from "../sidecars/types.ts"
import { startAccess } from "./access/server.ts"
import { defaultGateway } from "./access/host-request.ts"
import { setPassword } from "./access/password-store.ts"
import { CADDY_SIDECAR, caddySpec } from "./caddy.ts"
import { containerEnv } from "./container-env.ts"
import { contextFromEnv } from "./context-from-env.ts"
import { resolveSecret } from "./secret.ts"

const unsettled = contextFromEnv(process.env, "")
const context = { ...unsettled, secret: resolveSecret(process.env, unsettled.dataDir) }
// The Python specs pass it on themselves; every other sidecar inherits this environment (ADR 0018).
delete process.env.SURFSENSE_LOCAL_SECRET
// Read once, here: no sidecar needs the password, and none sees it.
const password = process.env.SURFSENSE_PASSWORD || undefined
delete process.env.SURFSENSE_PASSWORD
const environment = containerEnv(context.dataDir)
mkdirSync(environment.HOME, { recursive: true })
// The supervisor starts every sidecar on this environment.
Object.assign(process.env, environment)

// Unset on a checkout, which serves the API alone, as the desktop does.
const caddyfile = process.env.SURFSENSE_LOCAL_CADDYFILE || undefined
const chatgptCallbackPort = caddyfile ? await getFreePort() : undefined
if (chatgptCallbackPort) {
  // ChatGPT's sign-in listens where Caddy forwards `/callback`.
  process.env.SURFSENSE_LOCAL_CHATGPT_CALLBACK_PORT = String(chatgptCallbackPort)
}

let booted: Booted | null = null
let stopping = false

const stopSidecars = stopOnce(async () => {
  stopping = true
  booted?.stopWatching()
  withdrawApiUrl(context.dataDir)
  if (booted) await stopAll(booted.sidecars)
})

async function stop(code: number): Promise<never> {
  await stopSidecars()
  process.exit(code)
}

for (const signal of ["SIGTERM", "SIGINT"] as const) {
  process.on(signal, () => void stop(0))
}

const onCrash: CrashHandler = (name, code) => {
  console.error(`[headless] ${name} exited (code=${code})`)
  // Without either, nothing answers; any other sidecar is the supervisor's.
  if ((name === "api" || name === CADDY_SIDECAR) && !stopping) void stop(1)
}

booted = await bootSidecars(context, onCrash)
try {
  await booted.waitHealthy()
} catch (error) {
  console.error(`[headless] the API did not start: ${String(error)}`)
  await stop(1)
}
announceApiUrl(context.dataDir, booted.apiUrl)
if (caddyfile && chatgptCallbackPort) {
  // Set or replaced at every start, so it doubles as the reset for a forgotten one (ADR 0074).
  if (password) await setPassword(context.dataDir, password)
  const gateway = defaultGateway()
  const access = await startAccess({
    dataDir: context.dataDir,
    secret: context.secret,
    allowedHosts: process.env.SURFSENSE_ALLOWED_HOSTS ?? "",
    gateway: () => gateway,
  })
  const accessPort = (access.address() as AddressInfo).port
  sidecarControl(booted.sidecars, onCrash).start(
    caddySpec({
      caddy: process.env.SURFSENSE_LOCAL_CADDY || "caddy",
      caddyfile,
      apiPort: booted.ctx.apiPort,
      chatgptCallbackPort,
      accessPort,
      frontendDir:
        process.env.SURFSENSE_LOCAL_FRONTEND_DIR ||
        join(fileURLToPath(new URL("..", import.meta.url)), "frontend", "dist"),
    }),
  )
}
console.log(`[headless] ready ${booted.apiUrl}`)
