import { useEffect, useState, type ReactNode } from "react"

import { StartupRevealContext } from "./startup-reveal-context"

/**
 * Whether the dashboard's first draw fades in over the loading frame. True
 * through its first commit only, so nothing mounted later fades.
 */
export function StartupRevealProvider({
  reveal,
  children,
}: {
  reveal: boolean
  children: ReactNode
}) {
  const [active, setActive] = useState(reveal)
  useEffect(() => {
    if (!active) return
    // After this commit's own effects, which have read it already.
    const timer = setTimeout(() => setActive(false), 0)
    return () => clearTimeout(timer)
  }, [active])
  return (
    <StartupRevealContext.Provider value={active}>
      {children}
    </StartupRevealContext.Provider>
  )
}
