import { FirstPartyPlugins } from "./first-party-plugins"
import { ThirdPartyPlugins } from "./third-party-plugins"

/** Plugins to connect: SurfSense's own first, then the registry's. */
export function BrowsePlugins() {
  return (
    <>
      <FirstPartyPlugins />
      <ThirdPartyPlugins />
    </>
  )
}
