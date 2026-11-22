import { useEffect, useRef, useState } from "react"

import { ApiError } from "@/lib/api"

import { cancelPluginSignIn, getPluginSignIn, type SignInStarted } from "../api"

// The API answers from memory, so a short interval costs nothing.
const POLL_MS = 1000

export type PluginSignInState =
  | { phase: "idle" }
  | { phase: "waiting" }
  // Why, as the API said it; all null once the API has forgotten the sign-in.
  | {
      phase: "failed"
      code: string | null
      message: string | null
      host: string | null
      name: string | null
    }

function openSignInPage(url: string) {
  if (window.surfsense?.openExternal) {
    void window.surfsense.openExternal(url)
    return
  }
  // The browser dev build has no Electron bridge.
  window.open(url, "_blank", "noopener")
}

/**
 * Follows one plugin sign-in: opens the provider's page in the browser and polls
 * until the API reports it connected or failed. Leaving the screen cancels it.
 */
export function usePluginSignIn(onConnected: () => void) {
  const [state, setState] = useState<PluginSignInState>({ phase: "idle" })
  const flow = useRef<{ id: string; abort: AbortController } | null>(null)
  const connected = useRef(onConnected)
  useEffect(() => {
    connected.current = onConnected
  })

  const stop = () => {
    const current = flow.current
    flow.current = null
    if (!current) return
    current.abort.abort()
    void cancelPluginSignIn(current.id).catch(() => {})
  }

  useEffect(() => stop, [])

  const poll = async (id: string, abort: AbortController) => {
    while (!abort.signal.aborted) {
      await new Promise((resolve) => setTimeout(resolve, POLL_MS))
      if (abort.signal.aborted) return
      let progress
      try {
        progress = await getPluginSignIn(id, abort.signal)
      } catch (error) {
        if (abort.signal.aborted) return
        // Forgotten by the API: expired, or the API restarted. Anything else is retried.
        if (!(error instanceof ApiError && error.status === 404)) continue
        flow.current = null
        setState({
          phase: "failed",
          code: null,
          message: null,
          host: null,
          name: null,
        })
        return
      }
      if (progress.status === "connected") {
        flow.current = null
        setState({ phase: "idle" })
        connected.current()
        return
      }
      if (progress.status === "failed") {
        flow.current = null
        setState({
          phase: "failed",
          code: progress.code,
          message: progress.message,
          host: progress.host,
          name: progress.name,
        })
        return
      }
    }
  }

  const follow = (started: SignInStarted) => {
    stop()
    const abort = new AbortController()
    flow.current = { id: started.id, abort }
    setState({ phase: "waiting" })
    openSignInPage(started.authorization_url)
    void poll(started.id, abort)
  }

  const cancel = () => {
    stop()
    setState({ phase: "idle" })
  }

  return { state, follow, cancel }
}
