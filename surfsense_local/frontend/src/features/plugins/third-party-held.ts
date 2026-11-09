import type { Plugin } from "./api"

/** Held by the third-party switch: nothing reaches its server, so nothing offers to. */
export function thirdPartyHeld(plugin: Plugin, thirdPartyAllowed: boolean) {
  return plugin.source !== "first_party" && !thirdPartyAllowed
}
