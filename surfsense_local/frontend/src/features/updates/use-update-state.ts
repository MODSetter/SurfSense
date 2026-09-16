import { useEffect, useState } from "react"

import type { UpdateState } from "@/lib/api"

const IDLE: UpdateState = { status: "idle" }

// The preload bridge, absent in a bare browser and in the web build.
export function updatesBridge() {
  return typeof window === "undefined" ? undefined : window.surfsense?.updates
}

export function useUpdateState() {
  const [state, setState] = useState<UpdateState>(IDLE)
  useEffect(() => {
    const updates = updatesBridge()
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
