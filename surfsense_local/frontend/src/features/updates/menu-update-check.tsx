import { useEffect, useRef } from "react"

import { useReportedCheck } from "./use-reported-check"
import { updatesBridge } from "./use-update-state"

/**
 * The app menu's Check for Updates…. Mounted once at the app root, so its
 * result comes back as a toast whether or not Settings is open.
 */
export function MenuUpdateCheck() {
  const check = useReportedCheck()
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
