import { useEffect, useState } from "react"

import { Button } from "@/components/ui/button"
import type { UpdateState } from "@/lib/api"

export type { UpdateState }

const IDLE: UpdateState = { status: "idle" }

// The preload bridge, absent in a bare browser and in the web build.
function bridge() {
  return typeof window === "undefined" ? undefined : window.surfsense?.updates
}

function useUpdateState() {
  const [state, setState] = useState<UpdateState>(IDLE)
  useEffect(() => {
    const updates = bridge()
    if (!updates) return
    // An event that lands while the first read is in flight is the newer truth.
    let pushed = false
    const unsubscribe = updates.onState((state) => {
      pushed = true
      setState(state)
    })
    void updates.state().then((state) => {
      if (!pushed) setState(state)
    })
    return unsubscribe
  }, [])
  return state
}

function statusText(state: UpdateState) {
  switch (state.status) {
    case "checking":
      return "Checking…"
    case "up-to-date":
      return "SurfSense is up to date"
    case "downloading":
      return `Downloading ${state.version}…`
    case "ready":
      return `SurfSense ${state.version} is ready to install`
    default:
      return null
  }
}

export function UpdateSettings() {
  const updates = bridge()
  const state = useUpdateState()
  const [automatic, setAutomatic] = useState<boolean | null>(null)

  useEffect(() => {
    void updates?.prefs().then((prefs) => setAutomatic(prefs.automatic))
  }, [updates])

  if (!updates || automatic === null) return null

  const text = statusText(state)
  return (
    <div className="mt-8 flex items-start justify-between gap-8">
      <div className="flex flex-col gap-1">
        <h3 className="text-sm font-medium">Updates</h3>
        <p className="text-sm text-pretty text-muted-foreground">
          Updates come from GitHub Releases and are free for everyone. Until you
          turn this on, SurfSense never checks on its own.
        </p>
        <label className="mt-2 flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            className="size-4 accent-primary"
            checked={automatic}
            onChange={(event) => {
              const next = event.target.checked
              setAutomatic(next)
              void updates.setAutomatic(next)
            }}
          />
          Check for updates automatically
        </label>
        {state.status === "error" ? (
          <p role="alert" className="text-sm text-destructive">
            Could not check for updates: {state.message}
          </p>
        ) : text ? (
          <p className="text-sm text-muted-foreground">{text}</p>
        ) : null}
      </div>
      {state.status === "ready" ? (
        <Button type="button" onClick={() => void updates.install()}>
          Restart to update
        </Button>
      ) : (
        <Button
          type="button"
          variant="outline"
          disabled={
            state.status === "checking" || state.status === "downloading"
          }
          onClick={() => void updates.check()}
        >
          Check now
        </Button>
      )}
    </div>
  )
}

export function UpdateBanner() {
  const state = useUpdateState()
  if (state.status !== "ready") return null
  return (
    <div
      role="status"
      className="flex items-center justify-between gap-4 border-b bg-muted/60 px-4 py-2 text-sm"
    >
      <span>SurfSense {state.version} is ready to install.</span>
      <Button type="button" size="sm" onClick={() => void bridge()?.install()}>
        Restart to update
      </Button>
    </div>
  )
}
