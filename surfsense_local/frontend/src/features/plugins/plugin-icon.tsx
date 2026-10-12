import { useState } from "react"

import { registryIconUrl } from "./api"

/** The registry's verified icon, or the name's first letter when there is none or it fails to load. */
export function PluginIcon({
  id,
  name,
  hasIcon,
}: {
  id: string
  name: string
  hasIcon: boolean
}) {
  const [failed, setFailed] = useState(false)
  if (hasIcon && !failed) {
    return (
      <img
        src={registryIconUrl(id)}
        alt=""
        className="size-8 shrink-0 rounded-md object-contain outline -outline-offset-1 outline-black/10 dark:outline-white/10"
        onError={() => setFailed(true)}
      />
    )
  }
  return (
    <span
      aria-hidden
      className="flex size-8 shrink-0 items-center justify-center rounded-md bg-muted text-sm font-medium text-muted-foreground uppercase"
    >
      {name.trim().charAt(0)}
    </span>
  )
}
