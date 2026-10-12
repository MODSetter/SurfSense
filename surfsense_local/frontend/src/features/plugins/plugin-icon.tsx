import { useState } from "react"

import { cn } from "@/lib/utils"

import { registryIconUrl } from "./api"

/** The registry's verified icon, or the name's first letter when there is none or it fails to load. */
export function PluginIcon({
  id,
  name,
  hasIcon,
  className,
}: {
  id: string
  name: string
  hasIcon: boolean
  className?: string
}) {
  const [failed, setFailed] = useState(false)
  if (hasIcon && !failed) {
    return (
      <img
        src={registryIconUrl(id)}
        alt=""
        // Registry marks are light or coloured, so they sit on a grey tile, never the bare page.
        className={cn(
          "size-8 shrink-0 rounded-md bg-muted-foreground/35 object-contain p-1 outline -outline-offset-1 outline-black/10 dark:bg-muted dark:outline-white/10",
          className
        )}
        onError={() => setFailed(true)}
      />
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
