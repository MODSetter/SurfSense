import { useEffect, useState, type ReactNode } from "react"

import { setSignedOutHandler } from "@/lib/api"

import { getAccessState, type AccessState } from "./api"
import { SetupScreen } from "./setup-screen"
import { SignInScreen } from "./sign-in-screen"

type Gate = "checking" | "open" | "sign-in" | "setup"

function gateFor(state: AccessState): Gate {
  if (state.signInOff || state.signedIn) return "open"
  return state.password ? "sign-in" : "setup"
}

/** Docker only: the app behind its setup and sign-in (ADR 0074). */
export function AccessGate({ children }: { children: ReactNode }) {
  const [gate, setGate] = useState<Gate>("checking")

  useEffect(() => {
    let active = true
    const check = () =>
      getAccessState()
        .then((state) => {
          if (active) setGate(gateFor(state))
        })
        // The service is part of the image; if it can't be read, the API's own
        // refusals still stand, so the app opens and says what failed.
        .catch(() => {
          if (active) setGate("open")
        })
    void check()
    // A 401 from the API: signed out elsewhere, or the password changed.
    setSignedOutHandler(() => void check())
    return () => {
      active = false
      setSignedOutHandler(null)
    }
  }, [])

  if (gate === "checking") return null
  if (gate === "sign-in")
    return <SignInScreen onSignedIn={() => setGate("open")} />
  if (gate === "setup") return <SetupScreen onDone={() => setGate("open")} />
  return children
}
