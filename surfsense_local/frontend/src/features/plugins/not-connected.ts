import type { Plugin } from "./api"
import { thirdPartyHeld } from "./third-party-held"

/** Waits for Connect, in its row and its details: disconnected, or lacking the sign-in, key,
 * headers or OAuth app it needs. A server down or a license refused is not fixed by
 * connecting, and a plugin the third-party switch holds is not connected at all. */
export function notConnected(
  plugin: Plugin,
  thirdPartyAllowed: boolean
): boolean {
  if (thirdPartyHeld(plugin, thirdPartyAllowed)) return false
  return plugin.disconnected || plugin.check_failure === "sign_in"
}
