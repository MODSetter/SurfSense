import { createContext, useContext } from "react"

import type { PluginSignInState } from "./use-plugin-sign-in"

/** The sign-in a plugin was opened with, followed above its details so it outlives them. */
export type OpenedSignIn = {
  pluginId: string
  state: PluginSignInState
  cancel: () => void
}

export const OpenedSignInContext = createContext<OpenedSignIn | null>(null)

/** The opened sign-in, if it is this plugin's. */
export function useOpenedSignIn(pluginId: string): OpenedSignIn | null {
  const opened = useContext(OpenedSignInContext)
  return opened?.pluginId === pluginId ? opened : null
}
