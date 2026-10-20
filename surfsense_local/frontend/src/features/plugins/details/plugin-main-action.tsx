import type { Plugin } from "../api"
import { notConnected } from "../not-connected"
import { thirdPartyHeld } from "../third-party-held"
import { ConnectPluginButton } from "./connect-plugin-button"
import { DisconnectPluginButton } from "./disconnect-plugin-button"

/** The page's one action beside its menu: Connect while the plugin is not connected, whatever
 * that takes, and Disconnect once it is. */
export function PluginMainAction({
  plugin,
  thirdPartyAllowed,
  disconnecting,
  onDisconnect,
}: {
  plugin: Plugin
  thirdPartyAllowed: boolean
  disconnecting: boolean
  onDisconnect: () => void
}) {
  // Neither: both would reach a server the third-party switch keeps out.
  if (thirdPartyHeld(plugin, thirdPartyAllowed)) return null
  // A sign-in or key it lacks is fixed by connecting; there is nothing working to disconnect.
  if (notConnected(plugin, thirdPartyAllowed)) {
    return <ConnectPluginButton plugin={plugin} size="sm" />
  }
  return (
    <DisconnectPluginButton
      name={plugin.name}
      disconnecting={disconnecting}
      onDisconnect={onDisconnect}
    />
  )
}
