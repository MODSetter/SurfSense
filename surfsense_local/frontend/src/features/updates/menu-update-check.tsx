import { useEffect, useRef } from "react"

import { useCheckForUpdates } from "./use-check-for-updates"
import { updatesBridge } from "./use-update-state"

// The app menu's Check for Updates…. Mounted once at the app root; the
// sidebar and Settings › About show the result from the updater's own state.
export function MenuUpdateCheck() {
  const check = useCheckForUpdates()
  // Subscribed once; the latest check carries the latest consent.
  const checkRef = useRef(check)
  useEffect(() => {
    checkRef.current = check
  })

  useEffect(
    () => updatesBridge()?.onCheckRequested(() => void checkRef.current()),
    []
  )
  return null
}
