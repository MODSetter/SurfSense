import { useEffect, useRef, useState } from "react"

import {
  cancelSignIn,
  getSignIn,
  HostDeclinedError,
  startSignIn,
  type SignInTarget,
} from "./api"

// The API answers from memory, so a short interval costs nothing and the
// dialog moves on as soon as the browser hands the code back.
const POLL_MS = 1000

export type SignInState =
  | { phase: "idle" }
  | { phase: "starting" }
  | { phase: "waiting"; authorizeUrl: string }
  | { phase: "declined"; host: string }
  | { phase: "failed"; detail: string | null }

export function openSignInPage(url: string) {
  if (window.surfsense?.openExternal) {
    void window.surfsense.openExternal(url)
    return
  }
  // The browser dev build has no Electron bridge.
  window.open(url, "_blank", "noopener")
}

/**
 * One ChatGPT sign-in: starts it, opens the browser, and polls until the
 * API reports the connection signed in. Closing the dialog first cancels it,
 * which frees the API's loopback port.
 */
export function useChatGPTSignIn(onSignedIn: (connectionId: number) => void) {
  const [state, setState] = useState<SignInState>({ phase: "idle" })
  const flow = useRef<{ id: string; abort: AbortController } | null>(null)
  const signedIn = useRef(onSignedIn)
  useEffect(() => {
    signedIn.current = onSignedIn
  })

  const stop = () => {
    const current = flow.current
    flow.current = null
    if (!current) return
    current.abort.abort()
    void cancelSignIn(current.id).catch(() => {})
  }

  useEffect(() => stop, [])

  const poll = async (id: string, abort: AbortController) => {
    while (!abort.signal.aborted) {
      await new Promise((resolve) => setTimeout(resolve, POLL_MS))
      if (abort.signal.aborted) return
      let current
      try {
        current = await getSignIn(id, abort.signal)
      } catch {
        if (abort.signal.aborted) return
        continue
      }
      if (current.status === "signed_in" && current.connection_id !== null) {
        flow.current = null
        setState({ phase: "idle" })
        signedIn.current(current.connection_id)
        return
      }
      if (current.status === "failed") {
        flow.current = null
        setState({ phase: "failed", detail: current.message })
        return
      }
    }
  }

  const start = async (target: SignInTarget) => {
    stop()
    setState({ phase: "starting" })
    try {
      const started = await startSignIn(target)
      const abort = new AbortController()
      flow.current = { id: started.flow_id, abort }
      setState({ phase: "waiting", authorizeUrl: started.authorize_url })
      openSignInPage(started.authorize_url)
      void poll(started.flow_id, abort)
    } catch (error) {
      setState(
        error instanceof HostDeclinedError
          ? { phase: "declined", host: error.host }
          : {
              phase: "failed",
              detail: error instanceof Error ? error.message : null,
            }
      )
    }
  }

  const cancel = () => {
    stop()
    setState({ phase: "idle" })
  }

  return { state, start, cancel }
}
