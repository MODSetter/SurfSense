import { useEffect, useRef } from "react"
import { toast } from "sonner"

import { intl } from "@/i18n/intl"

import { useCheckForUpdates } from "./use-check-for-updates"
import { updatesBridge, useUpdateState } from "./use-update-state"

/**
 * The app menu's Check for Updates…. Mounted once at the app root. Settings
 * may be closed, so its own check's result comes back as a toast: up to date,
 * or failed. A found update shows in the title bar instead.
 */
export function MenuUpdateCheck() {
  const check = useCheckForUpdates()
  const state = useUpdateState()
  // Subscribed once; the latest check carries the latest consent.
  const checkRef = useRef(check)
  useEffect(() => {
    checkRef.current = check
  })
  // A result counts only once this check is seen running, so an earlier
  // check's "up to date" never answers it.
  const phase = useRef<"none" | "requested" | "running">("none")

  useEffect(
    () =>
      updatesBridge()?.onCheckRequested(() => {
        phase.current = "requested"
        void checkRef.current().then((started) => {
          if (!started && phase.current === "requested") phase.current = "none"
        })
      }),
    []
  )

  useEffect(() => {
    if (state.status === "checking") {
      if (phase.current === "requested") phase.current = "running"
      return
    }
    if (phase.current !== "running") return
    phase.current = "none"
    if (state.status === "up-to-date")
      toast.success(
        intl.formatMessage({
          id: "updates_menu_up_to_date_toast",
          defaultMessage: "SurfSense is up to date",
        })
      )
    else if (state.status === "error")
      toast.error(
        intl.formatMessage({
          id: "updates_menu_check_failed_toast",
          defaultMessage: "Couldn’t check for updates",
        }),
        { description: state.message }
      )
  }, [state])

  return null
}
