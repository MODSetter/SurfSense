import { createContext, useContext } from "react"

import type { SignInStarted } from "../api"
import type { PluginSignInState } from "./use-plugin-sign-in"

/** Sign-ins followed by Settings › Plugins, so one outlives the row or page that started it. */
export type FollowedSignIn = {
  /** The plugin whose sign-in is followed, if any. */
  pluginId: string | null
  state: PluginSignInState
  cancel: () => void
  follow: (pluginId: string, started: SignInStarted) => void
}

export const OpenedSignInContext = createContext<FollowedSignIn | null>(null)

/** The followed sign-in, if it is this plugin's. */
export function useOpenedSignIn(pluginId: string): FollowedSignIn | null {
  const followed = useContext(OpenedSignInContext)
  return followed?.pluginId === pluginId ? followed : null
}

/** Every caller is inside Settings › Plugins, which provides it. */
export function useFollowSignIn(): FollowedSignIn["follow"] {
  const followed = useContext(OpenedSignInContext)
  if (!followed) throw new Error("useFollowSignIn outside Settings › Plugins")
  return followed.follow
}
