import { useCallback, useContext, useState } from "react"

import { StartupRevealContext } from "./startup-reveal-context"

export type StartupReveal = {
  className?: string
  ref?: (element: HTMLElement | null) => (() => void) | undefined
}

/**
 * Props for a container whose contents fade in at startup while it stays
 * put: the loading frame drew it already. Spread them, and merge `className`.
 * The fade ends when its contents' animation does, so contents added later
 * arrive as usual; under reduced motion nothing animates and nothing shows.
 */
export function useStartupReveal(): StartupReveal {
  const reveal = useContext(StartupRevealContext)
  const [fading, setFading] = useState(reveal)
  // A native listener: React names animation events by what the page
  // supports, so its own handler is not one name everywhere.
  const ref = useCallback((element: HTMLElement | null) => {
    if (!element) return undefined
    // The contents animate, not the container; their end bubbles up here.
    const ended = (event: Event) => {
      if (event.target !== element) setFading(false)
    }
    element.addEventListener("animationend", ended)
    return () => element.removeEventListener("animationend", ended)
  }, [])
  return fading ? { className: "ss-reveal", ref } : {}
}
