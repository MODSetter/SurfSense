// Caddy, the container's one listener: the SPA, the API under /api, the sign-in
// callbacks and the access service, all on the ports this run picked.
import { dirname } from "node:path"

import type { SidecarSpec } from "../sidecars/types.ts"

export const CADDY_SIDECAR = "caddy"

export function caddySpec(options: {
  caddy: string
  caddyfile: string
  apiPort: number
  chatgptCallbackPort: number
  accessPort: number
  frontendDir: string
  /** What the chosen configuration reads besides the ports: its TLS mode's. */
  env?: Record<string, string>
}): SidecarSpec {
  return {
    name: CADDY_SIDECAR,
    cmd: options.caddy,
    args: ["run", "--config", options.caddyfile, "--adapter", "caddyfile"],
    // Its imports are beside it.
    cwd: dirname(options.caddyfile),
    env: {
      SURFSENSE_API_PORT: String(options.apiPort),
      SURFSENSE_CHATGPT_CALLBACK_PORT: String(options.chatgptCallbackPort),
      SURFSENSE_FRONTEND_DIR: options.frontendDir,
      // Asked about every request (forward_auth), and serves the app's /access/*.
      SURFSENSE_ACCESS_PORT: String(options.accessPort),
      ...options.env,
    },
  }
}
