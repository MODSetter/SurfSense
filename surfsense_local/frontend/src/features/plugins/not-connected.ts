import type { Plugin } from "./api"

/** Waits for Connect, in its row and its details: disconnected, or lacking the sign-in, key,
 * headers or OAuth app it needs. A server down or a license refused is not fixed by connecting. */
export function notConnected(plugin: Plugin): boolean {
  return plugin.disconnected || plugin.check_failure === "sign_in"
}
