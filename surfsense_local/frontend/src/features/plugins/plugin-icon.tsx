import { useCallback, useState } from "react"

import { cn } from "@/lib/utils"

import { firstPartyIconUrl, registryIconUrl } from "./api"

/** The icon beside the plugin's list, SurfSense's or the registry's, or the name's first letter when there is none or it fails to load. */
export function PluginIcon({
  id,
  name,
  hasIcon,
  firstParty = false,
  className,
}: {
  id: string
  name: string
  hasIcon: boolean
  /** One of SurfSense's own plugins, whose icon is served from its list. */
  firstParty?: boolean
  className?: string
}) {
  const [failed, setFailed] = useState(false)
  const [loaded, setLoaded] = useState(false)
  // Set before the first paint, so a logo the browser holds never replays the fade.
  const showIfAlreadyLoaded = useCallback((logo: HTMLImageElement | null) => {
    if (logo?.complete && logo.naturalWidth > 0) setLoaded(true)
  }, [])
  const src = !hasIcon
    ? undefined
    : firstParty
      ? firstPartyIconUrl(id)
      : registryIconUrl(id)
  if (src && !failed) {
    return (
      // Registry marks are light or coloured, so they sit on a grey tile, never the bare page.
      <span
        className={cn(
          "flex size-8 shrink-0 rounded-md bg-muted-foreground/20 p-1 outline -outline-offset-1 outline-black/10 dark:bg-muted dark:outline-white/10",
          className
        )}
      >
        <img
          ref={showIfAlreadyLoaded}
          src={src}
          alt=""
          className={cn(
            "size-full object-contain transition-opacity duration-150 motion-reduce:transition-none",
            loaded ? "opacity-100" : "opacity-0"
          )}
          onLoad={() => setLoaded(true)}
          onError={() => setFailed(true)}
        />
      </span>
    )
  }
  return (
    <span
      aria-hidden
      className={cn(
        "flex size-8 shrink-0 items-center justify-center rounded-md bg-muted text-sm font-medium text-muted-foreground uppercase",
        className
      )}
    >
      {name.trim().charAt(0)}
    </span>
  )
}
