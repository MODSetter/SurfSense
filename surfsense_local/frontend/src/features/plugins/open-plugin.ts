import { createContext, useContext } from "react"

import type { SignInStarted } from "./api"

/**
 * Opens a plugin's details in Yours, where a plugin is finished whatever it needs. A sign-in
 * started elsewhere goes with it and is followed by Settings › Plugins: followed by the dialog
 * or card that started it, it would end once that closed.
 */
export type OpenPlugin = (pluginId: string, signIn?: SignInStarted) => void

export const OpenPluginContext = createContext<OpenPlugin | null>(null)

/** Every caller is inside Settings › Plugins, which provides it. */
export function useOpenPlugin(): OpenPlugin {
  const openPlugin = useContext(OpenPluginContext)
  if (!openPlugin) throw new Error("useOpenPlugin outside Settings › Plugins")
  return openPlugin
}
