import { useEffect, useState } from "react"

import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
import { DownloadCircle02Icon } from "@/components/ui/icons"
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip"
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
          <Checkbox
            checked={automatic}
            onCheckedChange={(checked) => {
              const next = checked === true
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

/**
 * Sits in the title bar and appears only once an update has been downloaded
 * and is waiting. Shaped exactly like the right-panel toggle beside it — ghost,
 * same size — so only the color sets it apart.
 *
 * The title bar is `position: fixed`, so this button is out of the document
 * flow: rendering nothing costs no space and cannot disturb the layout around
 * it.
 */
export function UpdateButton() {
  const state = useUpdateState()
  if (state.status !== "ready") return null
  const label = `Restart to install ${state.version}`
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <Button
          type="button"
          variant="ghost"
          size="icon-sm"
          aria-label={label}
          className="pointer-events-auto size-6 text-notice hover:text-notice"
          onClick={() => void bridge()?.install()}
        >
          <DownloadCircle02Icon />
        </Button>
      </TooltipTrigger>
      <TooltipContent side="bottom" collisionPadding={8}>
        {label}
      </TooltipContent>
    </Tooltip>
  )
}
