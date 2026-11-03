import { useContext, useEffect, useState } from "react"

import { StartupRevealContext } from "./startup-reveal-context"

/** `.ss-reveal` in `index.css` runs 200 ms; the class is dropped after it ends. */
const REVEAL_CLEAR_MS = 400

/**
 * The class for a container whose contents fade in at startup while the
 * container stays put: the loading frame drew the container already.
 */
export function useStartupReveal(): string {
  const reveal = useContext(StartupRevealContext)
  const [fading, setFading] = useState(reveal)
  useEffect(() => {
    if (!fading) return
    const timer = setTimeout(() => setFading(false), REVEAL_CLEAR_MS)
    return () => clearTimeout(timer)
  }, [fading])
  return fading ? "ss-reveal" : ""
}
