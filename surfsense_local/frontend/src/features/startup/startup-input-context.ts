import { createContext, useContext } from "react"

import type { StartupInput } from "./startup-input"

// Null outside AppBootstrap, as in a component's own tests: nothing to hand over.
export const StartupInputContext = createContext<StartupInput | null>(null)

export function useStartupInput(): StartupInput | null {
  return useContext(StartupInputContext)
}
