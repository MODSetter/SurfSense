import { useEffect, useState } from "react"

import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
import type { UpdateState } from "@/lib/api"

import { updatesBridge, useUpdateState } from "./use-update-state"

export type { UpdateState }

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
  const updates = updatesBridge()
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
